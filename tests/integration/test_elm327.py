import time
from collections.abc import AsyncIterator

import pytest

from fakes import FakeElm327Client, FakeVehicleModel
from obd.collector.collector import Collector
from obd.collector.factory import build_transport
from obd.collector.publisher import RecordingPublisher
from obd.collector.scheduler import CollectorConfig
from obd.protocol.pids import get_pid
from obd.simulator.ecu import Ecu
from obd.simulator.elm327_server import Elm327Server
from obd.transport.elm327_tcp import parse_reply
from obd.transport.loopback import LoopbackTransport

VALUES = {
    0x04: 42.0,
    0x05: 88.0,
    0x06: 0.0,
    0x0B: 33.0,
    0x0C: 3127.5,
    0x0D: 77.0,
    0x0F: 31.0,
    0x11: 18.5,
    0x2F: 61.2,
    0x42: 13.987,
}
END = "\r\r>"


def make_ecu() -> Ecu:
    return Ecu(FakeVehicleModel(VALUES, time.monotonic), time.monotonic)


@pytest.fixture
async def rig() -> AsyncIterator[tuple[Ecu, Elm327Server]]:
    ecu = make_ecu()
    server = Elm327Server(LoopbackTransport(ecu), port=0)
    await server.start()
    try:
        yield ecu, server
    finally:
        await server.stop()


async def test_fake_client_script(rig: tuple[Ecu, Elm327Server]) -> None:
    _, server = rig
    async with FakeElm327Client("127.0.0.1", server.port) as c:
        assert await c.send("ATZ") == f"ELM327 v1.5{END}"
        assert await c.send("ATE0") == f"ATE0\rOK{END}"
        await c.run_script(
            [
                ("ATL0", f"OK{END}"),
                ("ATS1", f"OK{END}"),
                ("0100", f"SEARCHING...\r41 00 9C 3A 80 01{END}"),
                ("010C", f"41 0C 30 DE{END}"),
                ("03", f"NO DATA{END}"),
                ("ATDP", f"ISO 15765-4 (CAN 11/500){END}"),
                ("ATRV", f"14.0V{END}"),
            ]
        )


async def test_searching_only_on_first_0100(rig: tuple[Ecu, Elm327Server]) -> None:
    _, server = rig
    async with FakeElm327Client("127.0.0.1", server.port) as c:
        await c.send("ATE0")
        assert (await c.send("0100")).startswith("SEARCHING...")
        assert not (await c.send("0100")).startswith("SEARCHING...")
        await c.send("ATZ")
        assert "SEARCHING..." in await c.send("0100")


async def test_unknown_command_and_unsupported_pid(rig: tuple[Ecu, Elm327Server]) -> None:
    ecu, server = rig
    ecu.set_supported_pids({0x0C})
    async with FakeElm327Client("127.0.0.1", server.port) as c:
        await c.send("ATE0")
        await c.send("ATS0")
        await c.run_script(
            [
                ("FOO", f"?{END}"),
                ("ATXYZ", f"?{END}"),
                ("010", f"?{END}"),
                ("010D", f"NO DATA{END}"),
                ("010C", f"410C30DE{END}"),
            ]
        )


async def test_dtcs_and_clear(rig: tuple[Ecu, Elm327Server]) -> None:
    ecu, server = rig
    ecu.add_dtc("P0300")
    async with FakeElm327Client("127.0.0.1", server.port) as c:
        await c.send("ATE0")
        assert await c.send("03") == f"43 01 03 00{END}"
        assert await c.send("04") == f"44{END}"
        assert await c.send("03") == f"NO DATA{END}"


async def test_vin_comes_reassembled(rig: tuple[Ecu, Elm327Server]) -> None:
    _, server = rig
    async with FakeElm327Client("127.0.0.1", server.port) as c:
        await c.send("ATE0")
        await c.send("ATS0")
        reply = await c.send("0902")
    data = bytes.fromhex(reply.strip("\r>"))
    assert data[:3] == bytes([0x49, 0x02, 0x01])
    assert data[3:].decode() == "9BWZZZ377VT004251"


async def test_collector_via_elm327_matches_can_accuracy(
    rig: tuple[Ecu, Elm327Server],
) -> None:
    _, server = rig
    transport = build_transport("elm327_tcp", port=server.port)
    assert transport.name == "elm327_tcp"
    pub = RecordingPublisher()
    col = Collector(
        transport,
        pub,
        rates=CollectorConfig.from_yaml().plan,
        timeout_ms=500,
        source="elm327_tcp",
    )
    await col.start()
    await col.run_cycle()
    await col.close()
    s = pub.samples[0]
    planned = dict(VALUES)
    assert s.source == "elm327_tcp" and len(s.values) == len(planned)
    for pid, value in planned.items():
        d = get_pid(pid)
        assert abs(s.values[d.name].value - value) <= d.resolution / 2 + 1e-9
    assert s.errors.timeouts == 0 and s.errors.invalid == 0


async def test_transport_request_none_on_no_data(rig: tuple[Ecu, Elm327Server]) -> None:
    ecu, server = rig
    ecu.set_supported_pids({0x0C})
    transport = build_transport("elm327_tcp", port=server.port)
    await transport.open()
    try:
        assert await transport.request(bytes([0x01, 0x0C]), 500) == bytes([0x41, 0x0C, 0x30, 0xDE])
        assert await transport.request(bytes([0x01, 0x0D]), 500) is None
        vin = await transport.request(bytes([0x09, 0x02]), 500)
        assert vin is not None and vin[3:].decode() == "9BWZZZ377VT004251"
    finally:
        await transport.close()


def test_parse_reply_variants() -> None:
    assert parse_reply("SEARCHING...\r41 00 9C 3A 80 01\r\r") == bytes.fromhex("41009C3A8001")
    assert parse_reply("NO DATA\r\r") is None
    assert parse_reply("?\r\r") is None
    multi = "014\r0: 49 02 01 39 42 57\r1: 5A 5A 5A 33 37 37\r"
    assert parse_reply(multi) == bytes.fromhex("4902013942575A5A5A333737")
