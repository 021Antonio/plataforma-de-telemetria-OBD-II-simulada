"""E6: cliente ELM327 comum (soquete TCP cru, como um app) contra o servidor TCP."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from obd.simulator.control_api import Simulator
from obd.simulator.elm327_server import Elm327Server
from obd.transport.loopback import LoopbackTransport

from .runner import (
    RunOutput,
    Scenario,
    default_out_dir,
    parse_args,
    print_table,
    write_outputs,
)

NAME = "E6"

# (comando, expressão que a resposta deve satisfazer). O eco liga após o ATZ, como no chip real.
COMMANDS: tuple[tuple[str, str], ...] = (
    ("ATZ", r"ELM327 v1\.5"),
    ("ATE0", r"OK"),
    ("ATL0", r"OK"),
    ("ATS1", r"OK"),
    ("ATH0", r"OK"),
    ("ATSP0", r"OK"),
    ("ATDP", r"ISO 15765-4.*"),
    ("ATRV", r"\d+\.\dV"),
    ("0100", r"SEARCHING\.\.\.\s+41 00 ([0-9A-F]{2} ?){4}"),
    ("0120", r"41 20 ([0-9A-F]{2} ?){4}"),
    ("010C", r"41 0C [0-9A-F]{2} [0-9A-F]{2}"),
    ("010D", r"41 0D [0-9A-F]{2}"),
    ("0105", r"41 05 [0-9A-F]{2}"),
    ("0111", r"41 11 [0-9A-F]{2}"),
    ("0101", r"41 01 ([0-9A-F]{2} ?){4}"),
    ("03", r"NO DATA|43 .*"),
    ("0902", r"49 02 01 ([0-9A-F]{2} ?)+"),
    ("01FF", r"NO DATA"),
    ("XYZ", r"\?"),
)


async def _ask(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, cmd: str) -> str:
    writer.write(cmd.encode() + b"\r")
    await writer.drain()
    raw = await asyncio.wait_for(reader.readuntil(b">"), timeout=6.0)
    lines = [ln.strip() for ln in raw.decode("latin-1").replace("\r", "\n").split("\n")]
    lines = [ln for ln in lines if ln and ln != ">" and ln != cmd]  # tira o eco e o prompt
    return " ".join(lines).rstrip(">").strip()


async def run(
    out_dir: Path, duration: float | None = None, *, plot: bool = False
) -> dict[str, Any]:
    sim = Simulator(time.monotonic)
    server = Elm327Server(LoopbackTransport(sim.ecu, clock=time.monotonic), port=0)
    await server.start()
    rows: list[dict[str, Any]] = []
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
        for cmd, pattern in COMMANDS:
            t0 = time.perf_counter()
            reply = await _ask(reader, writer, cmd)
            ms = (time.perf_counter() - t0) * 1000
            rows.append(
                {
                    "run": "elm327",
                    "comando": cmd,
                    "esperado": pattern,
                    "resposta": reply,
                    "ok": bool(re.fullmatch(pattern, reply)),
                    "tempo_ms": ms,
                }
            )
        writer.close()
    finally:
        await server.stop()
    passed = sum(1 for r in rows if r["ok"])
    metrics = {
        "comandos": len(rows),
        "compativeis": passed,
        "compatibilidade": passed / len(rows),
        "falhas": [r["comando"] for r in rows if not r["ok"]],
    }
    result = RunOutput(Scenario(label="elm327", duration_s=0.0), [], metrics)
    return write_outputs(NAME, out_dir, [result], config={"comandos": len(COMMANDS)}, csv_rows=rows)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(__doc__ or NAME, argv)
    print_table(asyncio.run(run(args.out or default_out_dir(), args.duration)))


if __name__ == "__main__":
    main()
