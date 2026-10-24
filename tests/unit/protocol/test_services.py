import pytest

from obd.protocol.errors import ProtocolError
from obd.protocol.services import build_dtc_response, build_request, parse_response


def test_build_request() -> None:
    assert build_request(0x01, 0x0C) == b"\x01\x0c"
    assert build_request(0x03) == b"\x03"
    assert build_request(0x04) == b"\x04"
    assert build_request(0x07) == b"\x07"


@pytest.mark.parametrize(("mode", "pid"), [(0x02, None), (0x01, None), (0x03, 1), (0x01, 256)])
def test_build_request_invalid(mode: int, pid: int | None) -> None:
    with pytest.raises(ProtocolError):
        build_request(mode, pid)


def test_mode01_response() -> None:
    r = parse_response(bytes.fromhex("410C1F40"), build_request(1, 0x0C))
    assert (r.mode, r.pid, r.data) == (1, 0x0C, b"\x1f\x40")
    assert not r.is_negative


def test_wrong_pid_rejected() -> None:
    with pytest.raises(ProtocolError):
        parse_response(bytes.fromhex("410D3E"), build_request(1, 0x0C))


def test_wrong_mode_rejected() -> None:
    with pytest.raises(ProtocolError):
        parse_response(bytes.fromhex("430100"), build_request(1, 0x0C))


def test_wrong_data_length_rejected() -> None:
    with pytest.raises(ProtocolError):
        parse_response(bytes.fromhex("410C1F"))


def test_without_request_validates_mode_only() -> None:
    assert parse_response(bytes.fromhex("41FF01")).pid == 0xFF  # PID desconhecido passa


def test_dtc_response() -> None:
    r = parse_response(bytes.fromhex("430203000171"), build_request(3))
    assert r.dtcs == ("P0300", "P0171")
    assert parse_response(bytes.fromhex("4300")).dtcs == ()
    assert parse_response(bytes.fromhex("470103 00".replace(" ", ""))).dtcs == ("P0300",)


def test_dtc_count_mismatch() -> None:
    with pytest.raises(ProtocolError):
        parse_response(bytes.fromhex("43020300"))
    with pytest.raises(ProtocolError):
        parse_response(b"\x43")


def test_build_dtc_response_roundtrip() -> None:
    raw = build_dtc_response(0x03, ["P0300", "U0100"])
    assert raw == bytes.fromhex("43020300C100")
    assert parse_response(raw).dtcs == ("P0300", "U0100")
    with pytest.raises(ProtocolError):
        build_dtc_response(0x01, [])


def test_clear_response() -> None:
    assert parse_response(b"\x44", build_request(4)).mode == 4
    with pytest.raises(ProtocolError):
        parse_response(b"\x44\x00")


def test_negative_response() -> None:
    r = parse_response(bytes.fromhex("7F0112"), build_request(1, 0x0C))
    assert r.is_negative
    assert (r.mode, r.error_code) == (1, 0x12)


def test_negative_mismatch_and_length() -> None:
    with pytest.raises(ProtocolError):
        parse_response(bytes.fromhex("7F0312"), build_request(1, 0x0C))
    with pytest.raises(ProtocolError):
        parse_response(bytes.fromhex("7F01"))


def test_invalid_raw() -> None:
    for raw in (b"", b"\x99\x00", b"\x41\x0c"):
        with pytest.raises(ProtocolError):
            parse_response(raw)


def test_mode02_request_and_response() -> None:
    req = build_request(0x02, 0x0C)
    assert req == bytes([0x02, 0x0C, 0x00])
    r = parse_response(bytes([0x42, 0x0C, 0x00, 0x1F, 0x40]), req)
    assert (r.mode, r.pid, r.data) == (2, 0x0C, b"\x1f\x40")


def test_mode02_wrong_frame_or_pid_rejected() -> None:
    req = build_request(0x02, 0x0C)
    with pytest.raises(ProtocolError):
        parse_response(bytes([0x42, 0x0D, 0x00, 0x10]), req)
    with pytest.raises(ProtocolError):
        parse_response(bytes([0x42, 0x0C, 0x01, 0x1F, 0x40]), req)
    with pytest.raises(ProtocolError):
        parse_response(bytes([0x42, 0x0C, 0x00, 0x1F]), req)


def test_mode09_vin() -> None:
    from obd.protocol.services import build_vin_response

    req = build_request(0x09, 0x02)
    assert req == bytes([0x09, 0x02])
    raw = build_vin_response("1HGCM82633A004352")
    assert raw[:3] == bytes([0x49, 0x02, 0x01]) and len(raw) == 20
    r = parse_response(raw, req)
    assert (r.mode, r.pid, r.data) == (9, 2, b"1HGCM82633A004352")


def test_mode09_invalid_vin_or_response() -> None:
    from obd.protocol.services import build_vin_response

    with pytest.raises(ProtocolError):
        build_vin_response("CURTO")
    with pytest.raises(ProtocolError):
        parse_response(bytes([0x49, 0x02, 0x01]) + b"A" * 16, build_request(9, 2))
    with pytest.raises(ProtocolError):
        build_request(0x09, 0x04)
