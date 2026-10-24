"""API REST do servidor, com memória e SQLite temporário (mesmo comportamento nos dois)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from fakes import FakeClock, make_sample
from obd.protocol.schemas import DtcEntry, DtcReport, PidValue
from obd.server.app import create_app
from obd.server.storage import InMemoryStorage, SqlStorage, Storage


@pytest.fixture(params=["memory", "sqlite"])
async def storage(request: pytest.FixtureRequest, tmp_path: Path) -> AsyncIterator[Storage]:
    if request.param == "memory":
        yield InMemoryStorage()
        return
    sql = await SqlStorage.create(f"sqlite+aiosqlite:///{tmp_path / 'obd.db'}")
    yield sql
    await sql.close()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(start=1000.0)


@pytest.fixture
async def client(storage: Storage, clock: FakeClock) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(storage, clock=clock)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def test_healthz_responde_200(client: httpx.AsyncClient) -> None:
    resp = await client.get("/healthz")

    assert resp.status_code == 200


async def test_ingestao_retorna_202_e_latest_devolve_a_amostra(
    client: httpx.AsyncClient, clock: FakeClock
) -> None:
    clock.now = 1000.004

    resp = await client.post("/api/ingest/sample", json=make_sample(0, ts=1000.0).model_dump())
    latest = await client.get("/api/latest")

    assert resp.status_code == 202
    assert latest.status_code == 200
    assert latest.json()["seq"] == 0
    assert latest.json()["values"]["rpm"]["value"] == 2000.0


async def test_latest_sem_amostras_retorna_404(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/latest")

    assert resp.status_code == 404


async def test_historico_filtra_por_since_e_limit(
    client: httpx.AsyncClient, clock: FakeClock
) -> None:
    clock.now = 1005.0
    for seq in range(5):
        await client.post("/api/ingest/sample", json=make_sample(seq, ts=1000.0 + seq).model_dump())

    resp = await client.get("/api/history", params={"since": 1002.0, "limit": 2})

    assert resp.status_code == 200
    assert [s["seq"] for s in resp.json()] == [2, 3]


async def test_dtc_guarda_relatorios_com_e_sem_codigos(client: httpx.AsyncClient) -> None:
    com_falha = DtcReport(
        ts=1000.0,
        mil=True,
        count=1,
        codes=[DtcEntry(code="P0300", description="Falha de ignição aleatória")],
    )
    sem_falha = DtcReport(ts=1001.0, mil=False, count=0)

    r1 = await client.post("/api/ingest/dtc", json=com_falha.model_dump())
    r2 = await client.post("/api/ingest/dtc", json=sem_falha.model_dump())
    resp = await client.get("/api/dtc")

    assert r1.status_code == 202
    assert r2.status_code == 202
    reports = resp.json()
    assert len(reports) == 2
    assert reports[0]["codes"][0]["code"] == "P0300"
    assert reports[0]["mil"] is True
    assert reports[1]["codes"] == []
    assert reports[1]["mil"] is False


async def test_perda_e_duplicacao_sao_contadas_por_seq(
    client: httpx.AsyncClient, clock: FakeClock
) -> None:
    clock.now = 1000.0
    for seq in [0, 1, 3, 3]:
        resp = await client.post(
            "/api/ingest/sample", json=make_sample(seq, ts=1000.0).model_dump()
        )
        assert resp.status_code == 202  # duplicata não é erro para o coletor

    stats = (await client.get("/api/stats")).json()

    assert stats["received"] == 3
    assert stats["lost"] == 1  # falta o seq 2
    assert stats["duplicated"] == 1


async def test_estatisticas_de_latencia(client: httpx.AsyncClient, clock: FakeClock) -> None:
    clock.now = 1000.0
    for seq, lat_ms in enumerate([2.0, 4.0, 6.0]):
        await client.post(
            "/api/ingest/sample",
            json=make_sample(seq, ts=1000.0 - lat_ms / 1000.0).model_dump(),
        )

    latency = (await client.get("/api/stats")).json()["latency_ms"]

    assert latency["mean"] == pytest.approx(4.0)
    assert latency["max"] == pytest.approx(6.0)


async def test_taxa_de_atualizacao_usa_janela_de_3_segundos(
    client: httpx.AsyncClient, clock: FakeClock
) -> None:
    clock.now = 1000.0
    for seq in range(6):
        await client.post("/api/ingest/sample", json=make_sample(seq, ts=1000.0).model_dump())

    stats = (await client.get("/api/stats")).json()

    assert stats["update_rate_hz"] == pytest.approx(2.0)


async def test_exportacao_csv_tem_uma_linha_por_leitura(
    client: httpx.AsyncClient, clock: FakeClock
) -> None:
    clock.now = 1000.0
    values = {
        "rpm": PidValue(pid="0x0C", value=2000.0, unit="rpm", rtt_ms=11.0),
        "speed": PidValue(pid="0x0D", value=62.0, unit="km/h", rtt_ms=11.4),
    }
    await client.post(
        "/api/ingest/sample", json=make_sample(0, ts=1000.0, values=values).model_dump()
    )

    resp = await client.get("/api/export.csv", params={"since": 0})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    linhas = resp.text.strip().splitlines()
    assert linhas[0].startswith("seq,ts_pub,ts_recv")
    assert len(linhas) == 1 + 2
    assert linhas[1].startswith("0,")
