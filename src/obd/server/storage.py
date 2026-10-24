"""Armazenamento do servidor: interface, SQLite (SQLAlchemy + aiosqlite) e versão em memória."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from obd.protocol.schemas import DtcEntry, DtcReport, PidValue, Sample, SampleErrors
from obd.server.models import comm_events, dtc_events, metadata, readings, runs, samples
from obd.server.stats import SampleRow

DUPLICATE = "duplicate"  # tipo de evento em `comm_events` para `seq` repetido


@dataclass(frozen=True)
class StoredSample:
    run_id: int
    sample: Sample
    ts_recv: float
    latency_ms: float


class Storage(Protocol):
    async def create_run(self, started_at: float, source: str) -> int: ...

    async def insert_sample(
        self, run_id: int, sample: Sample, ts_recv: float, latency_ms: float
    ) -> bool:
        """Grava a amostra; False (com evento `DUPLICATE`) se o `seq` já existe na execução."""
        ...

    async def insert_dtc_report(self, run_id: int, report: DtcReport, ts_recv: float) -> None: ...

    async def insert_comm_event(self, run_id: int, ts: float, kind: str, detail: str) -> None: ...

    async def latest_sample(self) -> Sample | None: ...

    async def stored_samples(
        self, since: float | None = None, limit: int | None = None
    ) -> list[StoredSample]:
        """Amostras com `ts >= since`, em ordem de `ts` (as `limit` primeiras)."""
        ...

    async def sample_rows(self, run_id: int) -> list[SampleRow]: ...

    async def count_comm_events(self, run_id: int, kind: str) -> int: ...

    async def dtc_reports(self, since: float | None = None) -> list[DtcReport]: ...


class InMemoryStorage:
    """Mesmo contrato do `SqlStorage`, em listas. Para testes."""

    def __init__(self) -> None:
        self._next_run_id = 1
        self._samples: list[StoredSample] = []
        self._seqs: set[tuple[int, int]] = set()
        self._reports: list[DtcReport] = []
        self._comm: list[tuple[int, float, str, str]] = []

    async def create_run(self, started_at: float, source: str) -> int:
        run_id = self._next_run_id
        self._next_run_id += 1
        return run_id

    async def insert_sample(
        self, run_id: int, sample: Sample, ts_recv: float, latency_ms: float
    ) -> bool:
        key = (run_id, sample.seq)
        if key in self._seqs:
            self._comm.append((run_id, ts_recv, DUPLICATE, f"seq={sample.seq}"))
            return False
        self._seqs.add(key)
        self._samples.append(StoredSample(run_id, sample, ts_recv, latency_ms))
        return True

    async def insert_dtc_report(self, run_id: int, report: DtcReport, ts_recv: float) -> None:
        self._reports.append(report)

    async def insert_comm_event(self, run_id: int, ts: float, kind: str, detail: str) -> None:
        self._comm.append((run_id, ts, kind, detail))

    async def latest_sample(self) -> Sample | None:
        return self._samples[-1].sample if self._samples else None

    async def stored_samples(
        self, since: float | None = None, limit: int | None = None
    ) -> list[StoredSample]:
        items = [s for s in self._samples if since is None or s.sample.ts >= since]
        items.sort(key=lambda s: s.sample.ts)  # estável: empates seguem a ordem de chegada
        return items if limit is None else items[:limit]

    async def sample_rows(self, run_id: int) -> list[SampleRow]:
        return [
            SampleRow(seq=s.sample.seq, ts_recv=s.ts_recv, latency_ms=s.latency_ms)
            for s in self._samples
            if s.run_id == run_id
        ]

    async def count_comm_events(self, run_id: int, kind: str) -> int:
        return sum(1 for r, _, k, _ in self._comm if r == run_id and k == kind)

    async def dtc_reports(self, since: float | None = None) -> list[DtcReport]:
        return [r for r in self._reports if since is None or r.ts >= since]


class SqlStorage:
    """Persistência em SQLite. Crie com `await SqlStorage.create(url)`."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @classmethod
    async def create(cls, url: str) -> SqlStorage:
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        return cls(engine)

    async def close(self) -> None:
        await self._engine.dispose()

    async def create_run(self, started_at: float, source: str) -> int:
        async with self._engine.begin() as conn:
            result = await conn.execute(insert(runs).values(started_at=started_at, source=source))
            pk = result.inserted_primary_key
            assert pk is not None
            return int(pk[0])

    async def insert_sample(
        self, run_id: int, sample: Sample, ts_recv: float, latency_ms: float
    ) -> bool:
        async with self._engine.begin() as conn:
            result = await conn.execute(
                sqlite_insert(samples)
                .values(
                    run_id=run_id,
                    seq=sample.seq,
                    ts_pub=sample.ts,
                    ts_recv=ts_recv,
                    latency_ms=latency_ms,
                    cycle_ms=sample.cycle_ms,
                    source=sample.source,
                    timeouts=sample.errors.timeouts,
                    invalid=sample.errors.invalid,
                )
                .on_conflict_do_nothing(index_elements=["run_id", "seq"])
            )
            if result.rowcount == 0:
                await self._log_event(conn, run_id, ts_recv, DUPLICATE, f"seq={sample.seq}")
                return False
            pk = result.inserted_primary_key
            assert pk is not None
            if sample.values:
                await conn.execute(
                    insert(readings),
                    [
                        {
                            "sample_id": pk[0],
                            "pid": pv.pid,
                            "name": name,
                            "value": pv.value,
                            "unit": pv.unit,
                            "rtt_ms": pv.rtt_ms,
                        }
                        for name, pv in sample.values.items()
                    ],
                )
            return True

    async def insert_dtc_report(self, run_id: int, report: DtcReport, ts_recv: float) -> None:
        async with self._engine.begin() as conn:
            last = await conn.execute(select(func.max(dtc_events.c.report_id)))
            report_id = (last.scalar_one() or 0) + 1
            base: dict[str, Any] = {
                "run_id": run_id,
                "report_id": report_id,
                "ts_recv": ts_recv,
                "ts": report.ts,
                "mil": report.mil,
                "count": report.count,
            }
            if report.codes:
                rows = [
                    {**base, "code": e.code, "description": e.description, "status": e.status}
                    for e in report.codes
                ]
            else:
                rows = [{**base, "code": None, "description": None, "status": None}]
            await conn.execute(insert(dtc_events), rows)

    async def insert_comm_event(self, run_id: int, ts: float, kind: str, detail: str) -> None:
        async with self._engine.begin() as conn:
            await self._log_event(conn, run_id, ts, kind, detail)

    async def _log_event(
        self, conn: AsyncConnection, run_id: int, ts: float, kind: str, detail: str
    ) -> None:
        await conn.execute(
            insert(comm_events).values(run_id=run_id, ts=ts, kind=kind, detail=detail)
        )

    async def latest_sample(self) -> Sample | None:
        found = await self._load(select(samples).order_by(samples.c.id.desc()).limit(1))
        return found[0].sample if found else None

    async def stored_samples(
        self, since: float | None = None, limit: int | None = None
    ) -> list[StoredSample]:
        query = select(samples).order_by(samples.c.ts_pub, samples.c.id)
        if since is not None:
            query = query.where(samples.c.ts_pub >= since)
        if limit is not None:
            query = query.limit(limit)
        return await self._load(query)

    async def _load(self, query: Any) -> list[StoredSample]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).mappings().all()
            if not rows:
                return []
            ids = [r["id"] for r in rows]
            rd_rows = (
                (
                    await conn.execute(
                        select(readings)
                        .where(readings.c.sample_id.in_(ids))
                        .order_by(readings.c.id)
                    )
                )
                .mappings()
                .all()
            )

        values: dict[int, dict[str, PidValue]] = {}
        for rd in rd_rows:
            values.setdefault(rd["sample_id"], {})[rd["name"]] = PidValue(
                pid=rd["pid"], value=rd["value"], unit=rd["unit"], rtt_ms=rd["rtt_ms"]
            )

        return [
            StoredSample(
                run_id=r["run_id"],
                ts_recv=r["ts_recv"],
                latency_ms=r["latency_ms"],
                sample=Sample(
                    seq=r["seq"],
                    ts=r["ts_pub"],
                    cycle_ms=r["cycle_ms"],
                    source=r["source"],
                    values=values.get(r["id"], {}),
                    errors=SampleErrors(timeouts=r["timeouts"], invalid=r["invalid"]),
                ),
            )
            for r in rows
        ]

    async def sample_rows(self, run_id: int) -> list[SampleRow]:
        async with self._engine.connect() as conn:
            rows = (
                await conn.execute(
                    select(samples.c.seq, samples.c.ts_recv, samples.c.latency_ms).where(
                        samples.c.run_id == run_id
                    )
                )
            ).all()
        return [SampleRow(seq=s, ts_recv=t, latency_ms=lat) for s, t, lat in rows]

    async def count_comm_events(self, run_id: int, kind: str) -> int:
        async with self._engine.connect() as conn:
            total = await conn.execute(
                select(func.count())
                .select_from(comm_events)
                .where(comm_events.c.run_id == run_id, comm_events.c.kind == kind)
            )
            return int(total.scalar_one())

    async def dtc_reports(self, since: float | None = None) -> list[DtcReport]:
        query = select(dtc_events).order_by(dtc_events.c.report_id, dtc_events.c.id)
        if since is not None:
            query = query.where(dtc_events.c.ts >= since)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).mappings().all()

        groups: dict[int, list[Any]] = {}
        for row in rows:
            groups.setdefault(row["report_id"], []).append(row)
        return [
            DtcReport(
                ts=group[0]["ts"],
                mil=group[0]["mil"],
                count=group[0]["count"],
                codes=[
                    DtcEntry(code=r["code"], description=r["description"], status=r["status"])
                    for r in group
                    if r["code"] is not None
                ],
            )
            for group in groups.values()
        ]
