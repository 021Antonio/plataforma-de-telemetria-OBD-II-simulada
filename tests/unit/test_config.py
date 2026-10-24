from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = RAIZ / "config" / "default.yaml"


def _carrega() -> dict[str, Any]:
    with CONFIG.open(encoding="utf-8") as arquivo:
        dados = yaml.safe_load(arquivo)
    assert isinstance(dados, dict)
    return dados


def test_portas_padrao() -> None:
    portas = _carrega()["portas"]
    assert portas == {"servidor": 8000, "painel": 8001, "elm327_tcp": 35000}


def test_taxa_can_padrao() -> None:
    assert _carrega()["can"]["taxa_bps"] == 500000


def test_lista_de_pids_inclui_rpm_e_velocidade() -> None:
    pids = _carrega()["pids"]
    assert isinstance(pids, list) and pids
    assert all(isinstance(pid, int) and 0x00 <= pid <= 0xFF for pid in pids)
    assert 0x0C in pids  # rotação do motor
    assert 0x0D in pids  # velocidade do veículo
