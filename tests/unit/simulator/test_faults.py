import pytest

from fakes import FakeClock, FakeVehicleModel
from obd.protocol import frames, isotp
from obd.protocol.dtc import code_to_bytes
from obd.simulator.ecu import Ecu
from obd.simulator.faults import FaultInjector

VALUES = {0x05: 90.0, 0x0C: 2000.0, 0x0D: 60.0, 0x11: 20.0}


def make(faults: FaultInjector | None = None) -> tuple[Ecu, FakeClock, FaultInjector]:
    clock = FakeClock()
    faults = faults or FaultInjector(seed=1)
    ecu = Ecu(FakeVehicleModel(VALUES, clock), clock, pids=VALUES, faults=faults)
    return ecu, clock, faults


def ask(ecu: Ecu, payload: bytes) -> bytes | None:
    ecu.on_frame(frames.ID_FUNCTIONAL, isotp.segment(payload)[0])
    rx = isotp.Reassembler()
    for _ in range(50):
        for f in ecu.poll():
            msg = rx.feed(f.data, ecu.clock())
            if msg is None and f.data[0] >> 4 == 1:
                ecu.on_frame(0x7E0, isotp.flow_control_frame(0, 0))
            if msg is not None:
                return msg
    return None


def test_loss_probability_statistical() -> None:
    ecu, _, faults = make()
    faults.set_frame_loss(0.3)
    got = sum(ask(ecu, bytes([1, 0x0D])) is not None for _ in range(2000))
    assert 0.65 * 2000 < got < 0.75 * 2000


def test_loss_deterministic_per_seed() -> None:
    def pattern(seed: int) -> list[bool]:
        ecu, _, faults = make(FaultInjector(seed=seed))
        faults.set_frame_loss(0.5)
        return [ask(ecu, bytes([1, 0x0D])) is not None for _ in range(50)]

    assert pattern(4) == pattern(4)
    assert pattern(4) != pattern(5)


def test_corruption_probability_statistical_and_breaks_echo() -> None:
    ecu, _, faults = make()
    faults.set_corruption(0.25)
    bad = 0
    for _ in range(2000):
        resp = ask(ecu, bytes([1, 0x0D]))
        assert resp is not None and len(resp) == 3
        if resp[:2] != bytes([0x41, 0x0D]):
            bad += 1
    assert 0.20 * 2000 < bad < 0.30 * 2000


def test_no_faults_means_clean_responses() -> None:
    ecu, _, _ = make()
    for _ in range(100):
        assert ask(ecu, bytes([1, 0x0D]))[:2] == bytes([0x41, 0x0D])  # type: ignore[index]


def test_probability_validation() -> None:
    f = FaultInjector(seed=0)
    for bad in (-0.1, 1.1):
        with pytest.raises(ValueError):
            f.set_frame_loss(bad)
        with pytest.raises(ValueError):
            f.set_corruption(bad)


def test_mute_ecu_toggle() -> None:
    ecu, _, faults = make()
    faults.set_mute(True)
    assert ask(ecu, bytes([1, 0x0D])) is None
    assert ask(ecu, b"\x03") is None
    faults.set_mute(False)
    assert ask(ecu, bytes([1, 0x0D])) is not None


def test_unsupported_pids_leave_discovery_and_go_silent() -> None:
    ecu, _, faults = make()
    faults.set_unsupported({0x0D})
    assert ask(ecu, bytes([1, 0x0D])) is None
    mask = ask(ecu, bytes([1, 0x00]))
    assert mask is not None
    from obd.protocol.pids import decode_supported

    assert 0x0D not in decode_supported(0x00, mask[2:])
    assert ask(ecu, bytes([1, 0x0C])) is not None
    faults.set_unsupported(set())
    assert ask(ecu, bytes([1, 0x0D])) is not None


def test_negative_response_per_mode() -> None:
    ecu, _, faults = make()
    faults.set_negative(1, 0x22)
    assert ask(ecu, bytes([1, 0x0D])) == bytes([0x7F, 0x01, 0x22])
    assert ask(ecu, b"\x03") == b"\x43\x00"
    faults.set_negative(1, None)
    assert ask(ecu, bytes([1, 0x0D])) is not None


def test_stored_dtc_with_instant_applies_when_due() -> None:
    ecu, clock, faults = make()
    faults.schedule_dtc("P0300", at=5.0)
    assert ask(ecu, b"\x03") == b"\x43\x00"
    clock.advance(5.0)
    assert ask(ecu, b"\x03") == b"\x43\x01" + code_to_bytes("P0300")


def test_pending_dtc_goes_to_mode07_only() -> None:
    ecu, _, faults = make()
    faults.schedule_dtc("P0171", pending=True)
    assert ask(ecu, b"\x07") == b"\x47\x01" + code_to_bytes("P0171")
    assert ask(ecu, b"\x03") == b"\x43\x00"
    status = ask(ecu, bytes([1, 1]))
    assert status is not None and status[2] == 0


def test_isotp_stmin_spaces_consecutive_frames() -> None:
    ecu, clock, faults = make()
    faults.set_isotp(stmin_ms=5)
    ecu.on_frame(frames.ID_FUNCTIONAL, isotp.segment(bytes([9, 2]))[0])
    assert len(ecu.poll()) == 1  # primeiro quadro
    ecu.on_frame(0x7E0, isotp.flow_control_frame(0, 0))
    assert len(ecu.poll()) == 1
    assert ecu.poll() == []
    clock.advance(0.005)
    assert len(ecu.poll()) == 1


def test_isotp_block_size_forces_extra_flow_control() -> None:
    ecu, _, faults = make()
    faults.set_isotp(block_size=1)
    ecu.on_frame(frames.ID_FUNCTIONAL, isotp.segment(bytes([9, 2]))[0])
    ecu.poll()
    ecu.on_frame(0x7E0, isotp.flow_control_frame(0, 0))
    assert len(ecu.poll()) == 1
    assert ecu.poll() == []  # espera novo FC
    ecu.on_frame(0x7E0, isotp.flow_control_frame(0, 0))
    assert len(ecu.poll()) == 1


def test_isotp_validation() -> None:
    with pytest.raises(ValueError):
        FaultInjector(seed=0).set_isotp(stmin_ms=200)
    with pytest.raises(ValueError):
        FaultInjector(seed=0).set_isotp(block_size=256)


def test_response_delay_via_injector() -> None:
    ecu, clock, faults = make()
    faults.set_delay(20, 20)
    ecu.on_frame(frames.ID_FUNCTIONAL, isotp.segment(bytes([1, 0x0D]))[0])
    assert ecu.poll() == []
    clock.advance(0.02)
    assert len(ecu.poll()) == 1


def test_clear_resets_everything() -> None:
    ecu, _, faults = make()
    faults.set_mute(True)
    faults.set_frame_loss(1.0)
    faults.set_negative(1, 0x22)
    faults.clear()
    assert ask(ecu, bytes([1, 0x0D])) is not None
