"""Gera `dourado.json` a partir do simulador com valores fixos: `python -m tests.conformance.gerar`.

Os valores vêm de `VALORES_FIXOS` e o relógio é só o `time.monotonic` que o ECU exige; nada na
resposta depende do tempo.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fakes import FakeVehicleModel
from obd.simulator.ecu import Ecu
from obd.simulator.elm327_server import Elm327Server
from obd.transport.loopback import LoopbackTransport

from .executor import DOURADO, capturar
from .roteiro import ROTEIRO

VALORES_FIXOS = {
    0x04: 42.0,
    0x05: 88.0,
    0x06: 0.0,
    0x0B: 33.0,
    0x0C: 3127.5,
    0x0D: 77.0,
    0x0F: 31.0,
    0x11: 18.5,
    0x2F: 61.2,
    0x42: 13.987,
}


@asynccontextmanager
async def servidor_fixo() -> AsyncIterator[Elm327Server]:
    """`Elm327Server` na porta livre escolhida pelo SO, com valores fixos e sem DTCs."""
    ecu = Ecu(FakeVehicleModel(VALORES_FIXOS, time.monotonic), time.monotonic)
    server = Elm327Server(LoopbackTransport(ecu), port=0)
    await server.start()
    try:
        yield server
    finally:
        await server.stop()


async def gerar() -> list[dict[str, str]]:
    async with servidor_fixo() as server:
        respostas = await capturar("127.0.0.1", server.port)
    return [{"comando": p.comando, "resposta": r} for p, r in zip(ROTEIRO, respostas, strict=True)]


if __name__ == "__main__":
    dados = asyncio.run(gerar())
    DOURADO.write_text(json.dumps(dados, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(dados)} respostas em {DOURADO}")
