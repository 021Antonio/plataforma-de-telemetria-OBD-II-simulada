"""Caminho MQTT (coletor -> broker falso -> assinante -> armazenamento) contra o caminho HTTP."""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path

import httpx
import pytest
import yaml

from fakes import FakeBroker, FakeClock, ScriptedTransport, make_sample
from obd.collector.collector import Collector
from obd.collector.factory import build_publisher
from obd.collector.mqtt_publisher import MqttPublisher
from obd.collector.publisher import HttpPublisher, Publisher
from obd.collector.scheduler import PidRate
from obd.mqtt_common import AiomqttLink
from obd.protocol.schemas import DtcEntry, DtcReport, Sample
from obd.server.app import create_app
from obd.server.mqtt_subscriber import MqttSubscriber
from obd.server.state import ServerState
from obd.server.storage import DUPLICATE, InMemoryStorage

CONFIG = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


class NoSleep:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)
        await asyncio.sleep(0)


def report() -> DtcReport:
    return DtcReport(
        ts=1000.0,
        mil=True,
        count=1,
        codes=[DtcEntry(code="P0300", description="Falha de ignição", status="stored")],
    )


async def settle() -> None:
    for _ in range(50):
        await asyncio.sleep(0)


def new_state() -> ServerState:
    return ServerState(storage=InMemoryStorage(), clock=FakeClock(1000.0))


async def start_subscriber(broker: FakeBroker, state: ServerState) -> MqttSubscriber:
    sub = MqttSubscriber(broker.link, state, sleep=NoSleep())
    sub.start()
    await settle()
    return sub


async def test_publica_nos_topicos_e_qos_da_spec() -> None:
    broker = FakeBroker()
    pub = MqttPublisher(broker.link, "carro1")

    await pub.publish_sample(make_sample(0, 1000.0))
    await pub.publish_dtcs(report())

    topics = [(t, q) for t, _, q in broker.published]
    assert topics == [("telemetria/carro1/dados", 0), ("telemetria/carro1/dtc", 1)]


async def test_payload_e_o_mesmo_json_do_http() -> None:
    broker = FakeBroker()
    sample = make_sample(3, 1000.0)
    await MqttPublisher(broker.link).publish_sample(sample)

    assert json.loads(broker.published[0][1]) == json.loads(sample.model_dump_json())


async def test_resultado_mqtt_igual_ao_http() -> None:
    samples = [make_sample(i, 1000.0 + i * 0.1) for i in (0, 1, 3, 3, 4)]  # lacuna no 2, repetido 3
    # HTTP
    http_state = new_state()
    app = create_app(http_state.storage, clock=http_state.clock)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        http_pub: Publisher = HttpPublisher(client=c)
        for s in samples:
            await http_pub.publish_sample(s)
        await http_pub.publish_dtcs(report())
        http_stats = (await c.get("/api/stats")).json()
        http_hist = (await c.get("/api/history")).json()
        http_dtc = (await c.get("/api/dtc")).json()
    # MQTT
    broker = FakeBroker()
    state = new_state()
    sub = await start_subscriber(broker, state)
    mqtt_pub = MqttPublisher(broker.link)
    for s in samples:
        await mqtt_pub.publish_sample(s)
    await mqtt_pub.publish_dtcs(report())
    await settle()
    await sub.stop()

    stored = [item.sample.model_dump(mode="json") for item in await state.storage.stored_samples()]
    assert stored == http_hist
    assert [r.model_dump(mode="json") for r in await state.storage.dtc_reports()] == http_dtc
    assert state.run_id is not None
    rows = await state.storage.sample_rows(state.run_id)
    assert [r.seq for r in rows] == [0, 1, 3, 4]
    assert http_stats["received"] == 4 and http_stats["lost"] == 1
    assert http_stats["duplicated"] == 1
    assert await state.storage.count_comm_events(state.run_id, DUPLICATE) == 1


async def test_mensagem_invalida_e_rejeitada_sem_derrubar_o_assinante() -> None:
    broker = FakeBroker()
    state = new_state()
    sub = await start_subscriber(broker, state)
    link = broker.link()
    await link.connect()
    await link.publish("telemetria/x/dados", b"{nao e json", 0)
    await link.publish("telemetria/x/dados", b'{"seq": "a"}', 0)
    await MqttPublisher(broker.link, "x").publish_sample(make_sample(0, 1000.0))
    await settle()
    await sub.stop()

    assert sub.rejected == 2
    assert await state.storage.latest_sample() is not None


async def test_reconexao_do_coletor_mantem_a_ordem_de_seq() -> None:
    broker = FakeBroker()
    state = new_state()
    sub = await start_subscriber(broker, state)
    sleep = NoSleep()
    pub = MqttPublisher(broker.link, sleep=sleep)
    for seq in range(3):
        await pub.publish_sample(make_sample(seq, 1000.0 + seq))
    await settle()

    broker.go_down()
    sender = asyncio.create_task(pub.publish_sample(make_sample(3, 1003.0)))
    await settle()
    assert not sender.done()  # esperando o broker, sem pular o seq 3
    await settle()
    broker.come_back()
    await sender
    await pub.publish_sample(make_sample(4, 1004.0))
    await settle()
    await sub.stop()

    assert sleep.delays[:3] == [1, 2, 4]
    assert [t for t, _, _ in broker.published] == ["telemetria/simulado/dados"] * 5
    seqs = [Sample.model_validate_json(p).seq for _, p, _ in broker.published]
    assert seqs == [0, 1, 2, 3, 4]
    assert state.run_id is not None
    assert [r.seq for r in await state.storage.sample_rows(state.run_id)] == [0, 1, 2, 3, 4]


async def test_recuo_para_em_30_segundos() -> None:
    broker = FakeBroker()
    broker.go_down()
    sleep = NoSleep()
    pub = MqttPublisher(broker.link, sleep=sleep)
    sender = asyncio.create_task(pub.publish_sample(make_sample(0, 1000.0)))
    for _ in range(300):
        await asyncio.sleep(0)
    broker.come_back()
    await sender

    assert sleep.delays[:7] == [1, 2, 4, 8, 16, 30, 30]


async def test_assinante_reconecta_quando_o_broker_cai() -> None:
    broker = FakeBroker()
    state = new_state()
    sub = await start_subscriber(broker, state)
    pub = MqttPublisher(broker.link, sleep=NoSleep())
    await pub.publish_sample(make_sample(0, 1000.0))
    await settle()

    broker.go_down()
    await settle()
    broker.come_back()
    await settle()
    await pub.publish_sample(make_sample(1, 1001.0))
    await settle()
    await sub.stop()

    assert sub.reconnects >= 1
    assert state.run_id is not None
    assert [r.seq for r in await state.storage.sample_rows(state.run_id)] == [0, 1]


async def test_app_liga_o_assinante_pelo_lifespan() -> None:
    broker = FakeBroker()
    storage = InMemoryStorage()
    app = create_app(storage, clock=FakeClock(1000.0), mqtt_link=broker.link)
    async with app.router.lifespan_context(app):
        await settle()
        pub = MqttPublisher(broker.link)
        await pub.publish_sample(make_sample(0, 1000.0))
        await settle()
        assert await storage.latest_sample() is not None
        await pub.aclose()
    assert broker.links == []


def test_trocar_publisher_na_configuracao_nao_muda_o_coletor() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert config["publisher"] == "http"
    assert config["mqtt"]["porta"] == 1883

    http = build_publisher(config)
    mqtt = build_publisher({**config, "publisher": "mqtt"}, link_factory=FakeBroker().link)

    assert isinstance(http, HttpPublisher) and isinstance(mqtt, MqttPublisher)
    with pytest.raises(ValueError):
        build_publisher({"publisher": "kafka"})


async def test_coletor_publica_por_mqtt_sem_alteracao() -> None:
    broker = FakeBroker()
    col = Collector(ScriptedTransport({}), MqttPublisher(broker.link), rates={0x0C: PidRate()})
    await col.start()
    await col.run_cycle()
    await col.close()

    assert any(t.endswith("/dados") for t, _, _ in broker.published)


def _broker_up() -> bool:
    try:
        socket.create_connection(("localhost", 1883), timeout=0.5).close()
    except OSError:
        return False
    return True


@pytest.mark.broker
async def test_mosquitto_real_ponta_a_ponta() -> None:
    if not _broker_up():
        pytest.skip("sem broker em localhost:1883 (docker compose --profile mqtt up -d mosquitto)")
    state = new_state()
    sub = MqttSubscriber(lambda: AiomqttLink("localhost", 1883), state, vehicle="teste-broker")
    sub.start()
    await asyncio.sleep(0.5)
    pub = MqttPublisher(lambda: AiomqttLink("localhost", 1883), "teste-broker")
    await pub.publish_sample(make_sample(0, 1000.0))
    await pub.publish_dtcs(report())
    await asyncio.sleep(0.5)
    await sub.stop()
    await pub.aclose()

    assert await state.storage.latest_sample() is not None
    assert len(await state.storage.dtc_reports()) == 1
