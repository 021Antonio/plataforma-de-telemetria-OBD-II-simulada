"""Redesenho visual: tema único, sem recursos externos, abas do gráfico e monitor colorido."""

from __future__ import annotations

import re

import pytest

from obd.server.app import DASHBOARD_DIR
from obd.simulator.control_api import PANEL_DIR

PASTAS = [DASHBOARD_DIR, PANEL_DIR]
EXTERNA = re.compile(r"https?://(?!localhost|127\.0\.0\.1)", re.I)


@pytest.mark.parametrize("pasta", PASTAS, ids=["dashboard", "painel"])
def test_ativos_sem_url_externa(pasta) -> None:  # type: ignore[no-untyped-def]
    for arq in pasta.iterdir():
        if arq.suffix in {".html", ".css", ".js"}:
            texto = arq.read_text()
            assert not EXTERNA.search(texto), f"{arq.name} referencia URL externa"
            assert "@import" not in texto, arq.name


@pytest.mark.parametrize("pasta", PASTAS, ids=["dashboard", "painel"])
def test_sem_tema_escuro(pasta) -> None:  # type: ignore[no-untyped-def]
    css = (pasta / "style.css").read_text()
    assert "prefers-color-scheme: dark" not in css


def test_tokens_compartilhados_nos_dois_css() -> None:
    a = (DASHBOARD_DIR / "style.css").read_text()
    b = (PANEL_DIR / "style.css").read_text()
    for token in ("--azul", "--ambar", "--vermelho", "--espaco-2", "--raio"):
        assert token in a and token in b, token


def test_grafico_usa_abas_e_nao_lista_suspensa() -> None:
    html = (DASHBOARD_DIR / "index.html").read_text()
    assert 'role="tablist"' in html and html.count('role="tab"') >= 6
    assert "<select" not in html


def test_painel_tem_interruptor_e_monitor_com_sentidos() -> None:
    html = (PANEL_DIR / "index.html").read_text()
    css = (PANEL_DIR / "style.css").read_text()
    js = (PANEL_DIR / "panel.js").read_text()
    assert 'class="interruptor"' in html and 'id="sem-resposta"' in html
    assert "btn-primario" in html and "btn-secundario" in html
    assert "ui-monospace" in css and ".entrada" in css and ".saida" in css
    assert "entrada" in js and "saida" in js


def test_estados_distintos_no_cabecalho() -> None:
    css = (DASHBOARD_DIR / "style.css").read_text()
    for estado in ("connected", "reconnecting", "nodata"):
        assert f".{estado}" in css, estado
