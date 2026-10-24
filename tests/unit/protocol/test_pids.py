import pytest
from hypothesis import given
from hypothesis import strategies as st

from obd.protocol.errors import ProtocolError
from obd.protocol.pids import (
    PIDS,
    decode_monitor_status,
    decode_supported,
    encode_monitor_status,
    encode_supported,
    get_pid,
)

VECTORS = [
    (0x0C, "1F40", 2000.0),
    (0x05, "7B", 83.0),
    (0x0D, "3E", 62.0),
    (0x0B, "65", 101.0),
    (0x42, "3138", 12.600),
    (0x04, "FF", 100.0),
    (0x06, "80", 0.0),
    (0x0F, "28", 0.0),
]


@pytest.mark.parametrize(("pid", "hexdata", "expected"), VECTORS)
def test_known_vectors(pid: int, hexdata: str, expected: float) -> None:
    assert PIDS[pid].decode(bytes.fromhex(hexdata)) == pytest.approx(expected)


@pytest.mark.parametrize("pid", sorted(PIDS))
@given(i=st.integers(min_value=0, max_value=1000))
def test_roundtrip_within_half_resolution(pid: int, i: int) -> None:
    d = PIDS[pid]
    x = d.min_value + (d.max_value - d.min_value) * i / 1000  # 1.001 valores
    out = d.decode(d.encode(x))
    assert abs(out - x) <= d.resolution / 2 + 1e-9
    assert len(d.encode(x)) == d.n_bytes


def test_encode_saturates() -> None:
    d = PIDS[0x0D]
    assert d.encode(-5) == b"\x00"
    assert d.encode(9999) == b"\xff"


def test_decode_wrong_length() -> None:
    with pytest.raises(ProtocolError):
        PIDS[0x0C].decode(b"\x00")


def test_unknown_pid() -> None:
    with pytest.raises(ProtocolError):
        get_pid(0x99)


def test_supported_mask_vector() -> None:
    data = bytes.fromhex("BE3FA813")
    pids = decode_supported(0x00, data)
    assert {0x01, 0x03, 0x04, 0x05, 0x06, 0x07, 0x0B, 0x0C, 0x0D, 0x0F, 0x11} <= pids
    assert 0x02 not in pids
    assert encode_supported(0x00, pids) == data


@given(st.sets(st.integers(min_value=0x21, max_value=0x40)))
def test_supported_mask_roundtrip(pids: set[int]) -> None:
    assert decode_supported(0x20, encode_supported(0x20, pids)) == pids


def test_supported_mask_errors() -> None:
    with pytest.raises(ProtocolError):
        encode_supported(0x01, [])
    with pytest.raises(ProtocolError):
        decode_supported(0x00, b"\x00")
    with pytest.raises(ProtocolError):
        decode_supported(0x01, bytes(4))


def test_monitor_status() -> None:
    s = decode_monitor_status(bytes([0x82, 0x07, 0xE5, 0x00]))
    assert s.mil is True
    assert s.dtc_count == 2
    assert decode_monitor_status(bytes(4)).mil is False
    assert decode_monitor_status(encode_monitor_status(True, 5)).dtc_count == 5
    with pytest.raises(ProtocolError):
        decode_monitor_status(b"\x00")
    with pytest.raises(ProtocolError):
        encode_monitor_status(False, 128)
