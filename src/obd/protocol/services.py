"""Requisições e respostas dos Modos 01, 03, 04 e 07 (quadro único, sem ISO-TP)."""

from __future__ import annotations

from dataclasses import dataclass

from obd.protocol import dtc
from obd.protocol.errors import ProtocolError
from obd.protocol.pids import PIDS

MODE_CURRENT = 0x01
MODE_STORED_DTC = 0x03
MODE_CLEAR_DTC = 0x04
MODE_PENDING_DTC = 0x07
NEGATIVE = 0x7F
SUPPORTED_MODES = (MODE_CURRENT, MODE_STORED_DTC, MODE_CLEAR_DTC, MODE_PENDING_DTC)
_DTC_MODES = (MODE_STORED_DTC, MODE_PENDING_DTC)


@dataclass(frozen=True)
class Response:
    mode: int  # modo da requisição (sem o 0x40); em resposta negativa, o modo rejeitado
    pid: int | None = None
    data: bytes = b""  # Modo 01: bytes do PID
    dtcs: tuple[str, ...] = ()  # Modos 03 e 07
    error_code: int | None = None  # resposta negativa (7F)

    @property
    def is_negative(self) -> bool:
        return self.error_code is not None


def build_request(mode: int, pid: int | None = None) -> bytes:
    if mode not in SUPPORTED_MODES:
        raise ProtocolError(f"modo não suportado: 0x{mode:02X}")
    if mode == MODE_CURRENT:
        if pid is None or not 0 <= pid <= 0xFF:
            raise ProtocolError("Modo 01 exige um PID de 0x00 a 0xFF")
        return bytes([mode, pid])
    if pid is not None:
        raise ProtocolError(f"Modo 0x{mode:02X} não aceita PID")
    return bytes([mode])


def parse_response(raw: bytes, request: bytes | None = None) -> Response:
    """Interpreta a resposta. Com `request`, valida eco de modo+0x40 e do PID."""
    if not raw:
        raise ProtocolError("resposta vazia")
    if raw[0] == NEGATIVE:
        return _parse_negative(raw, request)
    mode = raw[0] - 0x40
    if mode not in SUPPORTED_MODES:
        raise ProtocolError(f"modo de resposta inesperado: 0x{raw[0]:02X}")
    if request and raw[0] != request[0] + 0x40:
        raise ProtocolError(f"resposta 0x{raw[0]:02X} não corresponde ao modo 0x{request[0]:02X}")
    if mode == MODE_CURRENT:
        return _parse_current(raw, request)
    if mode in _DTC_MODES:
        return _parse_dtcs(mode, raw)
    if len(raw) != 1:
        raise ProtocolError("resposta do Modo 04 deve ter 1 byte")
    return Response(mode)


def _parse_negative(raw: bytes, request: bytes | None) -> Response:
    if len(raw) != 3:
        raise ProtocolError(f"resposta negativa exige 3 bytes, recebeu {len(raw)}")
    if request and raw[1] != request[0]:
        raise ProtocolError(
            f"resposta negativa para o modo 0x{raw[1]:02X}, esperado 0x{request[0]:02X}"
        )
    return Response(mode=raw[1], error_code=raw[2])


def _parse_current(raw: bytes, request: bytes | None) -> Response:
    if len(raw) < 3:
        raise ProtocolError("resposta do Modo 01 exige ao menos 3 bytes")
    pid = raw[1]
    if request and (len(request) < 2 or pid != request[1]):
        raise ProtocolError(f"PID 0x{pid:02X} não corresponde à requisição")
    data = raw[2:]
    pid_def = PIDS.get(pid)
    if pid_def is not None and len(data) != pid_def.n_bytes:
        raise ProtocolError(
            f"PID 0x{pid:02X} espera {pid_def.n_bytes} byte(s), recebeu {len(data)}"
        )
    return Response(MODE_CURRENT, pid=pid, data=data)


def _parse_dtcs(mode: int, raw: bytes) -> Response:
    if len(raw) < 2:
        raise ProtocolError("resposta de DTCs exige o byte de contagem")
    n = raw[1]
    body = raw[2:]
    if len(body) != 2 * n:
        raise ProtocolError(f"contagem {n} incompatível com {len(body)} byte(s) de DTC")
    codes = tuple(dtc.bytes_to_code(body[i : i + 2]) for i in range(0, len(body), 2))
    return Response(mode, dtcs=codes)


def build_dtc_response(mode: int, codes: list[str]) -> bytes:
    """Resposta dos Modos 03/07 (usada pela ECU simulada)."""
    if mode not in _DTC_MODES:
        raise ProtocolError(f"modo 0x{mode:02X} não é de DTCs")
    return bytes([mode + 0x40, len(codes)]) + b"".join(dtc.code_to_bytes(c) for c in codes)
