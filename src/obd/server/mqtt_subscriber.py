"""Assinante MQTT: valida com os schemas e grava como o `POST /api/ingest/*`."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

from pydantic import ValidationError

from obd.mqtt_common import (
    QOS_DATA,
    QOS_DTC,
    LinkFactory,
    next_delay,
    topic_data,
    topic_dtc,
)
from obd.protocol.schemas import DtcReport, Sample
from obd.server.state import ServerState

log = logging.getLogger(__name__)


class MqttSubscriber:
    def __init__(
        self,
        link_factory: LinkFactory,
        state: ServerState,
        vehicle: str = "+",
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._factory = link_factory
        self._state = state
        self._data = topic_data(vehicle)
        self._dtc = topic_dtc(vehicle)
        self._sleep = sleep
        self._task: asyncio.Task[None] | None = None
        self.rejected = 0
        self.reconnects = 0

    async def handle(self, topic: str, payload: bytes) -> None:
        try:
            if topic.endswith("/dados"):
                await self._state.ingest_sample(Sample.model_validate_json(payload))
            elif topic.endswith("/dtc"):
                await self._state.ingest_dtc(DtcReport.model_validate_json(payload))
            else:
                self.rejected += 1
        except ValidationError as exc:
            self.rejected += 1
            log.warning("mqtt: mensagem inválida em %s: %s", topic, exc.error_count())

    async def run(self) -> None:
        """Assina e grava até ser cancelado; reconecta com recuo se o broker cair."""
        delay: float | None = None
        while True:
            link = self._factory()
            try:
                await link.connect()
                await link.subscribe([(self._data, QOS_DATA), (self._dtc, QOS_DTC)])
                delay = None
                async for topic, payload in link.messages():
                    await self.handle(topic, payload)
                raise ConnectionError("fluxo de mensagens encerrado")
            except (ConnectionError, OSError) as exc:
                delay = next_delay(delay)
                self.reconnects += 1
                log.warning(
                    "mqtt: assinante desconectado (%s); nova tentativa em %.0f s", exc, delay
                )
            finally:
                with contextlib.suppress(ConnectionError, OSError):
                    await link.close()
            await self._sleep(delay)

    def start(self) -> None:
        self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
