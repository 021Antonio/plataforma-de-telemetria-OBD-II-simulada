"""ISO-TP (ISO 15765-2): segmentação, remontagem e controle de fluxo.

Puro: sem I/O e sem relógio. O tempo (segundos, monotônico) entra por parâmetro.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from obd.protocol.errors import ProtocolError
from obd.protocol.frames import FRAME_SIZE, pad

N_CR_TIMEOUT = 1.0  # s, espera máxima pelo próximo CF (ou pelo FC, no emissor)
MAX_LENGTH = 0xFFF
SF_MAX = 7
FF_DATA = 6
CF_DATA = 7

PCI_SF, PCI_FF, PCI_CF, PCI_FC = 0x0, 0x1, 0x2, 0x3
FC_CONTINUE, FC_WAIT, FC_OVERFLOW = 0, 1, 2
_EPS = 1e-9


class IsoTpTimeout(ProtocolError):
    """Estouro de N_Cr: o quadro esperado não chegou em 1 s."""


def segment(message: bytes) -> list[bytes]:
    """Divide em SF (até 7 bytes) ou FF + CFs. Todos os quadros saem com 8 bytes."""
    n = len(message)
    if not 1 <= n <= MAX_LENGTH:
        raise ProtocolError(f"comprimento ISO-TP fora de 1 a {MAX_LENGTH}: {n}")
    if n <= SF_MAX:
        return [pad(bytes([n]) + message)]
    frames = [bytes([0x10 | (n >> 8), n & 0xFF]) + message[:FF_DATA]]
    seq = 1
    for i in range(FF_DATA, n, CF_DATA):
        frames.append(pad(bytes([0x20 | seq]) + message[i : i + CF_DATA]))
        seq = (seq + 1) & 0xF
    return frames


@dataclass(frozen=True)
class FlowControl:
    status: int
    block_size: int
    stmin: int


def flow_control_frame(bs: int, stmin: int, status: int = FC_CONTINUE) -> bytes:
    if not (0 <= bs <= 0xFF and 0 <= stmin <= 0xFF and 0 <= status <= FC_OVERFLOW):
        raise ProtocolError("parâmetro de controle de fluxo fora da faixa")
    return pad(bytes([0x30 | status, bs, stmin]))


def parse_flow_control(frame: bytes) -> FlowControl:
    if len(frame) < 3 or frame[0] >> 4 != PCI_FC:
        raise ProtocolError("não é um quadro de controle de fluxo")
    status = frame[0] & 0xF
    if status > FC_OVERFLOW:
        raise ProtocolError(f"status de controle de fluxo inválido: {status}")
    return FlowControl(status, frame[1], frame[2])


def decode_stmin(raw: int) -> float:
    """STmin em segundos: 0x00-0x7F = ms, 0xF1-0xF9 = 100 a 900 µs; reservado = 127 ms."""
    if raw <= 0x7F:
        return raw / 1000
    if 0xF1 <= raw <= 0xF9:
        return (raw - 0xF0) / 10_000
    return 0.127


class Reassembler:
    """Recebe SF/FF/CF e devolve a mensagem completa. Um erro aborta a recepção."""

    def __init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self._buf = bytearray()
        self._total = 0
        self._seq = 0
        self._deadline = 0.0
        self.active = False

    def check_timeout(self, now: float) -> None:
        if self.active and now > self._deadline + _EPS:
            self._reset()
            raise IsoTpTimeout("estouro de N_Cr: CF não chegou em 1 s")

    def feed(self, frame: bytes, now: float) -> bytes | None:
        self.check_timeout(now)
        if len(frame) != FRAME_SIZE:
            raise ProtocolError(f"quadro ISO-TP deve ter {FRAME_SIZE} bytes: {len(frame)}")
        kind = frame[0] >> 4
        if kind == PCI_SF:
            return self._single(frame)
        if kind == PCI_FF:
            self._first(frame, now)
            return None
        if kind == PCI_CF:
            return self._consecutive(frame, now)
        self._reset()
        raise ProtocolError(f"PCI inesperado na recepção: 0x{frame[0]:02X}")

    def _single(self, frame: bytes) -> bytes:
        self._reset()
        n = frame[0] & 0xF
        if not 1 <= n <= SF_MAX:
            raise ProtocolError(f"comprimento de SF inválido: {n}")
        return frame[1 : 1 + n]

    def _first(self, frame: bytes, now: float) -> None:
        self._reset()
        total = ((frame[0] & 0xF) << 8) | frame[1]
        if total <= SF_MAX:
            raise ProtocolError(f"comprimento de FF inválido: {total}")
        self._buf.extend(frame[2 : 2 + FF_DATA])
        self._total = total
        self._seq = 1
        self._deadline = now + N_CR_TIMEOUT
        self.active = True

    def _consecutive(self, frame: bytes, now: float) -> bytes | None:
        if not self.active:
            self._reset()
            raise ProtocolError("CF sem FF anterior")
        seq = frame[0] & 0xF
        if seq != self._seq:
            expected = self._seq
            self._reset()
            raise ProtocolError(f"sequência inválida: recebeu {seq}, esperado {expected}")
        self._buf.extend(frame[1 : 1 + min(CF_DATA, self._total - len(self._buf))])
        if len(self._buf) == self._total:
            msg = bytes(self._buf)
            self._reset()
            return msg
        self._seq = (self._seq + 1) & 0xF
        self._deadline = now + N_CR_TIMEOUT
        return None


def reassemble(frames: Iterable[bytes]) -> bytes:
    """Remonta uma sequência completa de quadros (sem controle de tempo)."""
    rx = Reassembler()
    for f in frames:
        msg = rx.feed(f, 0.0)
        if msg is not None:
            return msg
    raise ProtocolError("mensagem ISO-TP incompleta")


class Sender:
    """Emissor: `start` devolve SF/FF; após o FC, `poll(now)` libera os CFs devidos."""

    def __init__(self, message: bytes) -> None:
        self._frames = segment(message)
        self._next = 1
        self._started = False
        self._sending = False
        self._bs_left: int | None = None
        self._stmin = 0.0
        self._next_time = 0.0
        self._deadline = 0.0

    @property
    def done(self) -> bool:
        return self._started and self._next >= len(self._frames)

    def start(self, now: float = 0.0) -> bytes:
        self._started = True
        self._deadline = now + N_CR_TIMEOUT
        return self._frames[0]

    def on_flow_control(self, frame: bytes, now: float) -> None:
        if not self._started or self.done or self._sending:
            raise ProtocolError("controle de fluxo inesperado")
        fc = parse_flow_control(frame)
        if fc.status == FC_OVERFLOW:
            raise ProtocolError("estouro de buffer no receptor (FC overflow)")
        self._deadline = now + N_CR_TIMEOUT
        if fc.status == FC_WAIT:
            return
        self._sending = True
        self._bs_left = fc.block_size or None
        self._stmin = decode_stmin(fc.stmin)
        self._next_time = now

    def poll(self, now: float) -> list[bytes]:
        if not self._started:
            raise ProtocolError("start() não foi chamado")
        if not self._sending:
            if not self.done and now > self._deadline + _EPS:
                raise IsoTpTimeout("estouro de N_Cr: FC não chegou em 1 s")
            return []
        out: list[bytes] = []
        while self._sending and now + _EPS >= self._next_time and not self.done:
            out.append(self._frames[self._next])
            self._next += 1
            self._next_time = now + self._stmin
            if self._bs_left is not None:
                self._bs_left -= 1
                if self._bs_left == 0 and not self.done:
                    self._sending = False
                    self._deadline = now + N_CR_TIMEOUT
            if self._stmin > 0:
                break
        return out


__all__ = [
    "FC_CONTINUE",
    "FC_OVERFLOW",
    "FC_WAIT",
    "N_CR_TIMEOUT",
    "FlowControl",
    "IsoTpTimeout",
    "Reassembler",
    "Sender",
    "decode_stmin",
    "flow_control_frame",
    "parse_flow_control",
    "reassemble",
    "segment",
]
