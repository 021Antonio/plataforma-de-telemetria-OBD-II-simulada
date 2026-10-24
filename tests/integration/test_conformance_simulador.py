"""A suíte de conformidade contra o simulador (0 divergências) e contra servidores defeituosos."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conformance.executor import DOURADO, carregar_dourado, executar
from conformance.gerar import gerar, servidor_fixo
from conformance.roteiro import ROTEIRO
from fakes import FakeElm327Mutant

ROOT = Path(__file__).resolve().parents[2]


def test_roteiro_cobre_19_comandos_do_e6_e_casos_da_tarefa_16() -> None:
    comandos = {p.comando for p in ROTEIRO}
    assert len(ROTEIRO) >= 19
    assert {"ATH1", "ATDPN", "0900", "0600", "03", "0902"} <= comandos


async def test_simulador_sem_divergencias() -> None:
    async with servidor_fixo() as server:
        resultados = await executar("127.0.0.1", server.port)
    assert [r for r in resultados if not r.ok] == []
    assert len(resultados) == len(ROTEIRO)


async def test_dourado_esta_em_dia_com_o_simulador() -> None:
    assert json.loads(DOURADO.read_text(encoding="utf-8")) == await gerar()


@pytest.mark.parametrize(
    ("troca", "comando_apontado"),
    [({"ATDPN": "ATFOO"}, "ATDPN"), ({"ATH1": "ATH0"}, "010C")],
)
async def test_detecta_divergencia_de_proposito(
    troca: dict[str, str], comando_apontado: str
) -> None:
    async with servidor_fixo() as server, FakeElm327Mutant(server.port, troca) as mutante:
        resultados = await executar("127.0.0.1", mutante.port)
    falhas = [r.comando for r in resultados if not r.ok]
    assert falhas and comando_apontado in falhas


async def test_perfil_pode_ignorar_e_trocar_esperado() -> None:
    async with servidor_fixo() as server, FakeElm327Mutant(server.port, {"ATDPN": "ATFOO"}) as m:
        perfil = {"ignorar": ["ATDPN"], "esperado": {"ATRV": "14.0V\r\r>"}}
        resultados = await executar("127.0.0.1", m.port, perfil=perfil)
    assert [r for r in resultados if not r.ok] == []


async def test_cli_sai_com_codigo_diferente_de_zero_na_divergencia() -> None:
    async with servidor_fixo() as server, FakeElm327Mutant(server.port, {"ATDPN": "ATFOO"}) as m:
        proc = await _cli(m.port)
        ok = await _cli(server.port)
    assert proc[0] != 0 and "ATDPN" in proc[1] and "DIFERENÇA" in proc[1]
    assert ok[0] == 0 and "0 divergência(s)" in ok[1]


async def _cli(port: int) -> tuple[int, str]:
    import asyncio

    p = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "tests.conformance", "--host", "127.0.0.1", "--port", str(port),
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )  # fmt: skip
    out, _ = await p.communicate()
    return p.returncode or 0, out.decode()


def test_dourado_corresponde_ao_roteiro() -> None:
    assert [d["comando"] for d in carregar_dourado()] == [p.comando for p in ROTEIRO]


def test_suite_nao_usa_time_time_nem_portas_fixas() -> None:
    fontes = "".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "tests/conformance").glob("*.py")
    )
    assert "time.time()" not in fontes and "35000" not in fontes
