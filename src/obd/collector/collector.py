"""Coletor: descobre PIDs, executa o plano de leitura, valida, decodifica e publica."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from obd.collector.publisher import Publisher
from obd.collector.scheduler import BackoffConfig, CollectorConfig, PidRate, Scheduler
from obd.protocol import dtc
from obd.protocol.errors import ProtocolError
from obd.protocol.pids import (
    MONITOR_STATUS_PID,
    PIDS,
    SUPPORT_PIDS,
    MonitorStatus,
    decode_monitor_status,
    decode_supported,
)
from obd.protocol.schemas import DtcEntry, DtcReport, PidValue, Sample, SampleErrors
from obd.protocol.services import MODE_CURRENT, MODE_STORED_DTC, build_request, parse_response
from obd.transport.base import Transport

Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class CollectorEvent:
    ts: float
    kind: str  # timeout | invalid | backoff | publish_failed | discovery_failed
    detail: str


class Collector:
    def __init__(
        self,
        transport: Transport,
        publisher: Publisher,
        *,
        rates: Mapping[int, PidRate] | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        sleep: Sleep = asyncio.sleep,
        timeout_ms: int = 100,
        dtc_interval_s: float = 2.0,
        backoff: BackoffConfig | None = None,
        source: str | None = None,
    ) -> None:
        if rates is None:
            rates = CollectorConfig.from_yaml().plan or {}
        self._transport = transport
        self._publisher = publisher
        self._rates = dict(rates)
        self._clock = clock
        self._wall = wall_clock
        self._sleep = sleep
        self._timeout_ms = timeout_ms
        self._dtc_interval = dtc_interval_s
        self._backoff = backoff or BackoffConfig()
        self._source = source or transport.name
        self._scheduler = Scheduler(self._rates, frozenset())
        self._cycle = 0
        self._seq = 0
        self._last_dtc_check: float | None = None
        self._last_status: MonitorStatus | None = None
        self.supported: frozenset[int] = frozenset()
        self.consecutive_failures = 0
        self.events: list[CollectorEvent] = []
        self._discovered = False
        self._last_failure = ""
        self._last_rtt_ms = 0.0

    async def start(self) -> None:
        await self._transport.open()
        await self.discover()

    async def close(self) -> None:
        await self._transport.close()

    async def discover(self) -> bool:
        """Consulta 0x00, 0x20 e 0x40 (seguindo o bit de continuação) e monta o plano."""
        found: set[int] = set()
        for base in SUPPORT_PIDS:
            if base != SUPPORT_PIDS[0] and base not in found:
                break  # sem bit de continuação
            data = await self._request(build_request(MODE_CURRENT, base))
            if data is None:
                break
            found |= decode_supported(base, data)
        self._discovered = bool(found)
        if not self._discovered:
            self._event("discovery_failed", "nenhum PID suportado anunciado")
        self.supported = frozenset(found)
        self._scheduler = Scheduler(self._rates, self.supported & PIDS.keys())
        return self._discovered

    async def run_cycle(self) -> Sample:
        if not self._discovered:
            await self.discover()
        t0 = self._clock()
        values: dict[str, PidValue] = {}
        timeouts = invalid = 0
        for pid in self._scheduler.for_cycle(self._cycle):
            req = build_request(MODE_CURRENT, pid)
            data = await self._request(req)
            if data is None:
                if self._last_failure == "timeout":
                    timeouts += 1
                else:
                    invalid += 1
                continue
            pid_def = PIDS[pid]
            try:
                value = pid_def.decode(data)
            except ProtocolError as exc:
                self._fail("invalid", f"PID 0x{pid:02X}: {exc}")
                invalid += 1
                continue
            values[pid_def.name] = PidValue(
                pid=f"0x{pid:02X}", value=value, unit=pid_def.unit, rtt_ms=self._last_rtt_ms
            )
        cycle_ms = (self._clock() - t0) * 1000
        self._cycle += 1
        sample = Sample(
            seq=self._seq,
            ts=self._wall(),
            cycle_ms=cycle_ms,
            source=self._source,
            values=values,
            errors=SampleErrors(timeouts=timeouts, invalid=invalid),
        )
        self._seq += 1
        await self._publish(self._publisher.publish_sample(sample))
        await self._check_dtcs()
        return sample

    async def run(self, max_cycles: int | None = None, interval_s: float = 0.1) -> None:
        n = 0
        while max_cycles is None or n < max_cycles:
            t0 = self._clock()
            await self.run_cycle()
            n += 1
            rest = interval_s - (self._clock() - t0)
            if rest > 0:
                await self._sleep(rest)

    # -- internos -------------------------------------------------------------------------

    def _event(self, kind: str, detail: str) -> None:
        self.events.append(CollectorEvent(self._wall(), kind, detail))

    def _fail(self, kind: str, detail: str) -> None:
        self.consecutive_failures += 1
        self._last_failure = kind
        self._event(kind, detail)

    async def _request(self, req: bytes) -> bytes | None:
        """Envia, valida eco de modo/PID e devolve os dados do PID; None em falha (registrada)."""
        delay = self._backoff.delay(self.consecutive_failures)
        if delay > 0:
            self._event("backoff", f"{self.consecutive_failures} falhas seguidas; {delay:.3f} s")
            await self._sleep(delay)
        start = self._clock()
        raw = await self._transport.request(req, timeout_ms=self._timeout_ms)
        self._last_rtt_ms = (self._clock() - start) * 1000
        if raw is None:
            self._fail("timeout", req.hex())
            return None
        try:
            resp = parse_response(raw, req)
        except ProtocolError as exc:
            self._fail("invalid", f"{req.hex()}: {exc}")
            return None
        if resp.is_negative:
            self._fail("invalid", f"{req.hex()}: resposta negativa 0x{resp.error_code or 0:02X}")
            return None
        self.consecutive_failures = 0
        return resp.data

    async def _publish(self, coro: Awaitable[None]) -> None:
        try:
            await coro
        except Exception as exc:  # o servidor pode estar fora; a coleta continua
            self._event("publish_failed", repr(exc))

    async def _check_dtcs(self) -> None:
        now = self._clock()
        if self._last_dtc_check is not None and now - self._last_dtc_check < self._dtc_interval:
            return
        self._last_dtc_check = now
        data = await self._request(build_request(MODE_CURRENT, MONITOR_STATUS_PID))
        if data is None:
            return
        try:
            status = decode_monitor_status(data)
        except ProtocolError as exc:
            self._fail("invalid", f"PID 0x01: {exc}")
            return
        if status == self._last_status:
            return
        raw = await self._transport.request(build_request(MODE_STORED_DTC), self._timeout_ms)
        if raw is None:
            self._fail("timeout", "03")
            return
        try:
            resp = parse_response(raw, build_request(MODE_STORED_DTC))
        except ProtocolError as exc:
            self._fail("invalid", f"03: {exc}")
            return
        self._last_status = status
        report = DtcReport(
            ts=self._wall(),
            mil=status.mil,
            count=len(resp.dtcs),
            codes=[DtcEntry(code=c, description=dtc.describe(c)) for c in resp.dtcs],
        )
        await self._publish(self._publisher.publish_dtcs(report))
