"""Modelo físico do veículo (seção 6 da spec): passo fixo de 10 ms, dirigido pelo relógio injetado.

`value(pid)` avança o modelo até `clock()` e devolve o valor físico do PID, com ruído gaussiano
de semente fixa. O resultado só depende da semente, do perfil e do tempo, nunca de quando ou
quantas vezes se consulta.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

STEP_S = 0.01
ATMOSPHERIC_KPA = 101.0
DEFAULT_PROFILES_DIR = Path(__file__).resolve().parents[3] / "config" / "profiles"
DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "config" / "default.yaml"

# PID -> (limite inferior, limite superior) do valor reportado
_BOUNDS: dict[int, tuple[float, float]] = {
    0x04: (0.0, 100.0),
    0x05: (-40.0, 215.0),
    0x06: (-100.0, 99.2),
    0x0B: (0.0, ATMOSPHERIC_KPA),
    0x0C: (0.0, 16383.75),
    0x0D: (0.0, 255.0),
    0x0F: (-40.0, 215.0),
    0x11: (0.0, 100.0),
    0x2F: (0.0, 100.0),
    0x42: (0.0, 65.535),
}
# desvio-padrão do ruído por PID (combustível não tem ruído)
_SIGMA: dict[int, float] = {
    0x04: 0.3,
    0x05: 0.05,
    0x06: 0.1,
    0x0B: 0.3,
    0x0C: 8.0,
    0x0D: 0.2,
    0x0F: 0.05,
    0x11: 0.2,
    0x2F: 0.0,
    0x42: 0.02,
}


def rpm_formula(
    speed_kmh: float, tire_radius_m: float, gear_ratio: float, final_drive: float
) -> float:
    """n = (v/3,6)/r · i_marcha · i_final · 60/(2π)."""
    return speed_kmh / 3.6 / tire_radius_m * gear_ratio * final_drive * 60 / (2 * math.pi)


@dataclass(frozen=True)
class VehicleConfig:
    tire_radius_m: float = 0.30
    final_drive: float = 4.06
    gear_ratios: tuple[float, ...] = (3.62, 2.19, 1.41, 1.03, 0.81)
    shift_kmh: tuple[float, ...] = (25.0, 45.0, 65.0, 85.0)  # velocidade de entrada da marcha 2..5
    idle_rpm: float = 800.0
    redline_rpm: float = 6500.0
    max_accel_kmh_s: float = 10.0
    max_decel_kmh_s: float = 15.0
    ambient_c: float = 25.0
    coolant_target_c: float = 90.0
    coolant_tau_s: float = 120.0
    stft_amplitude: float = 3.0
    stft_period_s: float = 5.0
    fuel_start_pct: float = 75.0
    fuel_rate: float = 1e-4  # % de tanque por (% de carga · s)
    engine_on: bool = True
    noise: float = 1.0  # multiplicador do ruído; 0 desliga

    def __post_init__(self) -> None:
        if len(self.shift_kmh) != len(self.gear_ratios) - 1:
            raise ValueError("shift_kmh deve ter uma entrada a menos que gear_ratios")
        if self.coolant_tau_s <= 0 or self.tire_radius_m <= 0:
            raise ValueError("coolant_tau_s e tire_radius_m devem ser positivos")

    @classmethod
    def from_yaml(cls, path: Path = DEFAULT_CONFIG) -> VehicleConfig:
        """Lê a seção `veiculo` de `config/default.yaml`; chaves ausentes ficam no padrão."""
        with path.open(encoding="utf-8") as f:
            section: Mapping[str, Any] = (yaml.safe_load(f) or {}).get("veiculo", {})
        names = {
            "raio_pneu_m": "tire_radius_m",
            "relacao_final": "final_drive",
            "marcha_lenta_rpm": "idle_rpm",
            "tau_arrefecimento_s": "coolant_tau_s",
            "temperatura_ambiente_c": "ambient_c",
        }
        kw: dict[str, Any] = {names[k]: v for k, v in section.items() if k in names}
        if "relacoes_marcha" in section:
            kw["gear_ratios"] = tuple(section["relacoes_marcha"])
        return cls(**kw)


@dataclass(frozen=True)
class ProfileStep:
    t: float
    speed: float
    throttle: float


@dataclass(frozen=True)
class Profile:
    name: str
    loop: bool
    steps: tuple[ProfileStep, ...]

    def at(self, t: float) -> ProfileStep:
        """Passo vigente em `t` (degrau: vale até o próximo instante); com `loop`, dá a volta."""
        end = self.steps[-1].t
        if self.loop and end > 0:
            t %= end
        current = self.steps[0]
        for step in self.steps:
            if step.t > t:
                break
            current = step
        return current


def load_profile(name_or_path: str | Path, directory: Path = DEFAULT_PROFILES_DIR) -> Profile:
    path = Path(name_or_path)
    if path.suffix != ".yaml":
        path = directory / f"{name_or_path}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"perfil de condução não encontrado: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    steps = tuple(
        ProfileStep(float(s["t"]), float(s["speed"]), float(s["throttle"])) for s in data["steps"]
    )
    if (
        not steps
        or steps[0].t != 0
        or any(a.t >= b.t for a, b in zip(steps, steps[1:], strict=False))
    ):
        raise ValueError(f"perfil {path.name}: passos devem começar em t=0 e ser crescentes")
    return Profile(str(data["name"]), bool(data.get("loop", False)), steps)


@dataclass
class VehicleState:
    """Estado físico limpo (sem ruído); referência de verdade do modelo."""

    speed: float = 0.0
    gear: int = 1
    rpm: float = 0.0
    throttle: float = 0.0
    load: float = 0.0
    map_kpa: float = 0.0
    coolant: float = 0.0
    intake: float = 0.0
    stft: float = 0.0
    fuel: float = 0.0
    voltage: float = 0.0


class VehicleModel:
    """Implementa `PidSource` da ECU: `value(pid)` em unidades físicas."""

    def __init__(
        self,
        profile: Profile,
        clock: Callable[[], float],
        *,
        seed: int = 0,
        config: VehicleConfig | None = None,
    ) -> None:
        self.profile = profile
        self.config = config or VehicleConfig()
        self._clock = clock
        self._t0 = clock()
        self._rng = random.Random(seed)
        self._n = 0
        self._overrides: dict[int, float] = {}
        cfg = self.config
        self._state = VehicleState(
            coolant=cfg.ambient_c, fuel=cfg.fuel_start_pct, voltage=self._voltage()
        )
        self._update_derived()
        self._reported: dict[int, float] = {}
        self._add_noise()

    @property
    def state(self) -> VehicleState:
        """Estado físico limpo no instante do relógio."""
        self._sync()
        return self._state

    def pids(self) -> frozenset[int]:
        return frozenset(_BOUNDS)

    def set_override(self, pid: int, value: float | None) -> None:
        """Fixa o valor reportado de um PID (`None` libera)."""
        if pid not in _BOUNDS:
            raise KeyError(pid)
        if value is None:
            self._overrides.pop(pid, None)
        else:
            self._overrides[pid] = value

    def value(self, pid: int) -> float:
        if pid not in _BOUNDS:
            raise KeyError(pid)
        self._sync()
        return self._overrides.get(pid, self._reported[pid])

    # ---- dinâmica ----

    def _sync(self) -> None:
        target = int((self._clock() - self._t0) / STEP_S + 1e-9)
        while self._n < target:
            self._step()

    def _voltage(self) -> float:
        return 14.1 if self.config.engine_on else 12.4

    def _gear(self, speed: float) -> int:
        return 1 + sum(speed >= s for s in self.config.shift_kmh)

    def _step(self) -> None:
        cfg, s = self.config, self._state
        self._n += 1
        t = self._n * STEP_S
        want = self.profile.at(t)
        delta = want.speed - s.speed
        limit = (cfg.max_accel_kmh_s if delta > 0 else cfg.max_decel_kmh_s) * STEP_S
        s.speed = max(0.0, s.speed + max(-limit, min(limit, delta)))
        s.throttle = want.throttle * 100
        s.coolant += (cfg.coolant_target_c - s.coolant) * (
            1 - math.exp(-STEP_S / cfg.coolant_tau_s)
        )
        self._update_derived()
        s.fuel = max(0.0, s.fuel - cfg.fuel_rate * s.load * STEP_S)
        s.stft = cfg.stft_amplitude * math.sin(2 * math.pi * t / cfg.stft_period_s)
        self._add_noise()

    def _update_derived(self) -> None:
        cfg, s = self.config, self._state
        s.gear = self._gear(s.speed)
        raw = rpm_formula(s.speed, cfg.tire_radius_m, cfg.gear_ratios[s.gear - 1], cfg.final_drive)
        s.rpm = min(cfg.redline_rpm, max(cfg.idle_rpm, raw)) if cfg.engine_on else 0.0
        s.load = 15 + 85 * (s.throttle / 100) * (0.4 + 0.6 * min(s.rpm / 6000, 1))
        s.map_kpa = min(ATMOSPHERIC_KPA, 28 + 0.73 * s.load)
        s.intake = cfg.ambient_c + 0.12 * (s.coolant - cfg.ambient_c)
        s.voltage = self._voltage()

    def _add_noise(self) -> None:
        s = self._state
        clean = {
            0x04: s.load,
            0x05: s.coolant,
            0x06: s.stft,
            0x0B: s.map_kpa,
            0x0C: s.rpm,
            0x0D: s.speed,
            0x0F: s.intake,
            0x11: s.throttle,
            0x2F: s.fuel,
            0x42: s.voltage,
        }
        for pid in sorted(clean):  # ordem fixa: o consumo da semente é determinístico
            sigma = _SIGMA[pid] * self.config.noise
            noisy = clean[pid] + (self._rng.gauss(0.0, sigma) if sigma else 0.0)
            lo, hi = _BOUNDS[pid]
            self._reported[pid] = max(lo, min(hi, noisy))
