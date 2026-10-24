"""Formatação das respostas do ELM327 simulado (ATH0/ATH1, espaços e ISO-TP em linhas)."""

import pytest

from obd.simulator.elm327_server import ECU_HEADER, format_response

SINGLE = bytes.fromhex("41009C3A8001")
VIN = bytes([0x49, 0x02, 0x01]) + b"9BWZZZ377VT004251"


def test_single_frame_without_headers() -> None:
    assert format_response(SINGLE, headers=False, spaces=True) == ["41 00 9C 3A 80 01"]
    assert format_response(SINGLE, headers=False, spaces=False) == ["41009C3A8001"]


def test_single_frame_with_headers() -> None:
    assert ECU_HEADER == "7E8"
    assert format_response(SINGLE, headers=True, spaces=True) == ["7E8 06 41 00 9C 3A 80 01"]
    assert format_response(SINGLE, headers=True, spaces=False) == ["7E80641009C3A8001"]


def test_short_single_frame_has_no_padding() -> None:
    assert format_response(bytes([0x44]), headers=True, spaces=True) == ["7E8 01 44"]


def test_multiframe_with_headers_is_one_line_per_frame() -> None:
    lines = format_response(VIN, headers=True, spaces=True)
    assert lines[0] == "7E8 10 14 49 02 01 39 42 57"
    assert lines[1] == "7E8 21 5A 5A 5A 33 37 37 56"
    assert lines[2] == "7E8 22 54 30 30 34 32 35 31"
    assert len(lines) == 3


def test_multiframe_without_headers_stays_reassembled() -> None:
    assert format_response(VIN, headers=False, spaces=False) == [VIN.hex().upper()]


@pytest.mark.parametrize("n", [8, 13, 20])
def test_multiframe_last_frame_is_not_padded(n: int) -> None:
    msg = bytes(range(n))
    lines = format_response(msg, headers=True, spaces=True)
    body = b"".join(bytes.fromhex(ln[4:])[1:] for ln in lines[1:])
    assert bytes.fromhex(lines[0][4:])[2:] + body == msg
