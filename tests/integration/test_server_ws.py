"""WebSocket /ws/stream: replay de 60 s ao conectar e transmissão ao vivo."""

from __future__ import annotations

from fastapi.testclient import TestClient

from fakes import FakeClock, make_sample
from obd.protocol.schemas import DtcEntry, DtcReport
from obd.server.app import create_app
from obd.server.storage import InMemoryStorage


def test_cliente_recebe_os_ultimos_60_segundos_ao_conectar_e_depois_ao_vivo() -> None:
    clock = FakeClock(start=1000.0)
    app = create_app(InMemoryStorage(), clock=clock)
    with TestClient(app) as client:
        client.post("/api/ingest/sample", json=make_sample(0, ts=900.0).model_dump())  # fora
        client.post("/api/ingest/sample", json=make_sample(1, ts=990.0).model_dump())  # dentro
        dtc = DtcReport(
            ts=995.0,
            mil=True,
            count=1,
            codes=[DtcEntry(code="P0300", description="Falha de ignição")],
        )
        client.post("/api/ingest/dtc", json=dtc.model_dump())

        with client.websocket_connect("/ws/stream") as ws:
            replay_sample = ws.receive_json()
            replay_dtc = ws.receive_json()

            assert replay_sample["type"] == "sample"
            assert replay_sample["data"]["seq"] == 1
            assert replay_dtc["type"] == "dtc"
            assert replay_dtc["data"]["codes"][0]["code"] == "P0300"

            clock.now = 1001.0
            client.post("/api/ingest/sample", json=make_sample(2, ts=1001.0).model_dump())
            live = ws.receive_json()

            assert live["type"] == "sample"
            assert live["data"]["seq"] == 2
