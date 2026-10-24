import pytest
from hypothesis import given
from hypothesis import strategies as st

from fakes import FakeClock
from obd.protocol.errors import ProtocolError
from obd.protocol.isotp import (
    N_CR_TIMEOUT,
    FlowControl,
    IsoTpTimeout,
    Reassembler,
    Sender,
    decode_stmin,
    flow_control_frame,
    parse_flow_control,
    reassemble,
    segment,
)
from obd.protocol.services import build_vin_response, parse_response

VIN = "1HGCM82633A004352"


@given(st.binary(min_size=8, max_size=4095))
def test_segment_reassemble_roundtrip(msg: bytes) -> None:
    frames = segment(msg)
    assert all(len(f) == 8 for f in frames)
    assert frames[0][0] >> 4 == 1
    assert reassemble(frames) == msg


@given(st.binary(min_size=1, max_size=7))
def test_single_frame(msg: bytes) -> None:
    frames = segment(msg)
    assert len(frames) == 1
    assert frames[0][0] == len(msg)
    assert frames[0][1 + len(msg) :] == bytes([0x55]) * (7 - len(msg))
    assert reassemble(frames) == msg


@pytest.mark.parametrize("n", [0, 4096])
def test_segment_length_out_of_range(n: int) -> None:
    with pytest.raises(ProtocolError):
        segment(bytes(n))


def test_sequence_wraps_after_f() -> None:
    frames = segment(bytes(range(200)))
    assert [f[0] for f in frames[1:17]] == [0x20 | ((i + 1) & 0xF) for i in range(16)]
    assert frames[16][0] == 0x20  # volta a 0 depois de F


def test_out_of_order_cf_rejected() -> None:
    frames = segment(bytes(range(30)))
    r = Reassembler()
    r.feed(frames[0], 0.0)
    with pytest.raises(ProtocolError, match="sequência"):
        r.feed(frames[2], 0.0)


def test_repeated_cf_rejected() -> None:
    frames = segment(bytes(range(30)))
    r = Reassembler()
    r.feed(frames[0], 0.0)
    r.feed(frames[1], 0.0)
    with pytest.raises(ProtocolError, match="sequência"):
        r.feed(frames[1], 0.0)


def test_cf_without_ff_rejected() -> None:
    with pytest.raises(ProtocolError):
        Reassembler().feed(segment(bytes(range(30)))[1], 0.0)


def test_unknown_pci_rejected() -> None:
    with pytest.raises(ProtocolError):
        Reassembler().feed(bytes([0x40]) + bytes(7), 0.0)


def test_sf_invalid_length_rejected() -> None:
    with pytest.raises(ProtocolError):
        Reassembler().feed(bytes([0x08]) + bytes(7), 0.0)


def test_ff_short_length_rejected() -> None:
    with pytest.raises(ProtocolError):
        Reassembler().feed(bytes([0x10, 0x05]) + bytes(6), 0.0)


def test_vin_crosses_ff_fc_cfs() -> None:
    clock = FakeClock()
    payload = build_vin_response(VIN)
    assert len(payload) == 20
    frames = segment(payload)
    assert len(frames) == 3  # FF + 2 CFs
    assert frames[0][:2] == bytes([0x10, 0x14])

    rx = Reassembler()
    assert rx.feed(frames[0], clock()) is None
    fc = flow_control_frame(bs=0, stmin=0)
    assert fc[:3] == bytes([0x30, 0x00, 0x00])
    assert len(fc) == 8

    tx = Sender(payload)
    first = tx.start()
    assert first == frames[0]
    assert tx.poll(clock()) == []  # aguarda FC
    tx.on_flow_control(fc, clock())
    out = tx.poll(clock())
    assert out == frames[1:]
    done = None
    for f in out:
        done = rx.feed(f, clock())
    assert done == payload
    assert tx.done
    resp = parse_response(done, bytes([0x09, 0x02]))
    assert resp.data == VIN.encode()


@pytest.mark.parametrize(("stmin", "gap"), [(0, 0.0), (1, 0.001), (10, 0.010)])
def test_sender_respects_stmin(stmin: int, gap: float) -> None:
    clock = FakeClock()
    frames = segment(bytes(range(27)))  # FF + 3 CFs
    tx = Sender(bytes(range(27)))
    tx.start()
    tx.on_flow_control(flow_control_frame(0, stmin), clock())
    sent: list[float] = []
    for _ in range(2000):
        for f in tx.poll(clock()):
            assert f == frames[1 + len(sent)]
            sent.append(clock())
        if tx.done:
            break
        clock.advance(0.0005)
    assert len(sent) == 3
    for a, b in zip(sent, sent[1:], strict=False):
        assert b - a >= gap - 1e-9
    if gap:
        assert sent[1] - sent[0] < gap + 0.0006  # sem atraso desnecessário


def test_sender_block_size_waits_for_new_fc() -> None:
    clock = FakeClock()
    msg = bytes(range(40))  # FF + 5 CFs
    frames = segment(msg)
    tx = Sender(msg)
    tx.start()
    tx.on_flow_control(flow_control_frame(2, 0), clock())
    assert tx.poll(clock()) == frames[1:3]
    assert not tx.done
    assert tx.poll(clock()) == []  # bloco esgotado: espera novo FC
    tx.on_flow_control(flow_control_frame(2, 0), clock())
    assert tx.poll(clock()) == frames[3:5]
    tx.on_flow_control(flow_control_frame(2, 0), clock())
    assert tx.poll(clock()) == frames[5:]
    assert tx.done


def test_sender_wait_and_overflow() -> None:
    tx = Sender(bytes(range(27)))
    tx.start()
    tx.on_flow_control(flow_control_frame(0, 0, status=1), 0.0)  # WAIT
    assert tx.poll(0.0) == []
    tx.on_flow_control(flow_control_frame(0, 0), 0.0)
    assert len(tx.poll(0.0)) == 3
    tx2 = Sender(bytes(range(27)))
    tx2.start()
    with pytest.raises(ProtocolError, match="estouro"):
        tx2.on_flow_control(flow_control_frame(0, 0, status=2), 0.0)


def test_sender_fc_before_start_or_after_done_rejected() -> None:
    tx = Sender(bytes(range(30)))
    with pytest.raises(ProtocolError):
        tx.on_flow_control(flow_control_frame(0, 0), 0.0)
    with pytest.raises(ProtocolError):
        Sender(bytes(range(30))).poll(0.0)


def test_sender_single_frame() -> None:
    tx = Sender(b"\x41\x0c\x1f\x40")
    assert tx.start() == segment(b"\x41\x0c\x1f\x40")[0]
    assert tx.done
    assert tx.poll(0.0) == []


def test_sender_fc_timeout() -> None:
    tx = Sender(bytes(range(30)))
    tx.start(now=0.0)
    tx.poll(0.5)
    with pytest.raises(IsoTpTimeout):
        tx.poll(0.0 + N_CR_TIMEOUT + 0.001)


def test_n_cr_timeout_aborts_reception() -> None:
    frames = segment(bytes(range(30)))
    r = Reassembler()
    r.feed(frames[0], 0.0)
    r.check_timeout(N_CR_TIMEOUT - 0.001)  # ainda dentro do prazo
    with pytest.raises(IsoTpTimeout):
        r.check_timeout(N_CR_TIMEOUT + 0.001)
    assert not r.active  # recepção abortada


def test_cf_after_timeout_rejected() -> None:
    frames = segment(bytes(range(30)))
    r = Reassembler()
    r.feed(frames[0], 0.0)
    with pytest.raises(IsoTpTimeout):
        r.feed(frames[1], 2.0)


def test_n_cr_restarts_on_each_cf() -> None:
    msg = bytes(range(27))
    frames = segment(msg)
    r = Reassembler()
    r.feed(frames[0], 0.0)
    r.feed(frames[1], 0.9)
    r.feed(frames[2], 1.8)
    assert r.feed(frames[3], 2.7) == msg


def test_check_timeout_idle_is_noop() -> None:
    Reassembler().check_timeout(100.0)


def test_new_ff_restarts_reception() -> None:
    a, b = bytes(range(30)), bytes(range(50, 90))
    r = Reassembler()
    r.feed(segment(a)[0], 0.0)
    fb = segment(b)
    r.feed(fb[0], 0.1)
    out = None
    for f in fb[1:]:
        out = r.feed(f, 0.2)
    assert out == b


def test_flow_control_roundtrip() -> None:
    fc = parse_flow_control(flow_control_frame(5, 0x0A))
    assert fc == FlowControl(status=0, block_size=5, stmin=0x0A)
    with pytest.raises(ProtocolError):
        parse_flow_control(bytes([0x20]) + bytes(7))
    with pytest.raises(ProtocolError):
        parse_flow_control(bytes([0x33]) + bytes(7))
    with pytest.raises(ProtocolError):
        flow_control_frame(256, 0)


@pytest.mark.parametrize(
    ("raw", "seconds"), [(0, 0.0), (1, 0.001), (0x7F, 0.127), (0xF1, 0.0001), (0xF9, 0.0009)]
)
def test_decode_stmin(raw: int, seconds: float) -> None:
    assert decode_stmin(raw) == pytest.approx(seconds)


@pytest.mark.parametrize("raw", [0x80, 0xF0, 0xFA, 0xFF])
def test_decode_stmin_reserved_is_max(raw: int) -> None:
    assert decode_stmin(raw) == pytest.approx(0.127)


def test_reassemble_incomplete_raises() -> None:
    with pytest.raises(ProtocolError):
        reassemble(segment(bytes(range(30)))[:2])
