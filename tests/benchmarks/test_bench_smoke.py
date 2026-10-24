"""Ensaio curto (10 s) de ponta a ponta: simulador, coletor e servidor HTTP no ar."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pytest

from benchmarks import e1
from benchmarks.runner import truth_series
from obd.protocol.pids import PIDS

pytestmark = pytest.mark.filterwarnings("ignore::ResourceWarning")


async def test_smoke_e1_curto_gera_csv_json_e_banco(tmp_path: Path) -> None:
    out = await e1.run(tmp_path, duration=10.0)

    rows = list(csv.DictReader((tmp_path / "e1.csv").open(encoding="utf-8")))
    assert len(rows) > 500  # ~10 ciclos/s x 10 PIDs x 10 s, com folga
    assert {"run", "seq", "pid", "name", "value", "true_value", "error", "resolution"} <= set(
        rows[0]
    )
    assert all(r["true_value"] != "" for r in rows)
    for r in rows:
        assert abs(float(r["value"]) - float(r["true_value"])) <= float(r["resolution"]) / 2 + 1e-9

    doc = json.loads((tmp_path / "e1.json").read_text(encoding="utf-8"))
    assert doc["ensaio"] == "E1"
    assert doc["runs"][0]["config"]["seed_model"] == e1.SEED_MODEL
    assert doc["runs"][0]["config"]["seed_ecu"] == e1.SEED_ECU
    assert doc["maquina"]["python"]
    metrics = doc["runs"][0]["metrics"]
    assert metrics["perdas"] == 0
    assert metrics["duplicacoes"] == 0
    assert metrics["timeouts"] == 0
    assert metrics["erro_acima_de_meia_resolucao"] == 0
    assert 0 < metrics["deteccao_falha_s"] < 5  # P0300 agendado a 100/240 da duração
    assert set(metrics["por_pid"]) == {p.name for p in PIDS.values()}

    assert out["runs"][0]["metrics"]["leituras"] == len(rows)

    with sqlite3.connect(tmp_path / "e1_run1.db") as db:
        filled = db.execute("SELECT COUNT(*) FROM readings WHERE true_value IS NOT NULL").fetchone()
        total = db.execute("SELECT COUNT(*) FROM readings").fetchone()
    assert filled[0] == total[0] == len(rows)


def test_smoke_mesmas_sementes_mesma_sequencia_de_valores_reais() -> None:
    a = truth_series(seed_model=3, seed_ecu=5, duration=5.0)
    b = truth_series(seed_model=3, seed_ecu=5, duration=5.0)
    c = truth_series(seed_model=4, seed_ecu=5, duration=5.0)
    assert a == b
    assert a != c
    assert len(a) > 100
