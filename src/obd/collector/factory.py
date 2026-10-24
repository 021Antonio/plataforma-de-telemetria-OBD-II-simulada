"""Escolha do transporte por configuração (RF12): o coletor só vê a interface `Transport`."""

from __future__ import annotations

from obd.simulator.ecu import Ecu
from obd.transport.base import Transport
from obd.transport.can_virtual import CanVirtualTransport
from obd.transport.loopback import LoopbackTransport

TRANSPORTS = ("can_virtual", "loopback", "elm327_tcp")


def build_transport(kind: str, *, ecu: Ecu | None = None, channel: str = "obd") -> Transport:
    if kind == "can_virtual":
        return CanVirtualTransport(channel=channel)
    if kind == "loopback":
        if ecu is None:
            raise ValueError("o transporte loopback precisa de uma ECU")
        return LoopbackTransport(ecu)
    if kind == "elm327_tcp":
        raise NotImplementedError("elm327_tcp chega na tarefa 09")
    raise ValueError(f"transporte desconhecido: {kind!r} (opções: {', '.join(TRANSPORTS)})")
