"""Transporte sobre python-can com `interface="virtual"`: envia em 0x7DF, escuta 0x7E8."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

import can

from obd.protocol.errors import ProtocolError
from obd.protocol.frames import FRAME_SIZE, ID_ENGINE_RESPONSE, CanFrame
from obd.transport.isotp_client import POLL_INTERVAL, Sleep, exchange


class CanVirtualTransport:
    def __init__(
        self,
        channel: str = "obd",
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Sleep = asyncio.sleep,
        bs: int = 0,
        stmin: int = 0,
        interval: float = POLL_INTERVAL,
    ) -> None:
        self._channel = channel
        self._clock = clock
        self._sleep = sleep
        self._bs = bs
        self._stmin = stmin
        self._interval = interval
        self._bus: can.BusABC | None = None
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "can_virtual"

    async def open(self) -> None:
        if self._bus is None:
            self._bus = can.Bus(
                interface="virtual", channel=self._channel, receive_own_messages=False
            )

    async def close(self) -> None:
        if self._bus is not None:
            self._bus.shutdown()
            self._bus = None

    def _require_bus(self) -> can.BusABC:
        if self._bus is None:
            raise ProtocolError("transporte CAN virtual não está aberto")
        return self._bus

    def _send(self, can_id: int, data: bytes) -> None:
        self._require_bus().send(
            can.Message(arbitration_id=can_id, data=data, is_extended_id=False)
        )

    def _recv(self) -> list[CanFrame]:
        bus = self._require_bus()
        out: list[CanFrame] = []
        while (msg := bus.recv(0)) is not None:
            if (
                msg.arbitration_id == ID_ENGINE_RESPONSE
                and not msg.is_extended_id
                and len(msg.data) == FRAME_SIZE
            ):
                out.append(CanFrame(msg.arbitration_id, bytes(msg.data)))
        return out

    async def request(self, payload: bytes, timeout_ms: int = 100) -> bytes | None:
        async with self._lock:
            self._recv()  # descarta o que sobrou de uma resposta atrasada
            return await exchange(
                payload,
                timeout_ms,
                send=self._send,
                recv=self._recv,
                clock=self._clock,
                sleep=self._sleep,
                block_size=self._bs,
                stmin=self._stmin,
                interval=self._interval,
            )
