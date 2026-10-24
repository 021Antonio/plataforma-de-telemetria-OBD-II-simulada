"""Publicadores: o coletor entrega amostras e relatórios de DTC por esta interface."""

from __future__ import annotations

from typing import Protocol

import httpx

from obd.protocol.schemas import DtcReport, Sample


class Publisher(Protocol):
    async def publish_sample(self, sample: Sample) -> None: ...

    async def publish_dtcs(self, report: DtcReport) -> None: ...


class RecordingPublisher:
    """Guarda tudo em memória (testes)."""

    def __init__(self) -> None:
        self.samples: list[Sample] = []
        self.reports: list[DtcReport] = []

    async def publish_sample(self, sample: Sample) -> None:
        self.samples.append(sample)

    async def publish_dtcs(self, report: DtcReport) -> None:
        self.reports.append(report)


class HttpPublisher:
    """POST em `/api/ingest/sample` e `/api/ingest/dtc` do servidor (espera 202)."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 2.0,
    ) -> None:
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def publish_sample(self, sample: Sample) -> None:
        await self._post("/api/ingest/sample", sample.model_dump_json())

    async def publish_dtcs(self, report: DtcReport) -> None:
        await self._post("/api/ingest/dtc", report.model_dump_json())

    async def _post(self, path: str, body: str) -> None:
        resp = await self._client.post(
            path, content=body, headers={"Content-Type": "application/json"}
        )
        resp.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
