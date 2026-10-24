"""API de controle do simulador (porta 8001, docs/spec/05-api.md e 07-dados-web.md)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi.testclient import TestClient

from fakes import FakeClock
from obd.protocol.dtc import code_to_bytes
from obd.protocol.frames import pad
from obd.protocol.pids import PIDS
from obd.simulator.control_api import Simulator, create_control_app

REQ_RPM = pad(bytes([0x02, 0x01, 0x0C]))


def ler_rpm(sim: Simulator) -> float:
    """Pede o PID 0x0C pelo barramento e decodifica a resposta, como o coletor faria."""
    sim.on_frame(0x7DF, REQ_RPM)
    (resposta,) = sim.poll()
    return PIDS[0x0C].decode(resposta.data[3:5])


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(start=1000.0)


@pytest.fixture
def sim(clock: FakeClock) -> Simulator:
    return Simulator(clock, seed_model=1, seed_ecu=2)


@pytest.fixture
async def http(sim: Simulator) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_control_app(sim))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_estado_lista_variaveis_perfis_e_sementes(http: httpx.AsyncClient) -> None:
    resp = await http.get("/sim/state")

    corpo = resp.json()
    assert resp.status_code == 200
    assert set(corpo["variaveis"]) == {"rpm", "speed", "coolant", "throttle", "fuel", "voltage"}
    assert corpo["perfil"] == "urbano"
    assert "rodovia" in corpo["perfis"]
    assert corpo["sementes"] == {"modelo": 1, "ecu": 2}


async def test_override_de_rotacao_aparece_no_estado_e_na_leitura_do_pid(
    http: httpx.AsyncClient, sim: Simulator
) -> None:
    resp = await http.put("/sim/override/rpm", json={"value": 3000})

    assert resp.status_code == 200
    assert resp.json()["variaveis"]["rpm"] == 3000
    assert resp.json()["overrides"] == {"rpm": 3000}
    assert ler_rpm(sim) == pytest.approx(3000, abs=0.25)


async def test_override_vale_em_ate_dois_ciclos(
    http: httpx.AsyncClient, sim: Simulator, clock: FakeClock
) -> None:
    await http.put("/sim/override/rpm", json={"value": 3000})

    leituras = []
    for _ in range(2):
        clock.advance(0.1)
        leituras.append(ler_rpm(sim))

    assert all(v == pytest.approx(3000, abs=0.25) for v in leituras)


async def test_delete_override_volta_ao_modelo_automatico(
    http: httpx.AsyncClient, sim: Simulator, clock: FakeClock
) -> None:
    await http.put("/sim/override/rpm", json={"value": 3000})

    resp = await http.delete("/sim/override/rpm")
    clock.advance(5.0)

    assert resp.status_code == 200
    assert resp.json()["overrides"] == {}
    assert ler_rpm(sim) != pytest.approx(3000, abs=0.25)


async def test_override_com_nome_desconhecido_retorna_404(http: httpx.AsyncClient) -> None:
    resp = await http.put("/sim/override/torque", json={"value": 10})

    assert resp.status_code == 404


@pytest.mark.parametrize(
    ("nome", "valor"),
    [("rpm", -1), ("rpm", 99999), ("speed", 300), ("throttle", 101), ("coolant", -50)],
)
async def test_override_fora_de_faixa_e_rejeitado(
    http: httpx.AsyncClient, nome: str, valor: float
) -> None:
    resp = await http.put(f"/sim/override/{nome}", json={"value": valor})

    assert resp.status_code == 422


async def test_corpo_invalido_retorna_422(http: httpx.AsyncClient) -> None:
    resp = await http.put("/sim/override/rpm", json={"valor": 3000})

    assert resp.status_code == 422
    assert "value" in resp.text


async def test_perfil_muda_o_ciclo_de_conducao(http: httpx.AsyncClient, sim: Simulator) -> None:
    resp = await http.post("/sim/profile", json={"name": "rodovia"})

    assert resp.status_code == 200
    assert resp.json()["perfil"] == "rodovia"
    assert sim.model.profile.name == "rodovia"


async def test_perfil_inexistente_retorna_422(http: httpx.AsyncClient) -> None:
    resp = await http.post("/sim/profile", json={"name": "inexistente"})

    assert resp.status_code == 422


async def test_injeta_dtc_pendente_e_limpa(http: httpx.AsyncClient, sim: Simulator) -> None:
    resp = await http.post("/sim/dtc", json={"code": "P0300", "pending": True})

    assert resp.status_code == 200
    assert resp.json()["dtcs"] == {"armazenados": [], "pendentes": ["P0300"]}
    assert code_to_bytes("P0300") in (sim.ecu.process(bytes([0x07])) or b"")  # Modo 07

    resp = await http.delete("/sim/dtc")

    assert resp.json()["dtcs"] == {"armazenados": [], "pendentes": []}
    assert code_to_bytes("P0300") not in (sim.ecu.process(bytes([0x07])) or b"")


async def test_dtc_com_codigo_invalido_retorna_422(http: httpx.AsyncClient) -> None:
    resp = await http.post("/sim/dtc", json={"code": "X9"})

    assert resp.status_code == 422


async def test_latencia_e_gravada_e_faixa_invertida_e_rejeitada(
    http: httpx.AsyncClient, sim: Simulator
) -> None:
    resp = await http.put("/sim/latency", json={"min": 8, "max": 14})

    assert resp.status_code == 200
    assert resp.json()["latencia"] == {"min": 8, "max": 14}
    assert sim.latency == (8, 14)

    assert (await http.put("/sim/latency", json={"min": 20, "max": 5})).status_code == 422


async def test_rede_grava_perda_e_corrupcao(http: httpx.AsyncClient, sim: Simulator) -> None:
    resp = await http.put("/sim/network", json={"drop": 0.02, "corrupt": 0.5})

    assert resp.status_code == 200
    assert sim.faults.frame_loss == pytest.approx(0.02)
    assert sim.faults.corruption == pytest.approx(0.5)
    assert (await http.put("/sim/network", json={"drop": 1.5, "corrupt": 0})).status_code == 422


async def test_ecu_sem_resposta_silencia_o_barramento(
    http: httpx.AsyncClient, sim: Simulator
) -> None:
    resp = await http.post("/sim/unresponsive", json={"on": True})
    sim.on_frame(0x7DF, REQ_RPM)

    assert resp.status_code == 200
    assert resp.json()["sem_resposta"] is True
    assert sim.poll() == []

    await http.post("/sim/unresponsive", json={"on": False})
    sim.on_frame(0x7DF, REQ_RPM)

    assert len(sim.poll()) == 1


async def test_semente_reinicia_com_o_mesmo_resultado_para_a_mesma_semente(
    http: httpx.AsyncClient, sim: Simulator, clock: FakeClock
) -> None:
    resp = await http.post("/sim/seed", json={"model": 42, "ecu": 7})
    assert resp.status_code == 200
    assert resp.json()["sementes"] == {"modelo": 42, "ecu": 7}

    outro_relogio = FakeClock(start=1000.0)
    outro = Simulator(outro_relogio, seed_model=42, seed_ecu=7)
    clock.advance(3.0)
    outro_relogio.advance(3.0)

    assert ler_rpm(sim) == ler_rpm(outro)


async def test_semente_negativa_retorna_422(http: httpx.AsyncClient) -> None:
    assert (await http.post("/sim/seed", json={"model": -1, "ecu": 0})).status_code == 422


def test_stream_envia_estado_e_quadros_em_hexadecimal(clock: FakeClock) -> None:
    sim = Simulator(clock, seed_model=1, seed_ecu=2)
    with TestClient(create_control_app(sim)) as client:
        sim.on_frame(0x7DF, REQ_RPM)
        sim.poll()

        with client.websocket_connect("/sim/stream") as ws:
            primeira = ws.receive_json()
            quadros = [q["id"] for q in primeira["quadros"]]

            assert "variaveis" in primeira["estado"]
            assert quadros == ["7DF", "7E8"]
            assert primeira["quadros"][0]["dados"].startswith("02 01 0C")
            assert all(len(q["dados"].split()) == 8 for q in primeira["quadros"])


async def test_painel_estatico_e_servido_na_raiz(http: httpx.AsyncClient) -> None:
    resp = await http.get("/")

    assert resp.status_code == 200
    assert "Painel de controle do simulador" in resp.text
