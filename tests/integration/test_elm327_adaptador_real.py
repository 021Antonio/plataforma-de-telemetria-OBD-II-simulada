"""Coletor e transporte `elm327_tcp` diante de um adaptador que erra, atrasa e cai (tarefa 18)."""

import time
from collections.abc import AsyncIterator

import pytest

from fakes import FakeVehicleModel
from obd.collector.collector import Collector
from obd.collector.publisher import RecordingPublisher
from obd.collector.scheduler import CollectorConfig
from obd.protocol.pids import get_pid
from obd.simulator.ecu import Ecu
from obd.simulator.elm327_server import Elm327Server, ErrorInjection
from obd.transport.elm327_tcp import Elm327TcpTransport, classify_reply, parse_reply
from obd.transport.loopback import LoopbackTransport

VALUES = {
    0x04: 42.0,
    0x05: 88.0,
    0x06: 0.0,
    0x0B: 33.0,
    0x0C: 3127.5,
    0x0D: 77.0,
    0x0F: 31.0,
    0x11: 18.5,
    0x2F: 61.2,
    0x42: 13.987,
}
ERRORS = [
    "UNABLE TO CONNECT",
    "BUS INIT: ERROR",
    "CAN ERROR",
    "STOPPED",
    "BUFFER FULL",
    "?",
    "NO DATA",
]
REQ_0C = bytes([0x01, 0x0C])
REQ_0D = bytes([0x01, 0x0D])
INIT = ["ATZ", "ATE0", "ATL0", "ATS0", "ATH0", "ATSP0"]


async def no_sleep(_: float) -> None:
    return None


@pytest.fixture
async def server() -> AsyncIterator[Elm327Server]:
    ecu = Ecu(FakeVehicleModel(VALUES, time.monotonic), time.monotonic)
    srv = Elm327Server(LoopbackTransport(ecu), port=0, inject=ErrorInjection(record=True))
    await srv.start()
    try:
        yield srv
    finally:
        await srv.stop()


def make_collector(
    srv: Elm327Server, pub: RecordingPublisher, *, timeout_ms: int = 500
) -> tuple[Collector, Elm327TcpTransport]:
    transport = Elm327TcpTransport("127.0.0.1", srv.port, sleep=no_sleep)
    col = Collector(
        transport,
        pub,
        rates=CollectorConfig.from_yaml().plan,
        timeout_ms=timeout_ms,
        sleep=no_sleep,
    )
    return col, transport


def test_classify_reply() -> None:
    for text in ERRORS:
        assert classify_reply(f"SEARCHING...\r{text}\r\r") == text
    assert classify_reply("BUSINIT:ERROR\r") == "BUS INIT: ERROR"
    assert classify_reply("41 0C 1F 40\r\r") is None
    assert parse_reply("CAN ERROR\r\r") is None


def test_defaults_are_wifi_friendly() -> None:
    cfg = CollectorConfig.from_yaml()
    assert cfg.timeout_ms >= 300
    assert cfg.search_timeout_s >= 3.0


@pytest.mark.parametrize("text", ERRORS)
async def test_each_error_is_event_without_value(server: Elm327Server, text: str) -> None:
    pub = RecordingPublisher()
    col, _ = make_collector(server, pub)
    await col.start()
    server.inject.errors.append(text)
    sample = await col.run_cycle()
    await col.close()
    assert len(sample.values) == len(VALUES) - 1  # o primeiro PID do plano (0x0C) falhou
    assert "engine_rpm" not in sample.values
    assert sample.errors.invalid == 1 and sample.errors.timeouts == 0
    events = [e for e in col.events if e.kind == "adapter_error"]
    assert len(events) == 1 and text in events[0].detail


async def test_all_errors_in_a_row_then_recovers(server: Elm327Server) -> None:
    pub = RecordingPublisher()
    col, _ = make_collector(server, pub)
    await col.start()
    server.inject.errors.extend(ERRORS)
    s0 = await col.run_cycle()
    assert len(s0.values) == len(VALUES) - len(ERRORS) and s0.errors.invalid == len(ERRORS)
    details = [e.detail for e in col.events if e.kind == "adapter_error"]
    assert [any(t in d for d in details) for t in ERRORS] == [True] * len(ERRORS)
    s1 = await col.run_cycle()
    await col.close()
    assert len(s1.values) == 4 and (s0.seq, s1.seq) == (0, 1)
    d = get_pid(0x0C)
    assert abs(s1.values[d.name].value - VALUES[0x0C]) <= d.resolution / 2 + 1e-9


async def test_tcp_drop_reconnects_reinitializes_and_keeps_seq(server: Elm327Server) -> None:
    pub = RecordingPublisher()
    col, _ = make_collector(server, pub)
    await col.start()
    server.inject.drop_connection_after(4)
    server.inject.seen.clear()
    for _ in range(3):
        await col.run_cycle()
    await col.close()
    assert [s.seq for s in pub.samples] == [0, 1, 2]
    assert len(pub.samples[0].values) == len(VALUES) - 1  # só a consulta em que a queda aconteceu
    assert [e.kind for e in col.events].count("adapter_error") >= 1
    assert any("conex" in e.detail for e in col.events if e.kind == "adapter_error")
    seen = server.inject.seen
    first_atz = seen.index("ATZ")
    assert seen[first_atz : first_atz + 6] == INIT  # reinicialização completa antes de voltar a ler
    assert len(pub.samples[1].values) == 4  # ciclo rápido, completo após a reconexão


async def test_reconnect_backoff_grows_and_resets() -> None:
    ecu = Ecu(FakeVehicleModel(VALUES, time.monotonic), time.monotonic)
    srv = Elm327Server(LoopbackTransport(ecu), port=0)
    await srv.start()
    port = srv.port
    slept: list[float] = []

    async def sleep(s: float) -> None:
        slept.append(s)

    t = Elm327TcpTransport(
        "127.0.0.1", port, sleep=sleep, reconnect_base_ms=200, reconnect_max_ms=500
    )
    await t.open()
    assert await t.request(REQ_0C, 500) is not None
    await srv.stop()
    for _ in range(6):
        assert await t.request(REQ_0C, 200) is None
    # a queda é notada na 1ª, a 1ª reconexão é imediata, depois recuo dobrando até o teto
    assert slept == [0.2, 0.4, 0.5, 0.5]
    srv2 = Elm327Server(LoopbackTransport(ecu), port=port)
    await srv2.start()
    try:
        assert await t.request(REQ_0C, 500) is not None
        slept.clear()
        await srv2.stop()
        for _ in range(3):  # queda nova: o recuo recomeça do início
            assert await t.request(REQ_0C, 200) is None
        assert slept == [0.2]
    finally:
        await t.close()


async def test_delay_over_timeout_times_out_and_under_does_not(server: Elm327Server) -> None:
    transport = Elm327TcpTransport("127.0.0.1", server.port, sleep=no_sleep)
    await transport.open()
    try:
        assert await transport.request(REQ_0C, 500) is not None  # encerra a fase de busca
        server.inject.extra_delay_ms = 150
        assert await transport.request(REQ_0C, 50) is None
        assert transport.last_error is None  # estouro de tempo não é erro do adaptador
        server.inject.extra_delay_ms = 20
        raw = await transport.request(REQ_0D, 500)
        # a resposta atrasada de 0C não pode ser tomada como a de 0D
        assert raw is not None and raw[:2] == bytes([0x41, 0x0D])
    finally:
        await transport.close()


async def test_collector_records_timeout_on_slow_adapter(server: Elm327Server) -> None:
    pub = RecordingPublisher()
    col, _ = make_collector(server, pub, timeout_ms=50)
    await col.start()
    server.inject.extra_delay_ms = 150
    sample = await col.run_cycle()
    await col.close()
    assert sample.errors.timeouts == len(VALUES) and not sample.values
    assert {e.kind for e in col.events} >= {"timeout"}


async def test_search_phase_has_its_own_timeout(server: Elm327Server) -> None:
    server.inject.extra_delay_ms = 150
    transport = Elm327TcpTransport("127.0.0.1", server.port, search_timeout_s=2.0, sleep=no_sleep)
    await transport.open()
    try:
        assert await transport.request(bytes([0x01, 0x00]), 50) is not None  # busca: 2 s
        assert await transport.request(REQ_0C, 50) is None  # depois vale o tempo da consulta
    finally:
        await transport.close()


async def test_injection_off_by_default() -> None:
    ecu = Ecu(FakeVehicleModel(VALUES, time.monotonic), time.monotonic)
    srv = Elm327Server(LoopbackTransport(ecu), port=0)
    assert srv.inject.errors == [] and srv.inject.extra_delay_ms == 0
    assert srv.inject.drop_after is None
