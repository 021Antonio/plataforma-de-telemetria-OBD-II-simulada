"""Tabela de PIDs do Modo 01 com codificação e decodificação (seção 4 da spec)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from obd.protocol.errors import ProtocolError

SUPPORT_PIDS = (0x00, 0x20, 0x40)
MONITOR_STATUS_PID = 0x01


@dataclass(frozen=True)
class PidDef:
    pid: int
    name: str
    unit: str
    n_bytes: int
    resolution: float
    min_value: float
    max_value: float
    decode: Callable[[bytes], float]
    encode: Callable[[float], bytes]  # usado pela ECU simulada


def _raw(value: float, scale: float, offset: float, n_bytes: int) -> bytes:
    """Inverte `fisico = bruto * scale + offset`, saturando na faixa do campo."""
    top = (1 << (8 * n_bytes)) - 1
    raw = round((value - offset) / scale)
    return max(0, min(top, raw)).to_bytes(n_bytes, "big")


def _linear(
    pid: int,
    name: str,
    unit: str,
    n_bytes: int,
    scale: float,
    offset: float = 0.0,
) -> PidDef:
    """PID cuja fórmula é `bruto * scale + offset` (bruto big-endian)."""
    top = (1 << (8 * n_bytes)) - 1

    def decode(data: bytes) -> float:
        if len(data) != n_bytes:
            raise ProtocolError(f"PID 0x{pid:02X} espera {n_bytes} byte(s), recebeu {len(data)}")
        return int.from_bytes(data, "big") * scale + offset

    def encode(value: float) -> bytes:
        return _raw(value, scale, offset, n_bytes)

    return PidDef(pid, name, unit, n_bytes, scale, offset, top * scale + offset, decode, encode)


# A resolução usa o passo exato (ex.: 100/255), não o valor arredondado da spec,
# para que o erro de ida e volta seja de fato <= resolução / 2.
PIDS: dict[int, PidDef] = {
    p.pid: p
    for p in (
        _linear(0x04, "load", "%", 1, 100 / 255),
        _linear(0x05, "coolant", "C", 1, 1.0, -40.0),
        _linear(0x06, "short_fuel_trim", "%", 1, 100 / 128, -100.0),
        _linear(0x0B, "map", "kPa", 1, 1.0),
        _linear(0x0C, "rpm", "rpm", 2, 0.25),
        _linear(0x0D, "speed", "km/h", 1, 1.0),
        _linear(0x0F, "intake_temp", "C", 1, 1.0, -40.0),
        _linear(0x11, "throttle", "%", 1, 100 / 255),
        _linear(0x2F, "fuel_level", "%", 1, 100 / 255),
        _linear(0x42, "voltage", "V", 2, 0.001),
    )
}


def get_pid(pid: int) -> PidDef:
    try:
        return PIDS[pid]
    except KeyError:
        raise ProtocolError(f"PID 0x{pid:02X} não implementado") from None


def encode_supported(base: int, pids: Iterable[int]) -> bytes:
    """Máscara de 32 bits do PID `base` (0x00, 0x20 ou 0x40); bit 31 = base + 1."""
    if base not in SUPPORT_PIDS:
        raise ProtocolError(f"PID de suporte inválido: 0x{base:02X}")
    mask = 0
    for pid in pids:
        offset = pid - base
        if 1 <= offset <= 32:
            mask |= 1 << (32 - offset)
    return mask.to_bytes(4, "big")


def decode_supported(base: int, data: bytes) -> frozenset[int]:
    """PIDs anunciados pela máscara de `base`. O bit de continuação (base + 0x20) é incluído."""
    if base not in SUPPORT_PIDS:
        raise ProtocolError(f"PID de suporte inválido: 0x{base:02X}")
    if len(data) != 4:
        raise ProtocolError(f"máscara de suporte exige 4 bytes, recebeu {len(data)}")
    mask = int.from_bytes(data, "big")
    return frozenset(base + off for off in range(1, 33) if mask & (1 << (32 - off)))


@dataclass(frozen=True)
class MonitorStatus:
    mil: bool
    dtc_count: int


def decode_monitor_status(data: bytes) -> MonitorStatus:
    """PID 0x01: A bit 7 = MIL, bits 0 a 6 = número de DTCs."""
    if len(data) != 4:
        raise ProtocolError(f"PID 0x01 exige 4 bytes, recebeu {len(data)}")
    return MonitorStatus(mil=bool(data[0] & 0x80), dtc_count=data[0] & 0x7F)


def encode_monitor_status(mil: bool, dtc_count: int) -> bytes:
    if not 0 <= dtc_count <= 0x7F:
        raise ProtocolError(f"contagem de DTCs fora de 0..127: {dtc_count}")
    return bytes([(0x80 if mil else 0) | dtc_count, 0x00, 0x00, 0x00])
