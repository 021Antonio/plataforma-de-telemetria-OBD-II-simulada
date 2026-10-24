"""ECU virtual (ISO 15765-4): escuta 0x7DF e 0x7E0, responde em 0x7E8.

Máquina de estados dirigida por quadros e por relógio injetado: `on_frame` recebe o que chegou
no barramento e `poll` devolve os quadros que já estão devidos. Quem move os bytes (loopback ou
barramento CAN) fica fora, em `LoopbackTransport` e `EcuCanNode`.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
from collections.abc import Callable, Iterable
from typing import Protocol

import can

from obd.protocol import dtc, isotp
from obd.protocol.errors import ProtocolError
from obd.protocol.frames import (
    FRAME_SIZE,
    ID_ENGINE_RESPONSE,
    ID_FUNCTIONAL,
    ID_PHYSICAL_REQUEST,
    CanFrame,
)
from obd.protocol.pids import (
    MONITOR_STATUS_PID,
    PIDS,
    SUPPORT_PIDS,
    encode_monitor_status,
    encode_supported,
)
from obd.protocol.services import (
    MODE_CLEAR_DTC,
    MODE_CURRENT,
    MODE_FREEZE,
    MODE_PENDING_DTC,
    MODE_STORED_DTC,
    MODE_VEHICLE_INFO,
    NEGATIVE,
    PID_VIN,
    build_dtc_response,
    build_freeze_response,
    build_vin_response,
)
from obd.simulator.faults import FaultInjector

ID_PHYSICAL = ID_PHYSICAL_REQUEST[0]  # 0x7E0: endereço físico da ECU do motor
DEFAULT_VIN = "9BWZZZ377VT004251"
NRC_SERVICE_NOT_SUPPORTED = 0x11
NRC_SUBFUNCTION_NOT_SUPPORTED = 0x12
NRC_INCORRECT_LENGTH = 0x13
_EPS = 1e-9


class PidSource(Protocol):
    """Valor físico real de cada PID (`VehicleModel` e `FakeVehicleModel` o implementam)."""

    def value(self, pid: int) -> float: ...


def _negative(mode: int, code: int) -> bytes:
    return bytes([NEGATIVE, mode, code])


class Ecu:
    def __init__(
        self,
        model: PidSource,
        clock: Callable[[], float],
        *,
        pids: Iterable[int] | None = None,
        vin: str = DEFAULT_VIN,
        delay_ms: tuple[int, int] = (0, 0),
        seed: int = 0,
        faults: FaultInjector | None = None,
    ) -> None:
        self._model = model
        self._clock = clock
        self._vin = vin
        self._rng = random.Random(seed)
        self.faults = faults if faults is not None else FaultInjector(seed)
        self._delay_ms = (0, 0)
        self.set_response_delay(*delay_ms)
        self._pids: frozenset[int] = frozenset()
        self.set_supported_pids(PIDS if pids is None else pids)
        self._stored: list[str] = []
        self._pending: list[str] = []
        self._freeze: dict[int, bytes] = {}
        self._request_count = 0
        self._scheduled: tuple[float, bytes] | None = None
        self._sender: isotp.Sender | None = None
        self.log: list[tuple[int, float]] = []  # (request_id, valor físico verdadeiro)

    @property
    def clock(self) -> Callable[[], float]:
        return self._clock

    @property
    def pids(self) -> frozenset[int]:
        return self._pids

    def set_supported_pids(self, pids: Iterable[int]) -> None:
        wanted = frozenset(pids)
        unknown = wanted - PIDS.keys()
        if unknown:
            raise ValueError(f"PIDs não implementados: {sorted(unknown)}")
        self._pids = wanted

    def set_response_delay(self, ms_min: int, ms_max: int) -> None:
        if not 0 <= ms_min <= ms_max:
            raise ValueError(f"atraso inválido: ({ms_min}, {ms_max})")
        self._delay_ms = (ms_min, ms_max)

    def _active_pids(self) -> frozenset[int]:
        return self._pids - self.faults.unsupported

    def add_dtc(self, code: str, *, pending: bool = False) -> None:
        dtc.code_to_bytes(code)  # valida
        target = self._pending if pending else self._stored
        if code not in target:
            target.append(code)
        if not pending and not self._freeze:
            self._freeze = {
                pid: PIDS[pid].encode(self._model.value(pid)) for pid in self._active_pids()
            }

    def clear_dtcs(self) -> None:
        self._stored.clear()
        self._pending.clear()
        self._freeze.clear()

    # ---- ISO-TP / quadros ----

    def on_frame(self, can_id: int, data: bytes) -> None:
        if len(data) != FRAME_SIZE:
            return
        self._apply_due_dtcs()
        if self.faults.mute:
            self._drop_response()
            return
        if can_id == ID_PHYSICAL and data[0] >> 4 == isotp.PCI_FC:
            self._on_flow_control(data)
            return
        if can_id not in (ID_FUNCTIONAL, ID_PHYSICAL):
            return
        now = self._clock()
        try:
            payload = isotp.Reassembler().feed(data, now)
        except ProtocolError:
            return  # lixo no barramento: a ECU ignora
        if payload is None:
            return
        self._request_count += 1
        self._drop_response()
        if self.faults.drops():
            return
        response = self.process(payload, self._request_count)
        if response is not None:
            response = self.faults.corrupt(response)
            delay = self._rng.uniform(*(self.faults.delay_ms or self._delay_ms)) / 1000
            self._scheduled = (now + delay, response)

    def _drop_response(self) -> None:
        self._sender = None
        self._scheduled = None

    def _apply_due_dtcs(self) -> None:
        for d in self.faults.pop_due_dtcs(self._clock()):
            self.add_dtc(d.code, pending=d.pending)

    def _on_flow_control(self, data: bytes) -> None:
        if self._sender is None:
            return
        now = self._clock()
        try:
            self._sender.on_flow_control(self._shape_flow_control(data), now)
        except ProtocolError:
            if data[0] & 0xF == isotp.FC_OVERFLOW:
                self._sender = None

    def _shape_flow_control(self, data: bytes) -> bytes:
        """Aplica o atraso de ISO-TP injetado (STmin mínimo e BS máximo) ao FC do testador."""
        faults = self.faults
        if not (faults.stmin_ms or faults.block_size):
            return data
        fc = isotp.parse_flow_control(data)
        if fc.status != isotp.FC_CONTINUE:
            return data
        stmin_ms = round(isotp.decode_stmin(fc.stmin) * 1000)
        block = (
            min(fc.block_size, faults.block_size)
            if fc.block_size and faults.block_size
            else (fc.block_size or faults.block_size)
        )
        return isotp.flow_control_frame(block, max(stmin_ms, faults.stmin_ms))

    def poll(self) -> list[CanFrame]:
        """Quadros devidos neste instante (atraso vencido, CFs liberados pelo FC)."""
        self._apply_due_dtcs()
        if self.faults.mute:
            self._drop_response()
            return []
        now = self._clock()
        out: list[CanFrame] = []
        if self._scheduled is not None and now + _EPS >= self._scheduled[0]:
            message = self._scheduled[1]
            self._scheduled = None
            sender = isotp.Sender(message)
            out.append(CanFrame(ID_ENGINE_RESPONSE, sender.start(now)))
            self._sender = None if sender.done else sender
        if self._sender is not None:
            try:
                out.extend(CanFrame(ID_ENGINE_RESPONSE, f) for f in self._sender.poll(now))
            except isotp.IsoTpTimeout:
                self._sender = None
            else:
                if self._sender.done:
                    self._sender = None
        return out

    # ---- serviços ----

    def _advertised(self) -> frozenset[int]:
        found = set(self._active_pids()) | {MONITOR_STATUS_PID}
        for base in SUPPORT_PIDS[:-1]:
            if any(p > base + 0x20 for p in found):
                found.add(base + 0x20)
        return frozenset(found)

    def process(self, payload: bytes, request_id: int = 0) -> bytes | None:
        """Resposta de aplicação a uma requisição; `None` = silêncio."""
        if not payload:
            return None
        mode, n = payload[0], len(payload)
        if mode in self.faults.negative:
            return _negative(mode, self.faults.negative[mode])
        if mode == MODE_CURRENT:
            return self._mode01(payload, request_id) if n == 2 else self._bad_length(mode)
        if mode == MODE_FREEZE:
            return self._mode02(payload, request_id) if n == 3 else self._bad_length(mode)
        if mode in (MODE_STORED_DTC, MODE_PENDING_DTC, MODE_CLEAR_DTC):
            if n != 1:
                return self._bad_length(mode)
            if mode == MODE_CLEAR_DTC:
                self.clear_dtcs()
                return bytes([mode + 0x40])
            return build_dtc_response(
                mode, self._stored if mode == MODE_STORED_DTC else self._pending
            )
        if mode == MODE_VEHICLE_INFO:
            if n != 2:
                return self._bad_length(mode)
            if payload[1] == 0x00:  # máscara do Modo 09: só o PID 0x02 (VIN)
                return bytes([mode + 0x40, 0x00, 0x40, 0x00, 0x00, 0x00])
            if payload[1] != PID_VIN:
                return _negative(mode, NRC_SUBFUNCTION_NOT_SUPPORTED)
            return build_vin_response(self._vin)
        return _negative(mode, NRC_SERVICE_NOT_SUPPORTED)

    @staticmethod
    def _bad_length(mode: int) -> bytes:
        return _negative(mode, NRC_INCORRECT_LENGTH)

    def _mode01(self, payload: bytes, request_id: int) -> bytes | None:
        pid = payload[1]
        head = bytes([MODE_CURRENT + 0x40, pid])
        if pid in SUPPORT_PIDS:
            advertised = self._advertised()
            if pid != SUPPORT_PIDS[0] and pid not in advertised:
                return None
            return head + encode_supported(pid, advertised)
        if pid == MONITOR_STATUS_PID:
            return head + encode_monitor_status(bool(self._stored), len(self._stored))
        if pid not in self._active_pids():
            return None
        value = self._model.value(pid)
        self.log.append((request_id, value))
        return head + PIDS[pid].encode(value)

    def _mode02(self, payload: bytes, request_id: int) -> bytes | None:
        pid, frame_no = payload[1], payload[2]
        if frame_no != 0 or pid not in self._freeze:
            return None
        return build_freeze_response(pid, self._freeze[pid])


class EcuCanNode:
    """Liga uma `Ecu` a um barramento python-can: lê 0x7DF/0x7E0 e transmite em 0x7E8."""

    def __init__(
        self,
        ecu: Ecu,
        bus: can.BusABC,
        *,
        interval: float = 0.0005,
    ) -> None:
        self._ecu = ecu
        self._bus = bus
        self._interval = interval
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def step(self) -> None:
        while (msg := self._bus.recv(0)) is not None:
            if not msg.is_extended_id:
                self._ecu.on_frame(msg.arbitration_id, bytes(msg.data))
        for f in self._ecu.poll():
            self._bus.send(can.Message(arbitration_id=f.can_id, data=f.data, is_extended_id=False))

    async def _run(self) -> None:
        while True:
            self.step()
            await asyncio.sleep(self._interval)
