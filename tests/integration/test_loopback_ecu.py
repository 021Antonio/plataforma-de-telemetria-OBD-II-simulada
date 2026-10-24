import pytest

from fakes import FakeClock, FakeVehicleModel
from obd.protocol.dtc import code_to_bytes
from obd.protocol.pids import PIDS, decode_supported, get_pid
from obd.protocol.services import build_request, parse_response
from obd.simulator.ecu import Ecu
from obd.transport.loopback import LoopbackTransport

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


def build(
    delay_ms: tuple[int, int] = (0, 0), pids: set[int] | None = None, **tp: int
) -> tuple[LoopbackTransport, Ecu, FakeClock]:
    clock = FakeClock()
    model = FakeVehicleModel(VALUES, clock, slopes={0x0C: 100.0})
    ecu = Ecu(model, clock, vin=VIN, delay_ms=delay_ms, pids=pids)
    return LoopbackTransport(ecu, clock=clock, sleep=clock.sleep, **tp), ecu, clock


@pytest.mark.parametrize("pid", sorted(VALUES))
async def test_reads_each_pid_within_half_resolution(pid: int) -> None:
    t, ecu, clock = build()
    await t.open()
    clock.advance(2.0)  # a rampa do RPM já se afastou do valor inicial
    req = build_request(1, pid)
    raw = await t.request(req)
    assert raw is not None
    resp = parse_response(raw, req)
    d = get_pid(pid)
    _, true_value = ecu.log[-1]
    assert abs(d.decode(resp.data) - true_value) <= d.resolution / 2 + 1e-9
    await t.close()


async def test_loopback_name() -> None:
    t, _, _ = build()
    assert t.name == "loopback"


async def test_pid_discovery_matches_configuration() -> None:
    configured = {0x04, 0x0C, 0x0D, 0x11, 0x42}
    t, _, _ = build(pids=configured)
    found: set[int] = set()
    for base in (0x00, 0x20, 0x40):
        raw = await t.request(build_request(1, base))
        assert raw is not None
        found |= decode_supported(base, parse_response(raw).data)
    assert found - {0x20, 0x40} == configured | {0x01}


async def test_default_discovery_announces_all_ten_pids() -> None:
    t, _, _ = build()
    found: set[int] = set()
    for base in (0x00, 0x20, 0x40):
        raw = await t.request(build_request(1, base))
        assert raw is not None
        found |= decode_supported(base, parse_response(raw).data)
    assert set(PIDS) <= found


async def test_vin_by_full_isotp() -> None:
    t, _, _ = build()
    raw = await t.request(build_request(9, 2))
    assert raw is not None
    assert parse_response(raw).data == VIN.encode()


@pytest.mark.parametrize(("bs", "stmin"), [(0, 0), (1, 0), (2, 1), (0, 5)])
async def test_vin_with_block_size_and_stmin(bs: int, stmin: int) -> None:
    t, _, clock = build(bs=bs, stmin=stmin)
    raw = await t.request(build_request(9, 2), timeout_ms=200)
    assert raw is not None and parse_response(raw).data == VIN.encode()
    if stmin:
        assert clock.now >= 0.001  # os CFs respeitaram o espaçamento


async def test_unsupported_pid_times_out() -> None:
    t, _, clock = build(pids={0x0C})
    assert await t.request(build_request(1, 0x0D), timeout_ms=100) is None
    assert clock.now >= 0.1


async def test_response_arrives_after_configured_delay() -> None:
    t, _, clock = build(delay_ms=(30, 30))
    raw = await t.request(build_request(1, 0x0D), timeout_ms=100)
    assert raw is not None
    assert 0.030 <= clock.now < 0.040


async def test_delay_longer_than_timeout_gives_none() -> None:
    t, _, clock = build(delay_ms=(80, 80))
    assert await t.request(build_request(1, 0x0D), timeout_ms=50) is None
    assert clock.now >= 0.05


async def test_dtc_roundtrip_and_clear() -> None:
    t, ecu, _ = build()
    for c in ("P0300", "P0301", "P0171"):
        ecu.add_dtc(c)
    raw = await t.request(build_request(3))
    assert raw is not None
    assert parse_response(raw).dtcs == ("P0300", "P0301", "P0171")
    assert await t.request(build_request(4)) == b"\x44"
    raw = await t.request(build_request(3))
    assert raw == b"\x43\x00"
    assert code_to_bytes("P0300") not in raw


async def test_request_can_be_repeated() -> None:
    t, ecu, _ = build()
    for _ in range(5):
        assert await t.request(build_request(1, 0x0D)) is not None
    assert [i for i, _ in ecu.log] == [1, 2, 3, 4, 5]
