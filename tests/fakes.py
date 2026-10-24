"""Dublês de teste."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from obd.protocol.schemas import PidValue, Sample, SampleErrors


class FakeClock:
    """Relógio injetável em segundos, avançado manualmente."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    async def sleep(self, seconds: float) -> None:
        """Substitui `asyncio.sleep`: só avança o relógio."""
        self.advance(seconds)


class FakeVehicleModel:
    """Valores físicos constantes ou em rampa (`inicio + inclinacao * clock()`), por PID."""

    def __init__(
        self,
        values: Mapping[int, float],
        clock: Callable[[], float] | None = None,
        slopes: Mapping[int, float] | None = None,
    ) -> None:
        self._values = dict(values)
        self._slopes = dict(slopes or {})
        self._clock = clock or (lambda: 0.0)

    def value(self, pid: int) -> float:
        return self._values[pid] + self._slopes.get(pid, 0.0) * self._clock()

    def pids(self) -> frozenset[int]:
        return frozenset(self._values)


def make_sample(
    seq: int,
    ts: float,
    *,
    values: Mapping[str, PidValue] | None = None,
    cycle_ms: float = 100.0,
    source: str = "can_virtual",
    timeouts: int = 0,
    invalid: int = 0,
) -> Sample:
    """Amostra válida do coletor (padrão: só RPM)."""
    default = {"rpm": PidValue(pid="0x0C", value=2000.0, unit="rpm", rtt_ms=11.0)}
    return Sample(
        seq=seq,
        ts=ts,
        cycle_ms=cycle_ms,
        source=source,
        values=dict(default if values is None else values),
        errors=SampleErrors(timeouts=timeouts, invalid=invalid),
    )


class ScriptedTransport:
    """Responde a uma tabela fixa requisição -> resposta; o resto vira timeout (None)."""

    def __init__(self, script: Mapping[bytes, bytes | None]) -> None:
        self._script = dict(script)
        self.calls: list[bytes] = []
        self.is_open = False

    @property
    def name(self) -> str:
        return "scripted"

    async def open(self) -> None:
        self.is_open = True

    async def close(self) -> None:
        self.is_open = False

    async def request(self, payload: bytes, timeout_ms: int = 100) -> bytes | None:
        self.calls.append(payload)
        return self._script.get(payload)
