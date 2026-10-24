"""Painel de controle do simulador (porta 8001): API HTTP/WebSocket e interface estática.

`Simulator` junta modelo, ECU e falhas num só objeto que as rotas alteram. O relógio é injetado
e o objeto é mutado no lugar: reiniciar com outra semente reconstrói o interior, não a referência.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from obd.protocol.frames import CanFrame
from obd.simulator.ecu import Ecu
from obd.simulator.faults import FaultInjector
from obd.simulator.vehicle_model import (
    DEFAULT_PROFILES_DIR,
    VehicleConfig,
    VehicleModel,
    load_profile,
)

PANEL_DIR = Path(__file__).resolve().parents[1] / "web" / "simulator_panel"
# Variável controlável -> PID do modo 01 (faixa aceita = faixa codificável do PID)
VARIAVEIS: dict[str, int] = {
    "rpm": 0x0C,
    "speed": 0x0D,
    "coolant": 0x05,
    "throttle": 0x11,
    "fuel": 0x2F,
    "voltage": 0x42,
}
FAIXA_OVERRIDE: dict[str, tuple[float, float]] = {
    "rpm": (0.0, 16383.75),
    "speed": (0.0, 255.0),
    "coolant": (-40.0, 215.0),
    "throttle": (0.0, 100.0),
    "fuel": (0.0, 100.0),
    "voltage": (0.0, 65.535),
}
MAX_LATENCIA_MS = 1000
MAX_QUADROS = 200
PERIODO_STREAM_S = 0.1
DTC_PADRAO = r"^[PCBU][0-3][0-9A-F]{3}$"


class Simulator:
    """Estado mutável do simulador: modelo, ECU, falhas, sobreposições e monitor de quadros."""

    def __init__(
        self,
        clock: Callable[[], float] = time.time,
        *,
        profile: str = "urbano",
        seed_model: int = 0,
        seed_ecu: int = 0,
        config: VehicleConfig | None = None,
    ) -> None:
        self._clock = clock
        self._config = config
        self.perfil = profile
        self._construir(seed_model, seed_ecu)
        self.frames: deque[dict[str, Any]] = deque(maxlen=MAX_QUADROS)
        self._seq_quadro = 0

    def _construir(self, seed_model: int, seed_ecu: int) -> None:
        self.seed_model = seed_model
        self.seed_ecu = seed_ecu
        self.model = VehicleModel(
            load_profile(self.perfil), self._clock, seed=seed_model, config=self._config
        )
        self.faults = FaultInjector(seed=seed_ecu)
        self.ecu = Ecu(self.model, self._clock, seed=seed_ecu, faults=self.faults)
        self.latency: tuple[int, int] = (0, 0)
        self.overrides: dict[str, float] = {}
        self.dtcs: dict[str, bool] = {}  # código -> pendente

    # ---- configuração ----

    def set_profile(self, name: str) -> None:
        self.model.profile = load_profile(name)  # levanta FileNotFoundError/ValueError
        self.perfil = name

    def set_override(self, nome: str, value: float | None) -> None:
        pid = VARIAVEIS[nome]
        if value is None:
            self.overrides.pop(nome, None)
        else:
            self.overrides[nome] = value
        self.model.set_override(pid, value)

    def inject_dtc(self, code: str, *, pending: bool) -> None:
        self.ecu.add_dtc(code, pending=pending)  # valida o código
        self.dtcs[code] = pending

    def clear_dtcs(self) -> None:
        self.ecu.clear_dtcs()
        self.dtcs.clear()

    def set_latency(self, ms_min: int, ms_max: int) -> None:
        self.ecu.set_response_delay(ms_min, ms_max)
        self.latency = (ms_min, ms_max)

    def set_network(self, drop: float, corrupt: float) -> None:
        self.faults.set_frame_loss(drop)
        self.faults.set_corruption(corrupt)

    def set_unresponsive(self, on: bool) -> None:
        self.faults.set_mute(on)

    def reset(self, seed_model: int, seed_ecu: int) -> None:
        """Reinicia o veículo com as sementes dadas; perfil e monitor são mantidos."""
        self._construir(seed_model, seed_ecu)

    # ---- barramento (com monitor de quadros) ----

    def on_frame(self, can_id: int, data: bytes) -> None:
        self._registrar("->", can_id, data)
        self.ecu.on_frame(can_id, data)

    def poll(self) -> list[CanFrame]:
        quadros = self.ecu.poll()
        for quadro in quadros:
            self._registrar("<-", quadro.can_id, quadro.data)
        return quadros

    def _registrar(self, sentido: str, can_id: int, data: bytes) -> None:
        self._seq_quadro += 1
        self.frames.append(
            {
                "seq": self._seq_quadro,
                "sentido": sentido,
                "id": f"{can_id:03X}",
                "dados": data.hex(" ").upper(),
            }
        )

    # ---- leitura ----

    def snapshot(self) -> dict[str, Any]:
        return {
            "t": self._clock(),
            "perfil": self.perfil,
            "perfis": sorted(p.stem for p in DEFAULT_PROFILES_DIR.glob("*.yaml")),
            "sementes": {"modelo": self.seed_model, "ecu": self.seed_ecu},
            # valor que a ECU responde (com sobreposição), não o estado físico limpo
            "variaveis": {nome: self.model.value(pid) for nome, pid in VARIAVEIS.items()},
            "overrides": dict(self.overrides),
            "fisico": asdict(self.model.state),
            "dtcs": {
                "armazenados": sorted(c for c, p in self.dtcs.items() if not p),
                "pendentes": sorted(c for c, p in self.dtcs.items() if p),
            },
            "latencia": {"min": self.latency[0], "max": self.latency[1]},
            "rede": {"drop": self.faults.frame_loss, "corrupt": self.faults.corruption},
            "sem_resposta": self.faults.mute,
        }

    @property
    def ultimo_seq(self) -> int:
        return self._seq_quadro

    def quadros_desde(self, seq: int) -> list[dict[str, Any]]:
        return [q for q in self.frames if q["seq"] > seq]


# ---- corpos das requisições ----


class OverrideBody(BaseModel):
    value: float


class PerfilBody(BaseModel):
    name: str = Field(pattern=r"^[\w-]{1,64}$")


class DtcBody(BaseModel):
    code: str = Field(pattern=DTC_PADRAO)
    pending: bool = False


class LatenciaBody(BaseModel):
    min: int = Field(ge=0, le=MAX_LATENCIA_MS)
    max: int = Field(ge=0, le=MAX_LATENCIA_MS)

    @model_validator(mode="after")
    def _ordem(self) -> LatenciaBody:
        if self.min > self.max:
            raise ValueError("min não pode ser maior que max")
        return self


class RedeBody(BaseModel):
    drop: float = Field(ge=0.0, le=1.0)
    corrupt: float = Field(ge=0.0, le=1.0)


class SemRespostaBody(BaseModel):
    on: bool


class SementeBody(BaseModel):
    model: int = Field(ge=0, le=2**32 - 1)
    ecu: int = Field(ge=0, le=2**32 - 1)


def _variavel(nome: str) -> str:
    if nome not in VARIAVEIS:
        raise HTTPException(status_code=404, detail=f"variável desconhecida: {nome}")
    return nome


def build_control_router(sim: Simulator) -> APIRouter:
    router = APIRouter()

    @router.get("/sim/state")
    def estado() -> dict[str, Any]:
        return sim.snapshot()

    @router.put("/sim/override/{nome}")
    def definir_override(nome: str, body: OverrideBody) -> dict[str, Any]:
        low, high = FAIXA_OVERRIDE[_variavel(nome)]
        if not low <= body.value <= high:
            raise HTTPException(
                status_code=422,
                detail=f"{nome} fora de {low}..{high}: {body.value}",
            )
        sim.set_override(nome, body.value)
        return sim.snapshot()

    @router.delete("/sim/override/{nome}")
    def liberar_override(nome: str) -> dict[str, Any]:
        sim.set_override(_variavel(nome), None)
        return sim.snapshot()

    @router.post("/sim/profile")
    def trocar_perfil(body: PerfilBody) -> dict[str, Any]:
        try:
            sim.set_profile(body.name)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return sim.snapshot()

    @router.post("/sim/dtc")
    def injetar_dtc(body: DtcBody) -> dict[str, Any]:
        try:
            sim.inject_dtc(body.code, pending=body.pending)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return sim.snapshot()

    @router.delete("/sim/dtc")
    def limpar_dtcs() -> dict[str, Any]:
        sim.clear_dtcs()
        return sim.snapshot()

    @router.put("/sim/latency")
    def definir_latencia(body: LatenciaBody) -> dict[str, Any]:
        sim.set_latency(body.min, body.max)
        return sim.snapshot()

    @router.put("/sim/network")
    def definir_rede(body: RedeBody) -> dict[str, Any]:
        sim.set_network(body.drop, body.corrupt)
        return sim.snapshot()

    @router.post("/sim/unresponsive")
    def sem_resposta(body: SemRespostaBody) -> dict[str, Any]:
        sim.set_unresponsive(body.on)
        return sim.snapshot()

    @router.post("/sim/seed")
    def reiniciar(body: SementeBody) -> dict[str, Any]:
        sim.reset(body.model, body.ecu)
        return sim.snapshot()

    @router.websocket("/sim/stream")
    async def stream(ws: WebSocket) -> None:
        await ws.accept()
        ultimo = 0
        try:
            while True:
                quadros = sim.quadros_desde(ultimo)
                ultimo = sim.ultimo_seq
                await ws.send_json({"estado": sim.snapshot(), "quadros": quadros})
                await asyncio.sleep(PERIODO_STREAM_S)
        except (WebSocketDisconnect, RuntimeError):
            return

    return router


def create_control_app(
    sim: Simulator | None = None, clock: Callable[[], float] = time.time
) -> FastAPI:
    """Aplicação do painel de controle (porta 8001); `sim` vazio cria um simulador novo."""
    simulador = sim if sim is not None else Simulator(clock)
    app = FastAPI(title="Painel de controle do simulador")
    app.include_router(build_control_router(simulador))
    # Montado por último: o `/` estático não pode engolir as rotas da API.
    if PANEL_DIR.is_dir():
        app.mount("/", StaticFiles(directory=PANEL_DIR, html=True), name="painel")
    return app
