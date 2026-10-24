import pytest
from hypothesis import given
from hypothesis import strategies as st

from obd.protocol import dtc
from obd.protocol.errors import ProtocolError


def test_known_vector() -> None:
    assert dtc.bytes_to_code(bytes([0x03, 0x00])) == "P0300"
    assert dtc.code_to_bytes("P0300") == bytes([0x03, 0x00])


@pytest.mark.parametrize(
    ("code", "raw"),
    [("P0171", "0171"), ("C0123", "4123"), ("B1234", "9234"), ("U3FFF", "FFFF")],
)
def test_all_systems(code: str, raw: str) -> None:
    assert dtc.bytes_to_code(bytes.fromhex(raw)) == code
    assert dtc.code_to_bytes(code) == bytes.fromhex(raw)


@given(st.binary(min_size=2, max_size=2))
def test_roundtrip_all_bytes(raw: bytes) -> None:
    assert dtc.code_to_bytes(dtc.bytes_to_code(raw)) == raw


@pytest.mark.parametrize("bad", ["", "P030", "X0300", "P4000", "P03G0", "P03000"])
def test_invalid_code(bad: str) -> None:
    with pytest.raises(ProtocolError):
        dtc.code_to_bytes(bad)


def test_invalid_length() -> None:
    with pytest.raises(ProtocolError):
        dtc.bytes_to_code(b"\x01")


def test_descriptions() -> None:
    for code in ["P0300", "P0301", "P0302", "P0303", "P0304", "P0171", "P0172", "P0420", "P0133"]:
        assert dtc.DESCRIPTIONS[code]
    assert dtc.describe("p0300") == dtc.DESCRIPTIONS["P0300"]
    assert dtc.describe("P0999") == "Descrição indisponível"
