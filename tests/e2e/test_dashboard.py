"""Dashboard estático: servido em `/`, JavaScript válido e lógica pura testada com Node."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import AsyncIterator

import httpx
import pytest
from starlette.testclient import TestClient

from fakes import FakeClock, make_sample
from obd.server.app import DASHBOARD_DIR, create_app
from obd.server.storage import InMemoryStorage

JS_FILES = ["app.js", "gauges.js"]
node = pytest.mark.skipif(shutil.which("node") is None, reason="node ausente")


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(InMemoryStorage(), clock=FakeClock(start=1000.0))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as http:
        yield http


async def test_raiz_devolve_html(client: httpx.AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "<svg" in resp.text and "gauges.js" in resp.text and "app.js" in resp.text


@pytest.mark.parametrize("name", [*JS_FILES, "style.css"])
async def test_ativos_estaticos(client: httpx.AsyncClient, name: str) -> None:
    assert (await client.get(f"/{name}")).status_code == 200


async def test_api_nao_e_engolida_pelo_estatico(client: httpx.AsyncClient) -> None:
    assert (await client.get("/healthz")).status_code == 200


@node
@pytest.mark.parametrize("name", JS_FILES)
def test_javascript_sem_erro_de_sintaxe(name: str) -> None:
    done = subprocess.run(
        ["node", "--check", str(DASHBOARD_DIR / name)], capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr


def test_app_so_usa_ids_existentes_no_html() -> None:
    html = (DASHBOARD_DIR / "index.html").read_text()
    ids = set(re.findall(r'id="([^"]+)"', html))
    used = set(re.findall(r"""\$\(['"]([\w-]+)['"]\)""", (DASHBOARD_DIR / "app.js").read_text()))
    assert used, "app.js deveria buscar elementos por id"
    assert used <= ids, f"ids ausentes no HTML: {used - ids}"


def test_html_tem_todos_os_elementos_da_spec() -> None:
    html = (DASHBOARD_DIR / "index.html").read_text()
    for needed in (
        "rpm-gauge",
        "map-gauge",
        "speed",
        "coolant",
        "fuel",
        "bar-throttle",
        "bar-load",
        "bar-trim",
        "bar-voltage",
        "chart",
        "mil",
        "dtc-list",
        "conn-state",
        "rate",
        "cycle",
        "latency",
        "events",
        "overlay",
    ):
        assert f'id="{needed}"' in html, needed


def _run_node(script: str) -> object:
    done = subprocess.run(
        ["node", "-e", f"const g=require({json.dumps(str(DASHBOARD_DIR / 'gauges.js'))});{script}"],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@node
def test_angulo_do_ponteiro_e_limitado() -> None:
    out = _run_node(
        "console.log(JSON.stringify([g.needleAngle(0,0,8000),"
        "g.needleAngle(8000,0,8000),g.needleAngle(4000,0,8000),g.needleAngle(99999,0,8000)]))"
    )
    assert out == [-120, 120, 0, 120]


@node
def test_manometro_em_bar_relativo_com_vacuo_negativo() -> None:
    out = _run_node(
        "console.log(JSON.stringify([g.mapRelativeBar(101.325),g.mapRelativeBar(31.325),"
        "g.mapRelativeBar(201.325)]))"
    )
    assert out == [0, -0.7, 1]


@node
def test_cor_por_faixa() -> None:
    out = _run_node(
        "const z=[{max:90,color:'ok'},{max:105,color:'warn'},{max:Infinity,color:'bad'}];"
        "console.log(JSON.stringify([g.zoneColor(80,z),g.zoneColor(100,z),g.zoneColor(120,z)]))"
    )
    assert out == ["ok", "warn", "bad"]


@node
def test_janela_de_60_s_descarta_antigos() -> None:
    out = _run_node(
        "let s=[];for(const t of [0,10,50,61,70]) s=g.pushWindow(s,t,1,60);"
        "console.log(JSON.stringify(s.map(p=>p.t)))"
    )
    assert out == [10, 50, 61, 70]


@node
def test_taxa_na_janela_de_3_s() -> None:
    out = _run_node(
        "console.log(JSON.stringify([g.rateHz([9,9.5,10],10,3),g.rateHz([],10,3),"
        "g.rateHz([1,2],10,3)]))"
    )
    assert out == [1.0, 0, 0]


@node
def test_estado_da_conexao() -> None:
    out = _run_node(
        "console.log(JSON.stringify([g.connState(true,10,9),g.connState(true,10,1),"
        "g.connState(false,10,9),g.connState(true,10,null)]))"
    )
    assert out == ["connected", "nodata", "reconnecting", "nodata"]


def test_stream_entrega_amostra_ingerida() -> None:
    """O contrato que o dashboard consome: POST de amostra aparece no WS."""
    app = create_app(InMemoryStorage(), clock=FakeClock(start=1000.0))
    with TestClient(app) as http, http.websocket_connect("/ws/stream") as ws:
        sample = make_sample(seq=1, ts=1000.0)
        assert http.post("/api/ingest/sample", json=sample.model_dump()).status_code == 202
        msg = ws.receive_json()
        assert msg["type"] == "sample" and msg["data"]["seq"] == 1
