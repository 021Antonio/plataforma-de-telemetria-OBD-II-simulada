"""Estado compartilhado do servidor: armazenamento, relógio, execução e difusão."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from obd.server.storage import Storage


class Broadcaster:
    """Uma fila por cliente WebSocket. Filas sem limite: cliente lento acumula memória."""

    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._queues.discard(queue)

    def publish(self, message: dict[str, Any]) -> None:
        for queue in self._queues:
            queue.put_nowait(message)


@dataclass
class ServerState:
    storage: Storage
    clock: Callable[[], float]
    hub: Broadcaster = field(default_factory=Broadcaster)
    run_id: int | None = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def current_run(self, source: str) -> int:
        """Execução da aplicação: criada na primeira gravação, com a fonte da primeira amostra."""
        if self.run_id is None:
            async with self._lock:
                if self.run_id is None:
                    self.run_id = await self.storage.create_run(self.clock(), source)
        return self.run_id
