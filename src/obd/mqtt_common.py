"""Peças comuns do canal MQTT: tópicos, recuo de reconexão e o adaptador do `aiomqtt`."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator, Callable, Iterable
from typing import Protocol

BACKOFF_FIRST_S = 1.0
BACKOFF_MAX_S = 30.0
QOS_DATA = 0
QOS_DTC = 1


def topic_data(vehicle: str) -> str:
    return f"telemetria/{vehicle}/dados"


def topic_dtc(vehicle: str) -> str:
    return f"telemetria/{vehicle}/dtc"


def next_delay(delay: float | None) -> float:
    """Recuo exponencial: 1, 2, 4, ... até 30 s. `None` começa a sequência."""
    if delay is None:
        return BACKOFF_FIRST_S
    return min(delay * 2, BACKOFF_MAX_S)


class MqttLink(Protocol):
    """Conexão com o broker. Erros de rede chegam como `ConnectionError`."""

    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def publish(self, topic: str, payload: bytes, qos: int) -> None: ...

    async def subscribe(self, topics: Iterable[tuple[str, int]]) -> None: ...

    def messages(self) -> AsyncIterator[tuple[str, bytes]]: ...


LinkFactory = Callable[[], MqttLink]


class AiomqttLink:
    """Adaptador do `aiomqtt.Client` para `MqttLink`."""

    def __init__(self, host: str = "localhost", port: int = 1883, client_id: str | None = None):
        import aiomqtt

        self._aiomqtt = aiomqtt
        self._client = aiomqtt.Client(hostname=host, port=port, identifier=client_id)

    async def connect(self) -> None:
        try:
            await self._client.__aenter__()
        except self._aiomqtt.MqttError as exc:
            raise ConnectionError(str(exc)) from exc

    async def close(self) -> None:
        with contextlib.suppress(self._aiomqtt.MqttError):
            await self._client.__aexit__(None, None, None)

    async def publish(self, topic: str, payload: bytes, qos: int) -> None:
        try:
            await self._client.publish(topic, payload, qos=qos)
        except self._aiomqtt.MqttError as exc:
            raise ConnectionError(str(exc)) from exc

    async def subscribe(self, topics: Iterable[tuple[str, int]]) -> None:
        try:
            for topic, qos in topics:
                await self._client.subscribe(topic, qos=qos)
        except self._aiomqtt.MqttError as exc:
            raise ConnectionError(str(exc)) from exc

    async def messages(self) -> AsyncIterator[tuple[str, bytes]]:
        try:
            async for msg in self._client.messages:
                payload = msg.payload
                yield (
                    str(msg.topic),
                    bytes(payload) if isinstance(payload, bytes | bytearray) else b"",
                )
        except self._aiomqtt.MqttError as exc:
            raise ConnectionError(str(exc)) from exc
