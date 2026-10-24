import asyncio
import uuid
from collections.abc import AsyncIterator

import can
import pytest

from fakes import FakeVehicleModel
from obd.protocol.pids import decode_supported, get_pid
from obd.protocol.services import build_request, parse_response
from obd.simulator.ecu import Ecu, EcuCanNode
from obd.transport.can_virtual import CanVirtualTransport

VIN = "9BWZZZ377VT004251"
VALUES = {
    0x04: 42.0,
    0x05: 88.0,
    0x06: -2.3,
    0x0B: 33.0,
    0x0C: 3127.4,
    0x0D: 77.0,
    0x0F: 31.0,
    0x11: 18.5,
    0x2F: 61.2,
    0x42: 13.987,
}


@pytest.fixture
async def rig() -> AsyncIterator[tuple[CanVirtualTransport, Ecu]]:
    import time

    channel = f"obd-{uuid.uuid4().hex}"
    ecu = Ecu(FakeVehicleModel(VALUES, time.monotonic), time.monotonic, vin=VIN)
    bus = can.Bus(interface="virtual", channel=channel, receive_own_messages=False)
    node = EcuCanNode(ecu, bus)
    transport = CanVirtualTransport(channel=channel)
    await node.start()
    await transport.open()
    try:
        yield transport, ecu
    finally:
        await transport.close()
        await node.stop()
        bus.shutdown()


@pytest.mark.parametrize("pid", sorted(VALUES))
async def test_reads_each_pid_over_virtual_bus(
    rig: tuple[CanVirtualTransport, Ecu], pid: int
) -> None:
    transport, ecu = rig
    req = build_request(1, pid)
    raw = await transport.request(req, timeout_ms=500)
    assert raw is not None
    d = get_pid(pid)
    _, true_value = ecu.log[-1]
    assert abs(d.decode(parse_response(raw, req).data) - true_value) <= d.resolution / 2 + 1e-9


async def test_name(rig: tuple[CanVirtualTransport, Ecu]) -> None:
    assert rig[0].name == "can_virtual"


async def test_discovery_over_virtual_bus(rig: tuple[CanVirtualTransport, Ecu]) -> None:
    transport, ecu = rig
    found: set[int] = set()
    for base in (0x00, 0x20, 0x40):
        raw = await transport.request(build_request(1, base), timeout_ms=500)
        assert raw is not None
        found |= decode_supported(base, parse_response(raw).data)
    assert ecu.pids <= found


async def test_vin_multiframe_over_virtual_bus(rig: tuple[CanVirtualTransport, Ecu]) -> None:
    raw = await rig[0].request(build_request(9, 2), timeout_ms=500)
    assert raw is not None and parse_response(raw).data == VIN.encode()


async def test_unsupported_pid_times_out(rig: tuple[CanVirtualTransport, Ecu]) -> None:
    transport, ecu = rig
    ecu.set_supported_pids({0x0C})
    assert await transport.request(build_request(1, 0x0D), timeout_ms=60) is None


async def test_concurrent_requests_are_serialized(rig: tuple[CanVirtualTransport, Ecu]) -> None:
    transport, _ = rig
    results = await asyncio.gather(
        *(transport.request(build_request(1, p), timeout_ms=500) for p in (0x0C, 0x0D, 0x05))
    )
    assert [r[:2] for r in results if r] == [b"\x41\x0c", b"\x41\x0d", b"\x41\x05"]
