"""Transporte em memória: liga o coletor direto a uma ECU, sem barramento (para testes)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Protocol

from obd.protocol.frames import CanFrame
from obd.transport.isotp_client import POLL_INTERVAL, Sleep, exchange


class FrameBus(Protocol):
    """O que o loopback precisa do outro lado: uma `Ecu` ou o `Simulator` (que a envolve)."""

    def on_frame(self, can_id: int, data: bytes) -> None: ...

    def poll(self) -> list[CanFrame]: ...


class LoopbackTransport:
    def __init__(
        self,
        ecu: FrameBus,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Sleep = asyncio.sleep,
        bs: int = 0,
        stmin: int = 0,
        interval: float = POLL_INTERVAL,
    ) -> None:
        self._ecu = ecu
        self._clock = clock
        self._sleep = sleep
        self._bs = bs
        self._stmin = stmin
        self._interval = interval
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "loopback"

    async def open(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def _recv(self) -> list[CanFrame]:
        return self._ecu.poll()

    async def request(self, payload: bytes, timeout_ms: int = 100) -> bytes | None:
        async with self._lock:
            return await exchange(
                payload,
                timeout_ms,
                send=self._ecu.on_frame,
                recv=self._recv,
                clock=self._clock,
                sleep=self._sleep,
                block_size=self._bs,
                stmin=self._stmin,
                interval=self._interval,
            )
