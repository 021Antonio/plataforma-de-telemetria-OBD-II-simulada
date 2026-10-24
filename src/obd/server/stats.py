"""Estatísticas de `GET /api/stats`, calculadas sobre as linhas de uma execução."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from obd.protocol.schemas import LatencyStats, Stats


@dataclass(frozen=True)
class SampleRow:
    seq: int
    ts_recv: float
    latency_ms: float


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    """Percentil por posto mais próximo (nearest-rank); `sorted_values` não vazio."""
    rank = math.ceil(pct / 100.0 * len(sorted_values))
    return sorted_values[max(rank, 1) - 1]


def compute_stats(
    rows: Sequence[SampleRow],
    *,
    duplicated: int,
    now: float,
    window_s: float = 3.0,
) -> Stats:
    """`rows` deve ter no máximo uma linha por `seq` (o armazenamento garante isso).

    Perdas são as lacunas entre o menor e o maior `seq` recebidos da execução.
    A taxa conta amostras com `ts_recv` dentro da janela de `window_s` segundos.
    """
    if not rows:
        zero = LatencyStats(mean=0.0, p95=0.0, p99=0.0, max=0.0)
        return Stats(received=0, lost=0, duplicated=duplicated, latency_ms=zero, update_rate_hz=0.0)

    seqs = [r.seq for r in rows]
    lost = max(seqs) - min(seqs) + 1 - len(rows)

    latencies = sorted(r.latency_ms for r in rows)
    latency = LatencyStats(
        mean=sum(latencies) / len(latencies),
        p95=_percentile(latencies, 95.0),
        p99=_percentile(latencies, 99.0),
        max=latencies[-1],
    )

    recent = sum(1 for r in rows if r.ts_recv > now - window_s)
    return Stats(
        received=len(rows),
        lost=lost,
        duplicated=duplicated,
        latency_ms=latency,
        update_rate_hz=recent / window_s,
    )
