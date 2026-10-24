"""Contrato dos transportes: enviam uma requisição OBD e devolvem a resposta remontada."""

from __future__ import annotations

from typing import Protocol


class Transport(Protocol):
    async def open(self) -> None: ...

    async def close(self) -> None: ...

    async def request(self, payload: bytes, timeout_ms: int = 100) -> bytes | None:
        """Envia uma requisição OBD (ex.: `01 0C`) e devolve a resposta completa já remontada
        pelo ISO-TP. `None` se estourar o tempo."""
        ...

    @property
    def name(self) -> str: ...
