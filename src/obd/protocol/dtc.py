"""Conversão entre DTC de 2 bytes e código textual (ex.: `03 00` <-> `P0300`)."""

from __future__ import annotations

import re

from obd.protocol.errors import ProtocolError

_SYSTEMS = "PCBU"
_CODE_RE = re.compile(r"^[PCBU][0-3][0-9A-F]{3}$")

DESCRIPTIONS: dict[str, str] = {
    "P0300": "Falha de ignição aleatória ou em múltiplos cilindros",
    "P0301": "Falha de ignição no cilindro 1",
    "P0302": "Falha de ignição no cilindro 2",
    "P0303": "Falha de ignição no cilindro 3",
    "P0304": "Falha de ignição no cilindro 4",
    "P0171": "Mistura pobre (banco 1)",
    "P0172": "Mistura rica (banco 1)",
    "P0420": "Eficiência do catalisador abaixo do limite (banco 1)",
    "P0133": "Resposta lenta do sensor de oxigênio (banco 1, sensor 1)",
}


def bytes_to_code(data: bytes) -> str:
    if len(data) != 2:
        raise ProtocolError(f"DTC exige 2 bytes, recebeu {len(data)}")
    a, b = data
    return f"{_SYSTEMS[a >> 6]}{(a >> 4) & 0x3}{a & 0xF:X}{b:02X}"


def code_to_bytes(code: str) -> bytes:
    code = code.upper()
    if not _CODE_RE.match(code):
        raise ProtocolError(f"código DTC inválido: {code!r}")
    a = (_SYSTEMS.index(code[0]) << 6) | (int(code[1]) << 4) | int(code[2], 16)
    return bytes([a, int(code[3:5], 16)])


def describe(code: str) -> str:
    return DESCRIPTIONS.get(code.upper(), "Descrição indisponível")
