"""Servidor ELM327 simulado lido por um cliente de terceiros (python-OBD, `pip install obd`).

O pacote do PyPI se chama `obd`, como o nosso: por isso é instalado num venv temporário e roda
em subprocesso, nunca no venv do projeto.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import textwrap
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from obd.protocol.pids import get_pid
from obd.simulator.control_api import Simulator
from obd.simulator.elm327_server import Elm327Server
from obd.transport.loopback import LoopbackTransport

pytestmark = pytest.mark.realclient

OBD_VERSION = "0.7.3"
CLIENT_SCRIPT = textwrap.dedent(
    """
    import json, sys
    import obd

    conn = obd.OBD(portstr=sys.argv[1], fast=False, timeout=5)
    out = {"status": conn.status(), "protocol": conn.protocol_name()}
    for key, cmd in {
        "rpm": obd.commands.RPM,
        "speed": obd.commands.SPEED,
        "coolant": obd.commands.COOLANT_TEMP,
        "load": obd.commands.ENGINE_LOAD,
        "throttle": obd.commands.THROTTLE_POS,
        "fuel": obd.commands.FUEL_LEVEL,
    }.items():
        r = conn.query(cmd)
        out[key] = None if r.is_null() else float(r.value.magnitude)
    r = conn.query(obd.commands.GET_DTC)
    out["dtcs"] = [] if r.is_null() else [code for code, _ in r.value]
    conn.close()
    print(json.dumps(out))
    """
)


@pytest.fixture(scope="module")
def client_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    venv = tmp_path_factory.mktemp("obd-venv")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, timeout=120)
        py = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run(
            [str(py), "-m", "pip", "install", "-q", f"obd=={OBD_VERSION}"],
            check=True,
            timeout=300,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"sem rede para instalar o python-OBD: {exc}")
    return py


@pytest.fixture
async def rig() -> AsyncIterator[tuple[Simulator, Elm327Server]]:
    sim = Simulator(lambda: 10.0, profile="urbano")
    server = Elm327Server(LoopbackTransport(sim), port=0)
    await server.start()
    try:
        yield sim, server
    finally:
        await server.stop()


async def read_with_python_obd(py: Path, tmp: Path, port: int) -> dict[str, object]:
    script = tmp / "client.py"  # fora do cwd do projeto: nada de `import obd` do nosso pacote
    script.write_text(CLIENT_SCRIPT)
    proc = await asyncio.create_subprocess_exec(
        str(py),
        "-I",
        str(script),
        f"socket://127.0.0.1:{port}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(tmp),
    )
    out, err = await asyncio.wait_for(proc.communicate(), 60)
    assert proc.returncode == 0, err.decode()
    data: dict[str, object] = json.loads(out.decode().strip().splitlines()[-1])
    return data


def approx(sim: Simulator, key: str, pid: int, got: object) -> None:
    assert isinstance(got, float), f"{key} não foi lido"
    assert abs(got - sim.model.value(pid)) <= get_pid(pid).resolution + 1e-6, key


async def test_python_obd_reads_state_and_dtcs(
    rig: tuple[Simulator, Elm327Server], client_python: Path, tmp_path: Path
) -> None:
    sim, server = rig
    sim.set_override("rpm", 3000)
    data = await read_with_python_obd(client_python, tmp_path, server.port)
    assert data["status"] == "Car Connected"
    assert data["protocol"] == "ISO 15765-4 (CAN 11/500)"
    assert data["rpm"] == pytest.approx(3000, abs=0.25)
    for key, pid in (("speed", 0x0D), ("coolant", 0x05), ("load", 0x04)):
        approx(sim, key, pid, data[key])
    for key, pid in (("throttle", 0x11), ("fuel", 0x2F)):
        approx(sim, key, pid, data[key])
    assert data["dtcs"] == []

    sim.inject_dtc("P0300", pending=False)
    data = await read_with_python_obd(client_python, tmp_path, server.port)
    assert data["dtcs"] == ["P0300"]
