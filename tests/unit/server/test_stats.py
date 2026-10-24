"""Estatísticas puras do servidor (docs/spec/05-api.md, `GET /api/stats`)."""

from __future__ import annotations

import pytest

from obd.server.stats import SampleRow, compute_stats


def _row(seq: int, ts_recv: float, latency_ms: float = 1.0) -> SampleRow:
    return SampleRow(seq=seq, ts_recv=ts_recv, latency_ms=latency_ms)


def test_sem_amostras_todas_as_contagens_sao_zero() -> None:
    stats = compute_stats([], duplicated=0, now=1000.0)

    assert stats.received == 0
    assert stats.lost == 0
    assert stats.update_rate_hz == 0.0
    assert stats.latency_ms.max == 0.0


def test_lacuna_de_seq_conta_como_perda() -> None:
    rows = [_row(0, 1000.0), _row(1, 1000.0), _row(2, 1000.0), _row(5, 1000.0), _row(6, 1000.0)]

    stats = compute_stats(rows, duplicated=0, now=1000.0)

    assert stats.received == 5
    assert stats.lost == 2  # faltam 3 e 4


def test_duplicatas_sao_repassadas_sem_alterar_recebidas() -> None:
    rows = [_row(0, 1000.0), _row(1, 1000.0)]

    stats = compute_stats(rows, duplicated=3, now=1000.0)

    assert stats.received == 2
    assert stats.duplicated == 3


def test_latencia_media_e_percentis_por_posto_mais_proximo() -> None:
    rows = [_row(i, 1000.0, latency_ms=float(i + 1)) for i in range(100)]

    latency = compute_stats(rows, duplicated=0, now=1000.0).latency_ms

    assert latency.mean == pytest.approx(50.5)
    assert latency.p95 == 95.0
    assert latency.p99 == 99.0
    assert latency.max == 100.0


def test_taxa_conta_amostras_da_janela_de_3_segundos() -> None:
    rows = [_row(0, 900.0), _row(1, 997.5), _row(2, 998.0), _row(3, 1000.0)]

    stats = compute_stats(rows, duplicated=0, now=1000.0, window_s=3.0)

    # Entram 997.5, 998.0 e 1000.0 (janela aberta em 997.0); 900.0 fica de fora.
    assert stats.update_rate_hz == pytest.approx(1.0)
