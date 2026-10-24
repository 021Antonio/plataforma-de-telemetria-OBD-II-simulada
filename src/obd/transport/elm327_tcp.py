"""Cliente ELM327 por TCP: inicializa o adaptador e traduz texto hexadecimal em bytes."""

from __future__ import annotations

import asyncio
import contextlib
import re
from collections.abc import Awaitable, Callable

from obd.protocol.errors import ProtocolError

INIT_COMMANDS = ("ATZ", "ATE0", "ATL0", "ATS0", "ATH0", "ATSP0")
SEARCH_TIMEOUT_S = 5.0  # o primeiro 0100 procura o protocolo (SEARCHING...)
CONNECTION_LOST = "conexão perdida"
# Respostas do chip que significam falha de leitura, nunca dado (spec 09).
ADAPTER_ERRORS = (
    "UNABLE TO CONNECT",
    "BUS INIT: ERROR",
    "CAN ERROR",
    "STOPPED",
    "BUFFER FULL",
    "NO DATA",
    "?",
)
_ERROR_KEYS = {e.replace(" ", ""): e for e in ADAPTER_ERRORS}
_HEX_LINE = re.compile(r"(?:[0-9A-F]{2})+")
_MULTI_LINE = re.compile(r"\d+:(?P<data>[0-9A-F]+)")
_LENGTH_LINE = re.compile(r"[0-9A-F]{3}")

Sleep = Callable[[float], Awaitable[None]]


class Elm327TcpTransport:
    """Cliente ELM327 por TCP, tolerante a erros do chip, atrasos e quedas da conexão.

    Após cada `request`, `last_error` traz o erro do adaptador (`CAN ERROR`, `NO DATA`,
    `conexão perdida`, ...) ou `None` (resposta boa ou estouro de tempo)."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 35000,
        *,
        init_timeout_ms: int = 2000,
        search_timeout_s: float = SEARCH_TIMEOUT_S,
        reconnect_base_ms: float = 200.0,
        reconnect_max_ms: float = 5000.0,
        sleep: Sleep = asyncio.sleep,
    ):
        self._host = host
        self._port = port
        self._init_timeout = init_timeout_ms
        self._search_timeout_ms = int(search_timeout_s * 1000)
        self._reconnect_base_ms = reconnect_base_ms
        self._reconnect_max_ms = reconnect_max_ms
        self._sleep = sleep
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._searched = False
        self._wanted_open = False
        self._owed_prompt = False  # a resposta de uma consulta que estourou ainda está a caminho
        self._reconnect_failures = 0
        self.last_error: str | None = None

    @property
    def name(self) -> str:
        return "elm327_tcp"

    async def open(self) -> None:
        async with self._lock:
            self._wanted_open = True
            self._reconnect_failures = 0
            await self._connect()

    async def close(self) -> None:
        self._wanted_open = False
        await self._drop()

    async def request(self, payload: bytes, timeout_ms: int = 100) -> bytes | None:
        async with self._lock:
            self.last_error = None
            if not self._wanted_open:
                raise ProtocolError("transporte ELM327 não está aberto")
            if self._writer is None and not await self._reconnect():
                return None
            wait = timeout_ms if self._searched else max(timeout_ms, self._search_timeout_ms)
            text = await self._command(payload.hex().upper(), wait)
            if text is None:
                return None
            error = classify_reply(text)
            if error is not None:
                self.last_error = error
                return None
            self._searched = True
            return parse_reply(text)

    async def _connect(self) -> None:
        """Abre o soquete e envia a sequência de inicialização; falha com `ProtocolError`."""
        await self._drop()
        self._searched = False
        self._owed_prompt = False
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port), self._init_timeout / 1000
        )
        for cmd in INIT_COMMANDS:
            text = await self._command(cmd, self._init_timeout)
            if text is None or "?" in text.split():
                raise ProtocolError(f"adaptador ELM327 recusou {cmd}: {text!r}")

    async def _reconnect(self) -> bool:
        """Uma tentativa de reconexão, com recuo que dobra a cada falha seguida até o teto."""
        if self._reconnect_failures:
            step = min(self._reconnect_failures - 1, 30)
            await self._sleep(min(self._reconnect_max_ms, self._reconnect_base_ms * 2**step) / 1000)
        try:
            await self._connect()
        except (OSError, TimeoutError, ProtocolError, asyncio.IncompleteReadError):
            await self._drop()
            self._reconnect_failures += 1
            self.last_error = CONNECTION_LOST
            return False
        self._reconnect_failures = 0
        return True

    async def _drop(self) -> None:
        writer, self._reader, self._writer = self._writer, None, None
        if writer is not None:
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()

    async def _command(self, cmd: str, timeout_ms: int) -> str | None:
        """Envia o comando e lê até o prompt `>`; `None` se estourar o tempo ou a conexão cair."""
        if self._reader is None or self._writer is None:
            raise ProtocolError("transporte ELM327 não está aberto")
        try:
            if self._owed_prompt:  # descarta a resposta atrasada antes de mandar o próximo
                await asyncio.wait_for(self._reader.readuntil(b">"), timeout_ms / 1000)
                self._owed_prompt = False
            self._writer.write(cmd.encode("ascii") + b"\r")
            await self._writer.drain()
            raw = await asyncio.wait_for(self._reader.readuntil(b">"), timeout_ms / 1000)
        except TimeoutError:
            self._owed_prompt = True
            return None
        except (asyncio.IncompleteReadError, OSError):
            self.last_error = CONNECTION_LOST
            await self._drop()
            return None
        return raw[:-1].decode("latin-1")


def classify_reply(text: str) -> str | None:
    """Erro do adaptador contido na resposta (`CAN ERROR`, `NO DATA`, `?`...), ou `None`."""
    for ln in re.split(r"[\r\n]+", text):
        key = ln.replace(" ", "").upper()
        if key in _ERROR_KEYS:
            return _ERROR_KEYS[key]
    return None


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
