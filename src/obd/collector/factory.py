"""Escolha do transporte por configuração (RF12): o coletor só vê a interface `Transport`."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from obd.collector.mqtt_publisher import MqttPublisher
from obd.collector.publisher import HttpPublisher, Publisher
from obd.mqtt_common import AiomqttLink, LinkFactory
from obd.transport.base import Transport
from obd.transport.can_virtual import CanVirtualTransport
from obd.transport.elm327_tcp import Elm327TcpTransport
from obd.transport.loopback import FrameBus, LoopbackTransport

TRANSPORTS = ("can_virtual", "loopback", "elm327_tcp")


def build_transport(
    kind: str,
    *,
    ecu: FrameBus | None = None,
    channel: str = "obd",
    host: str = "localhost",
    port: int = 35000,
    search_timeout_s: float = 5.0,
) -> Transport:
    if kind == "can_virtual":
        return CanVirtualTransport(channel=channel)
    if kind == "loopback":
        if ecu is None:
            raise ValueError("o transporte loopback precisa de uma ECU")
        return LoopbackTransport(ecu)
    if kind == "elm327_tcp":
        return Elm327TcpTransport(host, port, search_timeout_s=search_timeout_s)
    raise ValueError(f"transporte desconhecido: {kind!r} (opções: {', '.join(TRANSPORTS)})")


PUBLISHERS = ("http", "mqtt")


def build_publisher(
    config: Mapping[str, Any], *, link_factory: LinkFactory | None = None
) -> Publisher:
    """Escolhe o publicador pelo bloco `publisher` da configuração (HTTP é o padrão)."""
    kind = config.get("publisher", "http")
    if kind == "http":
        return HttpPublisher(config.get("servidor_url", "http://localhost:8000"))
    if kind == "mqtt":
        mqtt = config.get("mqtt", {})
        host, port = mqtt.get("host", "localhost"), int(mqtt.get("porta", 1883))
        factory = link_factory or (lambda: AiomqttLink(host, port))
        return MqttPublisher(factory, mqtt.get("veiculo", "simulado"))
    raise ValueError(f"publicador desconhecido: {kind!r} (opções: {', '.join(PUBLISHERS)})")
