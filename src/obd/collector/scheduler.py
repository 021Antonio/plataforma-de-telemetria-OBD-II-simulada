"""Plano de leitura: prioridade e taxa por PID, configuráveis em `config/default.yaml`."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "config" / "default.yaml"


@dataclass(frozen=True)
class PidRate:
    every: int = 1  # ciclos entre leituras (1 = todo ciclo)
    priority: int = 0  # menor vai primeiro

    def __post_init__(self) -> None:
        if self.every < 1:
            raise ValueError("a_cada deve ser >= 1")


@dataclass(frozen=True)
class BackoffConfig:
    threshold: int = 3
    base_ms: float = 50.0
    max_ms: float = 2000.0

    def delay(self, consecutive_failures: int) -> float:
        """Espera em segundos: 0 abaixo do limiar; depois dobra a cada falha, até o teto."""
        if consecutive_failures < self.threshold:
            return 0.0
        step = consecutive_failures - self.threshold
        return min(self.max_ms, self.base_ms * float(2 ** min(step, 30))) / 1000


@dataclass(frozen=True)
class CollectorConfig:
    transport: str = "loopback"
    interval_ms: float = 100.0
    timeout_ms: int = 100
    dtc_interval_s: float = 2.0
    backoff: BackoffConfig = BackoffConfig()
    plan: Mapping[int, PidRate] | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CollectorConfig:
        recuo = data.get("recuo", {})
        backoff = BackoffConfig(
            threshold=int(recuo.get("limiar", 3)),
            base_ms=float(recuo.get("base_ms", 50)),
            max_ms=float(recuo.get("max_ms", 2000)),
        )
        plan = {
            int(pid): PidRate(int(r.get("a_cada", 1)), int(r.get("prioridade", 0)))
            for pid, r in data.get("plano", {}).items()
        }
        return cls(
            transport=str(data.get("transporte", "loopback")),
            interval_ms=float(data.get("intervalo_ms", 100)),
            timeout_ms=int(data.get("timeout_ms", 100)),
            dtc_interval_s=float(data.get("dtc_intervalo_s", 2.0)),
            backoff=backoff,
            plan=plan or None,
        )

    @classmethod
    def from_yaml(cls, path: Path = DEFAULT_CONFIG) -> CollectorConfig:
        with path.open(encoding="utf-8") as f:
            return cls.from_dict(yaml.safe_load(f).get("coletor", {}))


class Scheduler:
    """Decide quais PIDs suportados são lidos em cada ciclo, em ordem de prioridade."""

    def __init__(self, rates: Mapping[int, PidRate], supported: Collection[int]) -> None:
        self._order = sorted(
            (pid for pid in rates if pid in supported), key=lambda p: (rates[p].priority, p)
        )
        self._rates = dict(rates)

    @property
    def pids(self) -> list[int]:
        return list(self._order)

    def for_cycle(self, cycle: int) -> list[int]:
        return [pid for pid in self._order if cycle % self._rates[pid].every == 0]
