"""`python -m obd run` como subprocesso, com portas livres e banco temporário."""

from __future__ import annotations

import asyncio
import json
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
from websockets.asyncio.client import connect


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@dataclass
class Rig:
    proc: subprocess.Popen[bytes]
    servidor: int
    painel: int
    elm327: int

    @property
    def api(self) -> str:
        return f"http://127.0.0.1:{self.servidor}"

    @property
    def sim(self) -> str:
        return f"http://127.0.0.1:{self.painel}"


def _until(cond: Callable[[], bool], timeout: float, step: float = 0.1) -> bool:
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if cond():
            return True
        time.sleep(step)
    return cond()


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    portas = [_free_port() for _ in range(3)]
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "obd",
            "run",
            "--db",
            str(tmp_path / "obd.db"),
            "--porta-servidor",
            str(portas[0]),
            "--porta-painel",
            str(portas[1]),
            "--porta-elm327",
            str(portas[2]),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    r = Rig(proc, *portas)
    try:
        yield r
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
        assert proc.stderr is not None
        proc.stderr.close()


def _get(url: str) -> httpx.Response | None:
    try:
        return httpx.get(url, timeout=1.0)
    except httpx.HTTPError:
        return None


def _latest(r: Rig) -> dict[str, Any] | None:
    resp = _get(f"{r.api}/api/latest")
    return resp.json() if resp is not None and resp.status_code == 200 else None


def _espera_saudavel(r: Rig) -> None:
    def ok() -> bool:
        resp = _get(f"{r.api}/healthz")
        return resp is not None and resp.status_code == 200

    assert _until(ok, 10), "GET /healthz não respondeu em 10 s"


def test_healthz_responde_em_ate_10s(rig: Rig) -> None:
    _espera_saudavel(rig)


def test_latest_traz_rpm_velocidade_e_temperatura(rig: Rig) -> None:
    _espera_saudavel(rig)

    def completo() -> bool:
        s = _latest(rig)
        return s is not None and {"rpm", "speed", "coolant"} <= set(s["values"])

    assert _until(completo, 10), "amostra com rpm, speed e coolant não chegou em 10 s"


def test_dashboard_e_painel_servidos_na_raiz(rig: Rig) -> None:
    _espera_saudavel(rig)
    assert _until(lambda: (_get(f"{rig.sim}/") or httpx.Response(500)).status_code == 200, 10)
    assert "<html" in httpx.get(f"{rig.api}/").text.lower()
    assert "<html" in httpx.get(f"{rig.sim}/").text.lower()


def test_websocket_entrega_ao_menos_5_amostras_em_5s(rig: Rig) -> None:
    _espera_saudavel(rig)

    async def ouvir() -> int:
        n = 0
        async with connect(f"ws://127.0.0.1:{rig.servidor}/ws/stream") as ws:
            async with asyncio.timeout(5):
                while n < 5:
                    msg = json.loads(await ws.recv())
                    if msg["type"] == "sample":
                        n += 1
        return n

    assert asyncio.run(ouvir()) >= 5


def test_override_do_painel_chega_ao_coletor(rig: Rig) -> None:
    _espera_saudavel(rig)
    assert _until(lambda: _latest(rig) is not None, 10)
    assert _until(lambda: _get(f"{rig.sim}/sim/state") is not None, 5)
    resp = httpx.put(f"{rig.sim}/sim/override/rpm", json={"value": 3000})
    assert resp.status_code == 200

    def aplicado() -> bool:
        s = _latest(rig)
        return s is not None and abs(s["values"]["rpm"]["value"] - 3000) <= 1

    assert _until(aplicado, 2), "rotação 3000 não apareceu em /api/latest em 2 s"


def test_dtc_injetado_aparece_com_mil(rig: Rig) -> None:
    _espera_saudavel(rig)
    assert _until(lambda: _latest(rig) is not None, 10)
    resp = httpx.post(f"{rig.sim}/sim/dtc", json={"code": "P0300", "pending": False})
    assert resp.status_code in (200, 201)

    def listado() -> bool:
        r = _get(f"{rig.api}/api/dtc")
        if r is None:
            return False
        relatorios = r.json()
        return (
            bool(relatorios)
            and relatorios[-1]["mil"] is True
            and any(c["code"] == "P0300" for c in relatorios[-1]["codes"])
        )

    assert _until(listado, 10), "P0300 com MIL não apareceu em /api/dtc"


def test_elm327_responde_010c_por_soquete_cru(rig: Rig) -> None:
    _espera_saudavel(rig)

    def conecta() -> socket.socket | None:
        try:
            return socket.create_connection(("127.0.0.1", rig.elm327), timeout=2)
        except OSError:
            return None

    sock: socket.socket | None = None
    limite = time.monotonic() + 10
    while sock is None and time.monotonic() < limite:
        sock = conecta()
        if sock is None:
            time.sleep(0.1)
    assert sock is not None
    with sock:
        sock.settimeout(3)
        buf = b""
        sock.sendall(b"010C\r")
        while b">" not in buf:
            buf += sock.recv(256)
    assert "41 0C" in buf.decode()


@pytest.mark.parametrize("sinal", [signal.SIGINT, signal.SIGTERM])
def test_sinal_encerra_com_codigo_0_em_ate_5s(rig: Rig, sinal: signal.Signals) -> None:
    _espera_saudavel(rig)
    assert _until(lambda: _latest(rig) is not None, 10)
    rig.proc.send_signal(sinal)
    assert rig.proc.wait(timeout=5) == 0
    assert rig.proc.stderr is not None
    assert "Traceback" not in rig.proc.stderr.read().decode()


def test_source_reporta_o_transporte_configurado(rig: Rig) -> None:
    import yaml

    cfg = yaml.safe_load((Path(__file__).resolve().parents[2] / "config/default.yaml").read_text())
    _espera_saudavel(rig)
    assert _until(lambda: _latest(rig) is not None, 10)
    s = _latest(rig)
    assert s is not None
    assert s["source"] == cfg["coletor"]["transporte"]
    assert cfg["can"]["transporte"] == cfg["coletor"]["transporte"]


def test_pids_lentos_chegam_no_plano_padrao(rig: Rig) -> None:
    _espera_saudavel(rig)
    lentos = {"coolant", "fuel_level", "voltage", "short_fuel_trim"}

    vistos: set[str] = set()
    limite = time.monotonic() + 5
    while time.monotonic() < limite and not lentos <= vistos:
        s = _latest(rig)
        if s:
            vistos |= set(s["values"])
        time.sleep(0.05)
    assert lentos <= vistos
