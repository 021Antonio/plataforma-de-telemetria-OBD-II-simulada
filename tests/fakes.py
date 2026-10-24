"""Dublês de teste."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterable, Mapping

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


class FakeBrokerLink:
    """Cliente do `FakeBroker`: mesma interface de `MqttLink`."""

    def __init__(self, broker: FakeBroker) -> None:
        self._broker = broker
        self._queue: asyncio.Queue[tuple[str, bytes] | None] = asyncio.Queue()
        self._patterns: list[str] = []
        self.connected = False

    async def connect(self) -> None:
        if not self._broker.up:
            raise ConnectionError("broker fora do ar")
        self.connected = True
        self._broker.links.append(self)

    async def close(self) -> None:
        self.connected = False
        if self in self._broker.links:
            self._broker.links.remove(self)

    async def publish(self, topic: str, payload: bytes, qos: int) -> None:
        if not self.connected or not self._broker.up:
            raise ConnectionError("sem conexão com o broker")
        self._broker.published.append((topic, payload, qos))
        for link in self._broker.links:
            if any(_topic_matches(p, topic) for p in link._patterns):
                link._queue.put_nowait((topic, payload))

    async def subscribe(self, topics: Iterable[tuple[str, int]]) -> None:
        if not self.connected:
            raise ConnectionError("sem conexão com o broker")
        self._patterns.extend(topic for topic, _ in topics)

    async def messages(self) -> AsyncIterator[tuple[str, bytes]]:
        while True:
            item = await self._queue.get()
            if item is None:
                raise ConnectionError("conexão derrubada")
            yield item


def _topic_matches(pattern: str, topic: str) -> bool:
    p, t = pattern.split("/"), topic.split("/")
    return len(p) == len(t) and all(a in ("+", b) for a, b in zip(p, t, strict=True))


class FakeBroker:
    """Broker MQTT em memória: roteia por tópico (`+`) e simula queda e volta."""

    def __init__(self) -> None:
        self.up = True
        self.links: list[FakeBrokerLink] = []
        self.published: list[tuple[str, bytes, int]] = []

    def link(self) -> FakeBrokerLink:
        return FakeBrokerLink(self)

    def go_down(self) -> None:
        """Derruba todas as conexões; novas conexões falham até `come_back`."""
        self.up = False
        for link in list(self.links):
            link.connected = False
            link._queue.put_nowait(None)
        self.links.clear()

    def come_back(self) -> None:
        self.up = True
