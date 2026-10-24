"""Dublês de teste."""

from __future__ import annotations


class FakeClock:
    """Relógio injetável em segundos, avançado manualmente."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds
