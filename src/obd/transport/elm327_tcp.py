"""Cliente ELM327 por TCP: inicializa o adaptador e traduz texto hexadecimal em bytes."""

from __future__ import annotations

import asyncio
import contextlib
import re

from obd.protocol.errors import ProtocolError

INIT_COMMANDS = ("ATZ", "ATE0", "ATL0", "ATS0", "ATSP0")
SEARCH_TIMEOUT_MS = 5000  # o primeiro 0100 procura o protocolo (SEARCHING...)
_HEX_LINE = re.compile(r"(?:[0-9A-F]{2})+")
_MULTI_LINE = re.compile(r"\d+:(?P<data>[0-9A-F]+)")
_LENGTH_LINE = re.compile(r"[0-9A-F]{3}")


class Elm327TcpTransport:
    def __init__(self, host: str = "localhost", port: int = 35000, *, init_timeout_ms: int = 2000):
        self._host = host
        self._port = port
        self._init_timeout = init_timeout_ms
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._searched = False

    @property
    def name(self) -> str:
        return "elm327_tcp"

    async def open(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        self._searched = False
        for cmd in INIT_COMMANDS:
            text = await self._command(cmd, self._init_timeout)
            if text is None or "?" in text.split():
                raise ProtocolError(f"adaptador ELM327 recusou {cmd}: {text!r}")

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            with contextlib.suppress(ConnectionError):
                await self._writer.wait_closed()
        self._reader = self._writer = None

    async def request(self, payload: bytes, timeout_ms: int = 100) -> bytes | None:
        async with self._lock:
            wait = timeout_ms if self._searched else max(timeout_ms, SEARCH_TIMEOUT_MS)
            text = await self._command(payload.hex().upper(), wait)
            if text is None:
                return None
            self._searched = True
            return parse_reply(text)

    async def _command(self, cmd: str, timeout_ms: int) -> str | None:
        """Envia o comando e lê até o prompt `>`; `None` se estourar o tempo ou a conexão cair."""
        if self._reader is None or self._writer is None:
            raise ProtocolError("transporte ELM327 não está aberto")
        self._writer.write(cmd.encode("ascii") + b"\r")
        try:
            await self._writer.drain()
            raw = await asyncio.wait_for(self._reader.readuntil(b">"), timeout_ms / 1000)
        except (TimeoutError, asyncio.IncompleteReadError, ConnectionError):
            return None
        return raw[:-1].decode("latin-1")


def parse_reply(text: str) -> bytes | None:
    """Converte a resposta do adaptador em bytes; `None` para NO DATA, `?` e erros do chip.

    Aceita a forma remontada (`41 0C 1F 40`) e a multilinha de adaptadores reais
    (`014`, `0: 49 02 01 ...`, `1: ...`)."""
    lines = [ln.replace(" ", "").upper() for ln in re.split(r"[\r\n]+", text)]
    lines = [ln for ln in lines if ln and ln not in ("SEARCHING...", "OK")]
    chunks = [m["data"] for ln in lines if (m := _MULTI_LINE.fullmatch(ln))]
    if chunks:
        return bytes.fromhex("".join(chunks))
    for ln in lines:
        if _HEX_LINE.fullmatch(ln) and not (_LENGTH_LINE.fullmatch(ln) and len(lines) > 1):
            return bytes.fromhex(ln)
    return None
