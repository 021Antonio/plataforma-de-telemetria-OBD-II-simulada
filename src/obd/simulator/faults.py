"""Catálogo de falhas (seção 6 da spec): estado configurável que a ECU consulta a cada requisição.

Puro: sem I/O e sem relógio próprio (o instante vem da ECU). A semente governa perda e corrupção.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from obd.protocol import dtc

MAX_STMIN_MS = 127


@dataclass(frozen=True)
class ScheduledDtc:
    code: str
    at: float
    pending: bool


def _probability(p: float) -> float:
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"probabilidade fora de 0..1: {p}")
    return p


class FaultInjector:
    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self._scheduled: list[ScheduledDtc] = []
        self.clear()

    def clear(self) -> None:
        """Remove todas as falhas (inclusive DTCs ainda agendados)."""
        self._scheduled = []
        self.frame_loss = 0.0
        self.corruption = 0.0
        self.mute = False
        self.unsupported: frozenset[int] = frozenset()
        self.negative: dict[int, int] = {}
        self.delay_ms: tuple[int, int] | None = None
        self.stmin_ms = 0
        self.block_size = 0

    # ---- configuração ----

    def schedule_dtc(self, code: str, at: float = 0.0, *, pending: bool = False) -> None:
        """DTC armazenado (ou pendente) a ser aplicado pela ECU a partir do instante `at`."""
        dtc.code_to_bytes(code)  # valida
        self._scheduled.append(ScheduledDtc(code, at, pending))

    def set_delay(self, ms_min: int, ms_max: int) -> None:
        if not 0 <= ms_min <= ms_max:
            raise ValueError(f"atraso inválido: ({ms_min}, {ms_max})")
        self.delay_ms = (ms_min, ms_max)

    def set_frame_loss(self, probability: float) -> None:
        self.frame_loss = _probability(probability)

    def set_corruption(self, probability: float) -> None:
        self.corruption = _probability(probability)

    def set_mute(self, on: bool) -> None:
        self.mute = on

    def set_unsupported(self, pids: set[int] | frozenset[int]) -> None:
        self.unsupported = frozenset(pids)

    def set_negative(self, mode: int, code: int | None) -> None:
        """Responde `7F modo code` a todo pedido do modo; `None` remove."""
        if code is None:
            self.negative.pop(mode, None)
        else:
            self.negative[mode] = code

    def set_isotp(self, stmin_ms: int | None = None, block_size: int | None = None) -> None:
        """Lado da ECU: separação mínima entre CFs e tamanho de bloco impostos ao emissor."""
        if stmin_ms is not None:
            if not 0 <= stmin_ms <= MAX_STMIN_MS:
                raise ValueError(f"STmin fora de 0..{MAX_STMIN_MS} ms: {stmin_ms}")
            self.stmin_ms = stmin_ms
        if block_size is not None:
            if not 0 <= block_size <= 0xFF:
                raise ValueError(f"BS fora de 0..255: {block_size}")
            self.block_size = block_size

    # ---- consulta pela ECU ----

    def pop_due_dtcs(self, now: float) -> list[ScheduledDtc]:
        due = [d for d in self._scheduled if d.at <= now]
        self._scheduled = [d for d in self._scheduled if d.at > now]
        return due

    def drops(self) -> bool:
        return self.frame_loss > 0 and self._rng.random() < self.frame_loss

    def corrupt(self, payload: bytes) -> bytes:
        """Com a probabilidade configurada, inverte um bit do eco de modo ou de PID."""
        if not payload or not (self.corruption > 0 and self._rng.random() < self.corruption):
            return payload
        index = self._rng.randrange(min(2, len(payload)))
        out = bytearray(payload)
        out[index] ^= 1 << self._rng.randrange(8)
        return bytes(out)
