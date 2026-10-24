import math
from pathlib import Path
from typing import Any

import pytest

from fakes import FakeClock
from obd.protocol.pids import PIDS
from obd.simulator.vehicle_model import (
    ATMOSPHERIC_KPA,
    DEFAULT_PROFILES_DIR,
    Profile,
    ProfileStep,
    VehicleConfig,
    VehicleModel,
    load_profile,
    rpm_formula,
)

PROFILES = ["parado", "urbano", "rodovia", "ciclo_120s", "esforco"]


def run(profile: str, seed: int, seconds: float, **cfg: Any) -> list[tuple[float, ...]]:
    clock = FakeClock()
    model = VehicleModel(load_profile(profile), clock, seed=seed, config=VehicleConfig(**cfg))
    out = []
    for _ in range(int(seconds * 10)):
        clock.advance(0.1)
        out.append(tuple(model.value(p) for p in sorted(PIDS)))
    return out


@pytest.mark.parametrize("name", PROFILES)
def test_shipped_profiles_load(name: str) -> None:
    profile = load_profile(name)
    assert profile.name == name
    assert profile.steps[0].t == 0
    assert (DEFAULT_PROFILES_DIR / f"{name}.yaml").exists()


def test_load_profile_from_path(tmp_path: Path) -> None:
    f = tmp_path / "x.yaml"
    f.write_text("name: x\nloop: false\nsteps:\n  - {t: 0, speed: 10, throttle: 0.1}\n")
    assert load_profile(f) == Profile("x", False, (ProfileStep(0, 10, 0.1),))


def test_unknown_profile_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_profile("nao_existe")


def test_ciclo_120s_is_120_seconds_and_reaches_80() -> None:
    profile = load_profile("ciclo_120s")
    assert profile.steps[-1].t == 120
    assert max(s.speed for s in profile.steps) == 80


def test_determinism_same_seeds_same_sequence() -> None:
    assert run("ciclo_120s", 7, 30) == run("ciclo_120s", 7, 30)


def test_different_seed_changes_noise() -> None:
    assert run("urbano", 1, 5) != run("urbano", 2, 5)


def test_no_noise_is_seed_independent() -> None:
    assert run("urbano", 1, 5, noise=0.0) == run("urbano", 2, 5, noise=0.0)


def test_value_independent_of_query_granularity() -> None:
    def trace(step: float) -> float:
        clock = FakeClock()
        model = VehicleModel(load_profile("urbano"), clock, seed=3)
        while clock.now < 20 - 1e-9:
            clock.advance(step)
            model.value(0x0D)
        return model.value(0x0C)

    assert trace(0.01) == trace(0.5) == trace(2.0)


@pytest.mark.parametrize("name", PROFILES)
def test_map_never_exceeds_atmospheric(name: str) -> None:
    for row in run(name, 5, 130):
        assert row[sorted(PIDS).index(0x0B)] <= ATMOSPHERIC_KPA


def test_coolant_follows_time_constant_towards_90() -> None:
    clock = FakeClock()
    cfg = VehicleConfig(noise=0.0, coolant_tau_s=20.0)
    model = VehicleModel(load_profile("parado"), clock, seed=0, config=cfg)
    assert model.value(0x05) == pytest.approx(25.0)
    clock.advance(20.0)
    expected = 90 - 65 * math.exp(-1)
    assert model.value(0x05) == pytest.approx(expected, abs=0.2)
    clock.advance(200.0)
    assert model.value(0x05) == pytest.approx(90.0, abs=0.01)


def test_rpm_formula_values() -> None:
    # 50 km/h, 3a marcha (1,41), final 4,06, pneu 0,30 m
    expected = (50 / 3.6) / 0.30 * 1.41 * 4.06 * 60 / (2 * math.pi)
    assert rpm_formula(50, 0.30, 1.41, 4.06) == pytest.approx(expected)
    assert rpm_formula(0, 0.30, 1.41, 4.06) == 0


def test_model_rpm_follows_formula_with_gear_and_tire() -> None:
    clock = FakeClock()
    cfg = VehicleConfig(noise=0.0)
    model = VehicleModel(load_profile("rodovia"), clock, seed=0, config=cfg)
    clock.advance(100.0)
    state = model.state
    assert state.gear >= 1
    expected = rpm_formula(
        state.speed, cfg.tire_radius_m, cfg.gear_ratios[state.gear - 1], cfg.final_drive
    )
    assert state.rpm == pytest.approx(max(expected, cfg.idle_rpm))
    assert state.rpm > cfg.idle_rpm


def test_idle_rpm_when_stopped() -> None:
    clock = FakeClock()
    model = VehicleModel(load_profile("parado"), clock, seed=0, config=VehicleConfig(noise=0.0))
    clock.advance(1.0)
    assert model.value(0x0C) == pytest.approx(800.0)
    assert model.value(0x0D) == 0
    assert model.value(0x42) == pytest.approx(14.1)


def test_speed_acceleration_is_limited() -> None:
    cfg = VehicleConfig(noise=0.0, max_accel_kmh_s=10.0)
    clock = FakeClock()
    model = VehicleModel(load_profile("urbano"), clock, seed=0, config=cfg)
    clock.advance(10.0)  # instante em que o perfil pede 50 km/h
    clock.advance(1.0)
    assert model.value(0x0D) <= 10.0 + 0.2
    clock.advance(30.0)
    assert model.value(0x0D) == pytest.approx(50.0)


def test_profile_loops() -> None:
    clock = FakeClock()
    model = VehicleModel(load_profile("urbano"), clock, seed=0, config=VehicleConfig(noise=0.0))
    clock.advance(62.0)  # 12 s da segunda volta: acelerando de novo (sem loop ficaria parado)
    assert model.value(0x0D) > 5.0


def test_fuel_level_decreases() -> None:
    clock = FakeClock()
    model = VehicleModel(load_profile("esforco"), clock, seed=0, config=VehicleConfig(noise=0.0))
    first = model.value(0x2F)
    clock.advance(60.0)
    assert model.value(0x2F) < first


def test_stft_oscillates_within_amplitude() -> None:
    values = [r[sorted(PIDS).index(0x06)] for r in run("parado", 1, 30, noise=0.0)]
    assert max(values) == pytest.approx(3.0, abs=0.1)
    assert min(values) == pytest.approx(-3.0, abs=0.1)


def test_override_replaces_and_releases() -> None:
    clock = FakeClock()
    model = VehicleModel(load_profile("parado"), clock, seed=0)
    model.set_override(0x0C, 4321.0)
    clock.advance(1.0)
    assert model.value(0x0C) == 4321.0
    model.set_override(0x0C, None)
    assert model.value(0x0C) != 4321.0


def test_unknown_pid_raises() -> None:
    model = VehicleModel(load_profile("parado"), FakeClock(), seed=0)
    with pytest.raises(KeyError):
        model.value(0x99)
    with pytest.raises(KeyError):
        model.set_override(0x99, 1.0)


def test_values_encodable_in_every_pid() -> None:
    for row in run("esforco", 1, 60):
        for pid, v in zip(sorted(PIDS), row, strict=True):
            PIDS[pid].encode(v)  # não levanta
            assert PIDS[pid].min_value - 1 <= v <= PIDS[pid].max_value
