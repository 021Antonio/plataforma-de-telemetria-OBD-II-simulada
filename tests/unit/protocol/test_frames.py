import pytest

from obd.protocol.errors import ProtocolError
from obd.protocol.frames import CanFrame, build_frame, frame_bits, frame_time_us, is_valid_id, pad


def test_padding() -> None:
    f = build_frame(0x7DF, bytes([0x02, 0x01, 0x0C]))
    assert f.data == bytes([0x02, 0x01, 0x0C, 0x55, 0x55, 0x55, 0x55, 0x55])


def test_no_padding_needed() -> None:
    assert pad(bytes(8)) == bytes(8)


def test_invalid_dlc() -> None:
    with pytest.raises(ProtocolError):
        build_frame(0x7DF, bytes(9))
    with pytest.raises(ProtocolError):
        CanFrame(0x7DF, bytes(7))


@pytest.mark.parametrize("can_id", [0x7DF, 0x7E0, 0x7E7, 0x7E8])
def test_valid_ids(can_id: int) -> None:
    assert is_valid_id(can_id)
    build_frame(can_id, b"\x01")


@pytest.mark.parametrize("can_id", [0x000, 0x7DE, 0x7E9, 0x800])
def test_invalid_ids(can_id: int) -> None:
    assert not is_valid_id(can_id)
    with pytest.raises(ProtocolError):
        build_frame(can_id, b"\x01")


def test_frame_time() -> None:
    assert frame_bits(8) == 135
    assert frame_time_us(8) == pytest.approx(270.0)
    assert frame_bits(0) == 47 + 8
    with pytest.raises(ProtocolError):
        frame_bits(9)
