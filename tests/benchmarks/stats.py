"""Estatísticas reportadas nos ensaios: média, desvio, mediana, p95, p99 e máximo."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Summary:
    n: int
    mean: float
    std: float  # desvio padrão amostral (n - 1); 0 com um só valor
    median: float
    p95: float
    p99: float
    max: float

    def as_dict(self) -> dict[str, float]:
        return {k: float(v) for k, v in asdict(self).items()}


def percentile(sorted_values: Sequence[float], pct: float) -> float:
    """Posto mais próximo (o mesmo critério de `GET /api/stats`); entrada ordenada e não vazia."""
    rank = math.ceil(pct / 100.0 * len(sorted_values))
    return sorted_values[max(rank, 1) - 1]


def summarize(values: Sequence[float]) -> Summary:
    if not values:
        raise ValueError("sem valores para resumir")
    ordered = sorted(values)
    return Summary(
        n=len(ordered),
        mean=statistics.fmean(ordered),
        std=statistics.stdev(ordered) if len(ordered) > 1 else 0.0,
        median=statistics.median(ordered),
        p95=percentile(ordered, 95.0),
        p99=percentile(ordered, 99.0),
        max=ordered[-1],
    )
