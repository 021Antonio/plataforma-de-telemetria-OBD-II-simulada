"""Publicador MQTT: mesmo JSON do HTTP, `dados` em QoS 0 e `dtc` em QoS 1."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

from obd.mqtt_common import (
    QOS_DATA,
    QOS_DTC,
    LinkFactory,
    MqttLink,
    next_delay,
    topic_data,
    topic_dtc,
)
from obd.protocol.schemas import DtcReport, Sample

log = logging.getLogger(__name__)


class MqttPublisher:
    """Reconecta com recuo exponencial e reenvia a mensagem pendente: a ordem de `seq` se mantém.

    Enquanto o broker estiver fora, `publish_*` não retorna (o coletor espera, sem pular `seq`).
    """

    def __init__(
        self,
        link_factory: LinkFactory,
        vehicle: str = "simulado",
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._factory = link_factory
        self._vehicle = vehicle
        self._sleep = sleep
        self._link: MqttLink | None = None
        self._lock = asyncio.Lock()
        self.reconnects = 0

    async def publish_sample(self, sample: Sample) -> None:
        await self._send(topic_data(self._vehicle), sample.model_dump_json().encode(), QOS_DATA)

    async def publish_dtcs(self, report: DtcReport) -> None:
        await self._send(topic_dtc(self._vehicle), report.model_dump_json().encode(), QOS_DTC)

    async def _send(self, topic: str, payload: bytes, qos: int) -> None:
        async with self._lock:
            delay: float | None = None
            while True:
                try:
                    if self._link is None:
                        link = self._factory()
                        await link.connect()
                        self._link = link
                    await self._link.publish(topic, payload, qos)
                    return
                except (ConnectionError, OSError) as exc:
                    await self._drop_link()
                    delay = next_delay(delay)
                    self.reconnects += 1
                    log.warning("mqtt: falha (%s); nova tentativa em %.0f s", exc, delay)
                    await self._sleep(delay)

    async def _drop_link(self) -> None:
        link, self._link = self._link, None
        if link is not None:
            with contextlib.suppress(ConnectionError, OSError):
                await link.close()

    async def aclose(self) -> None:
        await self._drop_link()
