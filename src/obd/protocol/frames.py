"""Quadros CAN de 11 bits para OBD-II (ISO 15765-4)."""

from __future__ import annotations

from dataclasses import dataclass

from obd.protocol.errors import ProtocolError

PAD_BYTE = 0x55
FRAME_SIZE = 8
ID_FUNCTIONAL = 0x7DF
ID_PHYSICAL_REQUEST = range(0x7E0, 0x7E8)
ID_ENGINE_RESPONSE = 0x7E8


def is_valid_id(can_id: int) -> bool:
    return can_id in (ID_FUNCTIONAL, ID_ENGINE_RESPONSE) or can_id in ID_PHYSICAL_REQUEST


@dataclass(frozen=True)
class CanFrame:
    can_id: int
    data: bytes  # sempre 8 bytes, já preenchidos

    def __post_init__(self) -> None:
        if not is_valid_id(self.can_id):
            raise ProtocolError(f"identificador CAN inválido: 0x{self.can_id:X}")
        if len(self.data) != FRAME_SIZE:
            raise ProtocolError(f"DLC inválido: {len(self.data)} (esperado {FRAME_SIZE})")


def pad(data: bytes) -> bytes:
    """Completa até 8 bytes com 0x55."""
    if len(data) > FRAME_SIZE:
        raise ProtocolError(f"DLC inválido: {len(data)} > {FRAME_SIZE}")
    return data + bytes([PAD_BYTE]) * (FRAME_SIZE - len(data))


def build_frame(can_id: int, data: bytes) -> CanFrame:
    return CanFrame(can_id, pad(data))


def frame_bits(s: int) -> int:
    """Pior caso de bits de um quadro de `s` bytes: C = 47 + 8s + floor((34 + 8s - 1) / 4)."""
    if not 0 <= s <= FRAME_SIZE:
        raise ProtocolError(f"DLC inválido: {s}")
    return 47 + 8 * s + (34 + 8 * s - 1) // 4


def frame_time_us(s: int = FRAME_SIZE, bitrate: int = 500_000) -> float:
    return frame_bits(s) * 1_000_000 / bitrate
