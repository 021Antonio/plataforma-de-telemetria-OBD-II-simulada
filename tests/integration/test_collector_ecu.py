import time
import uuid
from collections.abc import AsyncIterator

import can
import pytest

from fakes import FakeVehicleModel
from obd.collector.collector import Collector
from obd.collector.factory import build_transport
from obd.collector.publisher import RecordingPublisher
from obd.collector.scheduler import CollectorConfig, PidRate
from obd.protocol.pids import get_pid
from obd.simulator.ecu import Ecu, EcuCanNode
from obd.transport.base import Transport

VALUES = {
    0x04: 42.0,
    0x05: 88.0,
    0x0B: 33.0,
    0x0C: 3127.5,
    0x0D: 77.0,
    0x0F: 31.0,
    0x11: 18.5,
    0x2F: 61.2,
    0x42: 13.987,
}
NAMES = {0x0C: "rpm", 0x0D: "speed", 0x05: "coolant", 0x11: "throttle"}


def make_ecu(delay_ms: tuple[int, int] = (0, 0)) -> Ecu:
    return Ecu(FakeVehicleModel(VALUES, time.monotonic), time.monotonic, delay_ms=delay_ms)


async def test_one_cycle_with_loopback_ecu_yields_correct_sample() -> None:
    ecu = make_ecu()
    cfg = CollectorConfig.from_yaml()
    pub = RecordingPublisher()
    col = Collector(build_transport("loopback", ecu=ecu), pub, rates=cfg.plan, source="loopback")
    await col.start()
    await col.run_cycle()
    await col.close()
    s = pub.samples[0]
    assert s.seq == 0 and s.source == "loopback"
    assert len(s.values) == len(VALUES)
    for pid, value in VALUES.items():
        d = get_pid(pid)
        assert abs(s.values[d.name].value - value) <= d.resolution / 2 + 1e-9
        assert s.values[d.name].rtt_ms >= 0
    assert s.errors.timeouts == 0 and s.errors.invalid == 0


async def test_published_seq_has_no_gaps() -> None:
    cfg = CollectorConfig.from_yaml()
    pub = RecordingPublisher()
    col = Collector(build_transport("loopback", ecu=make_ecu()), pub, rates=cfg.plan)
    await col.start()
    await col.run(max_cycles=12, interval_s=0.0)
    seqs = [s.seq for s in pub.samples]
    assert seqs == list(range(12))


@pytest.fixture
async def can_rig() -> AsyncIterator[tuple[Transport, EcuCanNode]]:
    channel = f"obd-{uuid.uuid4().hex}"
    bus = can.Bus(interface="virtual", channel=channel, receive_own_messages=False)
    node = EcuCanNode(make_ecu(), bus)
    transport = build_transport("can_virtual", channel=channel)
    await node.start()
    try:
        yield transport, node
    finally:
        await node.stop()
        bus.shutdown()


async def _read_cycle(transport: Transport) -> dict[str, float]:
    pub = RecordingPublisher()
    col = Collector(transport, pub, rates=CollectorConfig.from_yaml().plan, timeout_ms=500)
    await col.start()
    await col.run_cycle()
    await col.close()
    return {k: v.value for k, v in pub.samples[0].values.items()}


async def test_transport_swap_by_config_does_not_change_collector(
    can_rig: tuple[Transport, EcuCanNode],
) -> None:
    can_transport, _ = can_rig
    via_can = await _read_cycle(can_transport)
    via_loop = await _read_cycle(build_transport("loopback", ecu=make_ecu()))
    assert via_can == via_loop and len(via_can) == len(VALUES)


def test_unknown_and_pending_transports() -> None:
    with pytest.raises(ValueError):
        build_transport("serial")
    with pytest.raises(NotImplementedError):
        build_transport("elm327_tcp")
    with pytest.raises(ValueError):
        build_transport("loopback")


async def test_cycle_of_10_pids_with_10ms_ecu_within_150ms() -> None:
    """RNF01: ciclo de 10 PIDs com ECU em 10 ms <= 150 ms."""
    values = {**VALUES, 0x06: 0.0}
    ecu = Ecu(FakeVehicleModel(values, time.monotonic), time.monotonic, delay_ms=(10, 10))
    rates = {pid: r for pid, r in (CollectorConfig.from_yaml().plan or {}).items()}
    rates[0x06] = PidRate(1, 99)
    pub = RecordingPublisher()
    col = Collector(build_transport("loopback", ecu=ecu), pub, rates=rates)
    await col.start()
    await col.run_cycle()  # ciclo 0: PIDs rápidos e lentos juntos
    first = pub.samples[0]
    assert len(first.values) == 10
    assert first.cycle_ms <= 150, first.cycle_ms
