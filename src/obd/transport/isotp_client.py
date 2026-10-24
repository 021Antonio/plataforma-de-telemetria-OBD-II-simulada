"""Lado do testador no ISO-TP: envia o quadro único, remonta a resposta e manda os FC.

Compartilhado pelos transportes; o relógio, o `sleep` e o acesso aos quadros são injetados.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from obd.protocol import isotp
from obd.protocol.errors import ProtocolError
from obd.protocol.frames import (
    ID_ENGINE_RESPONSE,
    ID_FUNCTIONAL,
    ID_PHYSICAL_REQUEST,
    CanFrame,
)

Send = Callable[[int, bytes], None]
Recv = Callable[[], list[CanFrame]]
Sleep = Callable[[float], Awaitable[None]]

ID_TESTER_PHYSICAL = ID_PHYSICAL_REQUEST[0]  # 0x7E0: destino do controle de fluxo
POLL_INTERVAL = 0.0005  # s


def request_frame(payload: bytes) -> bytes:
    frames = isotp.segment(payload)
    if len(frames) != 1:
        raise ProtocolError(f"requisição OBD deve caber em um quadro único: {len(payload)} bytes")
    return frames[0]


async def exchange(
    payload: bytes,
    timeout_ms: int,
    *,
    send: Send,
    recv: Recv,
    clock: Callable[[], float],
    sleep: Sleep,
    block_size: int = 0,
    stmin: int = 0,
    interval: float = POLL_INTERVAL,
) -> bytes | None:
    """Uma requisição e a resposta remontada. `timeout_ms` vale até o primeiro quadro (P2);
    depois do FF, vale o N_Cr do ISO-TP. Estouro de N_Cr também devolve None."""
    frame = request_frame(payload)
    deadline = clock() + timeout_ms / 1000
    send(ID_FUNCTIONAL, frame)
    rx = isotp.Reassembler()
    since_fc = 0
    fc = isotp.flow_control_frame(block_size, stmin)
    try:
        while True:
            now = clock()
            rx.check_timeout(now)
            for f in recv():
                if f.can_id != ID_ENGINE_RESPONSE:
                    continue
                kind = f.data[0] >> 4
                if kind == isotp.PCI_CF and not rx.active:
                    continue  # resto de uma resposta anterior
                msg = rx.feed(f.data, now)
                if msg is not None:
                    return msg
                if kind == isotp.PCI_FF:
                    since_fc = 0
                    send(ID_TESTER_PHYSICAL, fc)
                elif block_size:
                    since_fc += 1
                    if since_fc == block_size:
                        since_fc = 0
                        send(ID_TESTER_PHYSICAL, fc)
            if not rx.active and now >= deadline:
                return None
            await sleep(interval)
    except isotp.IsoTpTimeout:
        return None
