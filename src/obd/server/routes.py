"""Rotas HTTP do servidor (docs/spec/05-api.md)."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, HTTPException, Query, Response

from obd.protocol.schemas import DtcReport, Sample, Stats
from obd.server.state import ServerState
from obd.server.stats import compute_stats
from obd.server.storage import DUPLICATE, StoredSample

DEFAULT_HISTORY_LIMIT = 1000
MAX_HISTORY_LIMIT = 10_000
CSV_HEADER = [
    "seq",
    "ts_pub",
    "ts_recv",
    "latency_ms",
    "cycle_ms",
    "source",
    "timeouts",
    "invalid",
    "name",
    "pid",
    "value",
    "unit",
    "rtt_ms",
    "true_value",
]


def _csv(stored: list[StoredSample]) -> str:
    """Uma linha por leitura; amostra sem leituras ocupa uma linha com campos vazios."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER)
    for item in stored:
        s = item.sample
        base = [
            s.seq,
            s.ts,
            item.ts_recv,
            item.latency_ms,
            s.cycle_ms,
            s.source,
            s.errors.timeouts,
            s.errors.invalid,
        ]
        if not s.values:
            writer.writerow(base + [""] * 6)
        for name, pv in s.values.items():
            writer.writerow(base + [name, pv.pid, pv.value, pv.unit, pv.rtt_ms, ""])
    return buf.getvalue()


def build_router(state: ServerState) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/api/ingest/sample", status_code=202)
    async def ingest_sample(sample: Sample) -> Response:
        await state.ingest_sample(sample)
        return Response(status_code=202)

    @router.post("/api/ingest/dtc", status_code=202)
    async def ingest_dtc(report: DtcReport) -> Response:
        await state.ingest_dtc(report)
        return Response(status_code=202)

    @router.get("/api/latest", response_model=Sample)
    async def latest() -> Sample:
        sample = await state.storage.latest_sample()
        if sample is None:
            raise HTTPException(status_code=404, detail="nenhuma amostra recebida")
        return sample

    @router.get("/api/history", response_model=list[Sample])
    async def history(
        since: float | None = None,
        limit: int = Query(DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
    ) -> list[Sample]:
        stored = await state.storage.stored_samples(since=since, limit=limit)
        return [item.sample for item in stored]

    @router.get("/api/dtc", response_model=list[DtcReport])
    async def dtc() -> list[DtcReport]:
        """Histórico de relatórios; o último traz os DTCs ativos."""
        return await state.storage.dtc_reports()

    @router.get("/api/stats", response_model=Stats)
    async def stats() -> Stats:
        now = state.clock()
        if state.run_id is None:
            return compute_stats([], duplicated=0, now=now)
        rows = await state.storage.sample_rows(state.run_id)
        duplicated = await state.storage.count_comm_events(state.run_id, DUPLICATE)
        return compute_stats(rows, duplicated=duplicated, now=now)

    @router.get("/api/export.csv")
    async def export_csv(since: float | None = None) -> Response:
        stored = await state.storage.stored_samples(since=since)
        return Response(content=_csv(stored), media_type="text/csv")

    return router
