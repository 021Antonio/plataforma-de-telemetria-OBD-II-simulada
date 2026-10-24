"""Estatísticas dos ensaios (média, desvio, mediana, p95, p99, máximo) com vetores conhecidos."""

from __future__ import annotations

import math

import pytest

from benchmarks.stats import percentile, summarize


def test_stats_vetor_de_um_a_cinco() -> None:
    s = summarize([1, 2, 3, 4, 5])
    assert s.n == 5
    assert s.mean == 3.0
    assert s.std == pytest.approx(math.sqrt(2.5))  # desvio amostral
    assert s.median == 3.0
    assert s.p95 == 5.0
    assert s.p99 == 5.0
    assert s.max == 5.0


def test_stats_vetor_de_um_a_cem() -> None:
    s = summarize(list(range(100, 0, -1)))  # fora de ordem de propósito
    assert s.mean == 50.5
    assert s.median == 50.5
    assert s.p95 == 95.0
    assert s.p99 == 99.0
    assert s.max == 100.0


def test_stats_um_valor_tem_desvio_zero() -> None:
    s = summarize([7.5])
    assert (s.mean, s.std, s.median, s.p95, s.p99, s.max) == (7.5, 0.0, 7.5, 7.5, 7.5, 7.5)


def test_stats_vazio_levanta() -> None:
    with pytest.raises(ValueError):
        summarize([])


def test_stats_percentil_posto_mais_proximo() -> None:
    assert percentile([10.0, 20.0, 30.0, 40.0], 50) == 20.0
    assert percentile([10.0, 20.0, 30.0, 40.0], 100) == 40.0
    assert percentile([10.0, 20.0, 30.0, 40.0], 0) == 10.0


def test_stats_as_dict_tem_as_seis_medidas() -> None:
    assert set(summarize([1.0, 2.0]).as_dict()) == {
        "n",
        "mean",
        "std",
        "median",
        "p95",
        "p99",
        "max",
    }
