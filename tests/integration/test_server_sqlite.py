"""Persistência em SQLite temporário (docs/spec/07-dados-web.md) e RNF02."""

from __future__ import annotations

import math
import time
from pathlib import Path

import httpx

from fakes import FakeClock, make_sample
from obd.protocol.schemas import DtcEntry, DtcReport
from obd.server.app import create_app
from obd.server.storage import SqlStorage


def _url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'obd.db'}"


async def test_reiniciar_a_aplicacao_preserva_amostras_e_dtcs(tmp_path: Path) -> None:
    clock = FakeClock(start=1000.0)
    storage = await SqlStorage.create(_url(tmp_path))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(storage, clock=clock)),
        base_url="http://test",
    ) as http:
        for seq in range(2):
            await http.post(
                "/api/ingest/sample", json=make_sample(seq, ts=1000.0 + seq).model_dump()
            )
        report = DtcReport(
            ts=1000.5,
            mil=True,
            count=1,
            codes=[DtcEntry(code="P0300", description="Falha de ignição")],
        )
        await http.post("/api/ingest/dtc", json=report.model_dump())
    await storage.close()

    reiniciado = await SqlStorage.create(_url(tmp_path))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(reiniciado, clock=clock)),
        base_url="http://test",
    ) as http:
        history = (await http.get("/api/history")).json()
        dtcs = (await http.get("/api/dtc")).json()
    await reiniciado.close()

    assert [s["seq"] for s in history] == [0, 1]
    assert history[0]["values"]["rpm"] == {
        "pid": "0x0C",
        "value": 2000.0,
        "unit": "rpm",
        "rtt_ms": 11.0,
    }
    assert dtcs[0]["codes"][0]["code"] == "P0300"


async def test_p95_da_ingestao_local_abaixo_de_50_ms(tmp_path: Path) -> None:
    clock = FakeClock(start=1000.0)
    storage = await SqlStorage.create(_url(tmp_path))
    duracoes_ms: list[float] = []
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(storage, clock=clock)),
        base_url="http://test",
    ) as http:
        for seq in range(300):
            corpo = make_sample(seq, ts=1000.0 + seq * 0.1).model_dump()
            inicio = time.perf_counter()
            resp = await http.post("/api/ingest/sample", json=corpo)
            duracoes_ms.append((time.perf_counter() - inicio) * 1000.0)
            assert resp.status_code == 202
    await storage.close()

    duracoes_ms.sort()
    p95 = duracoes_ms[math.ceil(0.95 * len(duracoes_ms)) - 1]
    assert p95 < 50.0
