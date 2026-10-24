"""Servidor TCP no dialeto ELM327 (porta 35000) por cima de um transporte para a ECU simulada.

O `backend` recebe a requisição OBD e devolve a resposta já remontada pelo ISO-TP, que é o que o
chip real também entrega ao cliente (multiquadro numa só resposta).
"""

from __future__ import annotations

import asyncio
import contextlib
import re

from obd.protocol.isotp import segment
from obd.protocol.pids import PIDS
from obd.protocol.services import NEGATIVE
from obd.transport.base import Transport

PORT = 35000
VERSION = "ELM327 v1.5"
PROTOCOL = "ISO 15765-4 (CAN 11/500)"
DESCRIPTION = "OBD-II simulator (software-in-the-loop)"
ECU_HEADER = "7E8"
PROMPT = ">"
MAX_REQUEST = 7  # um quadro único ISO-TP
_VOLTAGE_PID = 0x42
_HEX = re.compile(r"[0-9A-F]+")
_AT_FLAGS = {"E": "echo", "L": "linefeed", "S": "spaces", "H": "headers"}
# Aceitos com `OK` e sem efeito: ATAT, ATST, ATSH, ATCAF, ATAL, ATCRA, ATD.
_AT_ACCEPTED = ("AT", "ST", "SH", "CAF", "CRA", "AL", "D")


class _Session:
    """Estado de uma conexão: opções de formatação e o `SEARCHING...` do primeiro `0100`."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.echo = True
        self.linefeed = False
        self.spaces = True
        self.headers = False
        self.searched = False
        self.auto = True  # ATSP0 (automático) ou ATSP6/ATTP6 (fixo)


class Elm327Server:
    def __init__(
        self,
        backend: Transport,
        *,
        host: str = "127.0.0.1",
        port: int = PORT,
        timeout_ms: int = 200,
    ) -> None:
        self._backend = backend
        self._host = host
        self._port = port
        self._timeout_ms = timeout_ms
        self._server: asyncio.Server | None = None
        self._writers: set[asyncio.StreamWriter] = set()

    @property
    def port(self) -> int:
        """Porta efetiva (útil quando `port=0`)."""
        if self._server is None or not self._server.sockets:
            return self._port
        return int(self._server.sockets[0].getsockname()[1])

    async def start(self) -> None:
        await self._backend.open()
        self._server = await asyncio.start_server(self._serve, self._host, self._port)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            for w in list(self._writers):
                w.close()
            await self._server.wait_closed()
            self._server = None
        await self._backend.close()

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._writers.add(writer)
        session = _Session()
        buf = b""
        try:
            while chunk := await reader.read(256):
                buf += chunk
                while (cut := _first_terminator(buf)) is not None:
                    raw, buf = buf[:cut], buf[cut + 1 :]
                    if raw.strip():
                        writer.write(await self._answer(session, raw.decode("latin-1")))
                        await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            self._writers.discard(writer)
            writer.close()
            with contextlib.suppress(ConnectionError):
                await writer.wait_closed()

    async def _answer(self, s: _Session, line: str) -> bytes:
        eol = "\r\n" if s.linefeed else "\r"
        cmd = line.replace(" ", "").upper()
        echoed = s.echo  # ATZ reinicia e não ecoa
        lines = await self._execute(s, cmd)
        echoed = echoed and cmd != "ATZ"
        out = line.strip() + eol if echoed else ""
        for text in lines:
            out += text + eol
        return (out + eol + PROMPT).encode("latin-1")

    async def _execute(self, s: _Session, cmd: str) -> list[str]:
        if cmd.startswith("AT"):
            return await self._at(s, cmd[2:])
        if not _HEX.fullmatch(cmd) or len(cmd) % 2 or not 1 <= len(cmd) // 2 <= MAX_REQUEST:
            return ["?"]
        payload = bytes.fromhex(cmd)
        prefix = []
        if cmd == "0100" and not s.searched:
            prefix = ["SEARCHING..."]
        s.searched = True
        resp = await self._backend.request(payload, self._timeout_ms)
        if resp is None or resp[0] == NEGATIVE or resp == bytes([0x43, 0x00]):
            return [*prefix, "NO DATA"]  # o chip real não repete a negativa da ECU
        return [*prefix, *format_response(resp, headers=s.headers, spaces=s.spaces)]

    async def _at(self, s: _Session, arg: str) -> list[str]:
        if arg == "Z":
            s.reset()
            return [VERSION]
        if arg == "DP":
            return [f"AUTO, {PROTOCOL}" if s.auto else PROTOCOL]
        if arg == "DPN":
            return ["A6" if s.auto else "6"]
        if arg == "RV":
            return [await self._voltage()]
        if arg == "@1":
            return [DESCRIPTION]
        if arg[:1] in _AT_FLAGS and arg[1:] in ("0", "1"):
            setattr(s, _AT_FLAGS[arg[0]], arg[1] == "1")
            return ["OK"]
        if arg[:2] in ("SP", "TP") and arg[2:].lstrip("A") in ("0", "6"):
            s.auto = arg[2:] == "0" or arg[2:3] == "A"
            return ["OK"]
        if arg.startswith(_AT_ACCEPTED):
            return ["OK"]
        return ["?"]

    async def _voltage(self) -> str:
        resp = await self._backend.request(bytes([0x01, _VOLTAGE_PID]), self._timeout_ms)
        if resp is None or len(resp) < 4:
            return "12.6V"
        return f"{PIDS[_VOLTAGE_PID].decode(resp[2:4]):.1f}V"


def _first_terminator(buf: bytes) -> int | None:
    hits = [i for i in (buf.find(b"\r"), buf.find(b"\n")) if i >= 0]
    return min(hits) if hits else None


def _hex(data: bytes, spaces: bool) -> str:
    return (data.hex(" ") if spaces else data.hex()).upper()


def format_response(resp: bytes, *, headers: bool, spaces: bool) -> list[str]:
    """Linhas de uma resposta: só os dados (`ATH0`) ou um quadro CAN por linha (`ATH1`).

    Com cabeçalhos vem o identificador da ECU e o quadro ISO-TP sem o preenchimento 0x55, como
    o chip real. Sem cabeçalhos a resposta multiquadro sai remontada em uma linha."""
    if not headers:
        return [_hex(resp, spaces)]
    lines = []
    for i, frame in enumerate(segment(resp)):
        used = len(frame) if frame[0] >> 4 == 1 else _frame_length(frame, resp, i)
        lines.append(_hex_row(frame[:used], spaces))
    return lines


def _frame_length(frame: bytes, resp: bytes, index: int) -> int:
    """Bytes úteis do SF (1 + N) ou do CF (1 + restante), sem o preenchimento."""
    if frame[0] >> 4 == 0:
        return 1 + frame[0]
    return 1 + min(7, len(resp) - 6 - 7 * (index - 1))


def _hex_row(frame: bytes, spaces: bool) -> str:
    return f"{ECU_HEADER} {_hex(frame, True)}" if spaces else ECU_HEADER + _hex(frame, False)
