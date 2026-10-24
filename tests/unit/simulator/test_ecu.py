import pytest

from fakes import FakeClock, FakeVehicleModel
from obd.protocol import frames, isotp
from obd.protocol.dtc import code_to_bytes
from obd.protocol.pids import PIDS, decode_supported, get_pid
from obd.simulator.ecu import Ecu

VIN = "9BWZZZ377VT004251"
VALUES = {
    0x04: 40.0,
    0x05: 90.0,
    0x06: 1.5,
    0x0B: 35.0,
    0x0C: 2500.25,
    0x0D: 60.0,
    0x0F: 30.0,
    0x11: 20.0,
    0x2F: 55.0,
    0x42: 14.1,
}


def make(clock: FakeClock | None = None, **kw: object) -> tuple[Ecu, FakeClock]:
    clock = clock or FakeClock()
    ecu = Ecu(FakeVehicleModel(VALUES, clock), clock, vin=VIN, **kw)  # type: ignore[arg-type]
    return ecu, clock


def ask(ecu: Ecu, payload: bytes, can_id: int = frames.ID_FUNCTIONAL) -> bytes | None:
    """Envia a requisição e devolve a resposta completa (só quadro único ou remontada)."""
    ecu.on_frame(can_id, isotp.segment(payload)[0])
    rx = isotp.Reassembler()
    for _ in range(50):
        for f in ecu.poll():
            assert f.can_id == frames.ID_ENGINE_RESPONSE
            msg = rx.feed(f.data, ecu.clock())
            if rx.active and msg is None and f.data[0] >> 4 == 1:
                ecu.on_frame(0x7E0, isotp.flow_control_frame(0, 0))
            if msg is not None:
                return msg
    return None


@pytest.mark.parametrize("pid", sorted(VALUES))
def test_mode01_value_within_half_resolution(pid: int) -> None:
    ecu, _ = make()
    resp = ask(ecu, bytes([1, pid]))
    assert resp is not None and resp[:2] == bytes([0x41, pid])
    d = get_pid(pid)
    assert abs(d.decode(resp[2:]) - VALUES[pid]) <= d.resolution / 2 + 1e-9


def test_log_records_request_id_and_true_value() -> None:
    ecu, _ = make()
    ask(ecu, bytes([1, 0x0D]))
    ask(ecu, bytes([1, 0x05]))
    assert ecu.log == [(1, 60.0), (2, 90.0)]


def test_unsupported_pid_is_silent_and_not_logged() -> None:
    ecu, _ = make(pids={0x0C})
    assert ask(ecu, bytes([1, 0x0D])) is None
    assert ecu.log == []


def test_ignores_other_ids_and_garbage() -> None:
    ecu, _ = make()
    ecu.on_frame(0x7E1, isotp.segment(bytes([1, 0x0D]))[0])
    ecu.on_frame(frames.ID_FUNCTIONAL, b"\x07\x01")  # DLC errado
    ecu.on_frame(frames.ID_FUNCTIONAL, bytes([0x2F]) + b"\x55" * 7)  # CF solto
    assert ecu.poll() == []


def test_physical_address_answers() -> None:
    ecu, _ = make()
    assert ask(ecu, bytes([1, 0x0D]), can_id=0x7E0) is not None


def test_support_masks_match_configured_pids() -> None:
    pids = {0x04, 0x0C, 0x0D, 0x2F, 0x42}
    ecu, _ = make(pids=pids)
    announced: set[int] = set()
    for base in (0x00, 0x20, 0x40):
        resp = ask(ecu, bytes([1, base]))
        assert resp is not None
        announced |= decode_supported(base, resp[2:])
    assert announced == pids | {0x01, 0x20, 0x40}


def test_support_mask_without_high_pids_has_no_continuation() -> None:
    ecu, _ = make(pids={0x0C})
    resp = ask(ecu, bytes([1, 0x00]))
    assert resp is not None
    assert decode_supported(0x00, resp[2:]) == {0x01, 0x0C}
    assert ask(ecu, bytes([1, 0x20])) is None


def test_default_pids_are_the_ten_implemented() -> None:
    ecu, _ = make()
    assert ecu.pids == frozenset(PIDS)


def test_response_delay_uses_clock() -> None:
    ecu, clock = make(delay_ms=(30, 30))
    ecu.on_frame(frames.ID_FUNCTIONAL, isotp.segment(bytes([1, 0x0D]))[0])
    assert ecu.poll() == []
    clock.advance(0.029)
    assert ecu.poll() == []
    clock.advance(0.001)
    assert len(ecu.poll()) == 1


def test_delay_is_deterministic_per_seed_and_in_range() -> None:
    def draw(seed: int) -> list[float]:
        ecu, clock = make(delay_ms=(10, 50), seed=seed)
        out = []
        for _ in range(20):
            ecu.on_frame(frames.ID_FUNCTIONAL, isotp.segment(bytes([1, 0x0D]))[0])
            t0 = clock.now
            while not ecu.poll():
                clock.advance(0.001)
            out.append(round(clock.now - t0, 3))
        return out

    a = draw(1)
    assert a == draw(1)
    assert all(0.010 <= d <= 0.051 for d in a)
    assert a != draw(2)


def test_set_response_delay_validates() -> None:
    ecu, _ = make()
    with pytest.raises(ValueError):
        ecu.set_response_delay(50, 10)
    with pytest.raises(ValueError):
        ecu.set_response_delay(-1, 10)


def test_vin_is_multiframe_and_complete() -> None:
    ecu, _ = make()
    resp = ask(ecu, bytes([9, 2]))
    assert resp == bytes([0x49, 0x02, 0x01]) + VIN.encode()


def test_multiframe_waits_for_flow_control() -> None:
    ecu, _ = make()
    ecu.on_frame(frames.ID_FUNCTIONAL, isotp.segment(bytes([9, 2]))[0])
    first = ecu.poll()
    assert len(first) == 1 and first[0].data[0] >> 4 == 1
    assert ecu.poll() == []  # sem FC, nada de CF
    ecu.on_frame(0x7E0, isotp.flow_control_frame(0, 0))
    assert len(ecu.poll()) == 2


def test_missing_flow_control_aborts_after_n_cr() -> None:
    ecu, clock = make()
    ecu.on_frame(frames.ID_FUNCTIONAL, isotp.segment(bytes([9, 2]))[0])
    ecu.poll()
    clock.advance(isotp.N_CR_TIMEOUT + 0.1)
    assert ecu.poll() == []
    ecu.on_frame(0x7E0, isotp.flow_control_frame(0, 0))  # FC atrasado é ignorado
    assert ecu.poll() == []


def test_dtc_modes_and_clear() -> None:
    ecu, _ = make()
    assert ask(ecu, b"\x03") == b"\x43\x00"
    assert ask(ecu, b"\x07") == b"\x47\x00"
    ecu.add_dtc("P0300")
    ecu.add_dtc("P0171", pending=True)
    assert ask(ecu, b"\x03") == b"\x43\x01" + code_to_bytes("P0300")
    assert ask(ecu, b"\x07") == b"\x47\x01" + code_to_bytes("P0171")
    status = ask(ecu, bytes([1, 0x01]))
    assert status is not None and status[2] & 0x80 and status[2] & 0x7F == 1
    assert ask(ecu, b"\x04") == b"\x44"
    assert ask(ecu, b"\x03") == b"\x43\x00"
    assert ask(ecu, b"\x07") == b"\x47\x00"
    status = ask(ecu, bytes([1, 0x01]))
    assert status is not None and status[2] == 0


def test_many_dtcs_use_multiframe() -> None:
    ecu, _ = make()
    codes = ["P0300", "P0301", "P0302", "P0303"]
    for c in codes:
        ecu.add_dtc(c)
    resp = ask(ecu, b"\x03")
    assert resp == b"\x43\x04" + b"".join(code_to_bytes(c) for c in codes)


def test_freeze_frame_captured_with_first_dtc() -> None:
    clock = FakeClock()
    model = FakeVehicleModel({**VALUES}, clock, slopes={0x0D: 10.0})
    ecu = Ecu(model, clock, vin=VIN)
    assert ask(ecu, bytes([2, 0x0D, 0])) is None  # sem DTC, sem freeze frame
    clock.advance(1.0)
    ecu.add_dtc("P0300")
    clock.advance(5.0)
    resp = ask(ecu, bytes([2, 0x0D, 0]))
    assert resp is not None and resp[:3] == bytes([0x42, 0x0D, 0x00])
    assert resp[3] == 70  # velocidade no instante da falha, não a atual
    ecu.clear_dtcs()
    assert ask(ecu, bytes([2, 0x0D, 0])) is None


def test_negative_responses() -> None:
    ecu, _ = make()
    assert ask(ecu, bytes([0x05, 0x00])) == bytes([0x7F, 0x05, 0x11])
    assert ask(ecu, bytes([9, 0x04])) == bytes([0x7F, 0x09, 0x12])
    assert ask(ecu, bytes([3, 0x00])) == bytes([0x7F, 0x03, 0x13])
    assert ask(ecu, bytes([1])) == bytes([0x7F, 0x01, 0x13])
