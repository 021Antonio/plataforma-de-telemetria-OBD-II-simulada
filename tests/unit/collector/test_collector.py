from collections.abc import Mapping

import httpx
import pytest

from fakes import FakeClock, ScriptedTransport
from obd.collector.collector import Collector
from obd.collector.publisher import HttpPublisher, RecordingPublisher
from obd.collector.scheduler import BackoffConfig, CollectorConfig, PidRate, Scheduler
from obd.protocol.pids import encode_monitor_status, encode_supported
from obd.protocol.schemas import Sample

RPM = bytes([0x41, 0x0C, 0x1F, 0x40])  # 2000 rpm
SPEED = bytes([0x41, 0x0D, 60])
COOLANT = bytes([0x41, 0x05, 128])  # 88 C
PLAN = {0x0C: PidRate(1, 0), 0x0D: PidRate(1, 1), 0x05: PidRate(3, 2)}
FAST_BACKOFF = BackoffConfig(threshold=2, base_ms=100, max_ms=400)


def script(**extra: bytes | None) -> dict[bytes, bytes | None]:
    mask = encode_supported(0x00, [0x01, 0x05, 0x0C, 0x0D])
    table: dict[bytes, bytes | None] = {
        b"\x01\x00": b"\x41\x00" + mask,
        b"\x01\x0c": RPM,
        b"\x01\x0d": SPEED,
        b"\x01\x05": COOLANT,
        b"\x01\x01": b"\x41\x01" + encode_monitor_status(False, 0),
    }
    table.update({bytes.fromhex(k): v for k, v in extra.items()})
    return table


def make(
    table: Mapping[bytes, bytes | None], clock: FakeClock | None = None
) -> tuple[Collector, ScriptedTransport, RecordingPublisher, FakeClock]:
    clock = clock or FakeClock(1000.0)
    transport = ScriptedTransport(table)
    pub = RecordingPublisher()
    col = Collector(
        transport,
        pub,
        rates=PLAN,
        clock=clock,
        wall_clock=clock,
        sleep=clock.sleep,
        backoff=FAST_BACKOFF,
        source="can_virtual",
    )
    return col, transport, pub, clock


async def test_discovery_queries_support_pids_in_chain() -> None:
    mask0 = encode_supported(0x00, [0x01, 0x0C, 0x20])
    mask20 = encode_supported(0x20, [0x2F, 0x40])
    mask40 = encode_supported(0x40, [0x42])
    col, t, _, _ = make(
        {
            b"\x01\x00": b"\x41\x00" + mask0,
            b"\x01\x20": b"\x41\x20" + mask20,
            b"\x01\x40": b"\x41\x40" + mask40,
        }
    )
    await col.start()
    assert t.calls == [b"\x01\x00", b"\x01\x20", b"\x01\x40"]
    assert {0x0C, 0x2F, 0x42} <= col.supported


async def test_discovery_stops_without_continuation_bit() -> None:
    col, t, _, _ = make(script())
    await col.start()
    assert t.calls == [b"\x01\x00"]
    assert col.supported >= {0x0C, 0x0D, 0x05}


async def test_plan_fast_every_cycle_slow_every_n() -> None:
    col, t, pub, _ = make(script())
    await col.start()
    for _ in range(4):
        await col.run_cycle()
    names = [sorted(s.values) for s in pub.samples]
    assert names[0] == ["coolant", "rpm", "speed"]
    assert names[1] == ["rpm", "speed"]
    assert names[2] == ["rpm", "speed"]
    assert names[3] == ["coolant", "rpm", "speed"]


async def test_sample_decoded_values_and_metadata() -> None:
    col, _, pub, clock = make(script())
    await col.start()
    await col.run_cycle()
    s = pub.samples[0]
    assert s.values["rpm"].value == 2000.0
    assert s.values["rpm"].pid == "0x0C"
    assert s.values["rpm"].unit == "rpm"
    assert s.values["coolant"].value == 88.0
    assert s.source == "can_virtual"
    assert s.ts == clock.now
    assert s.errors.timeouts == 0 and s.errors.invalid == 0


async def test_unsupported_pid_is_not_requested() -> None:
    col_sup = {
        b"\x01\x00": b"\x41\x00" + encode_supported(0x00, [0x01, 0x0C]),
        b"\x01\x0c": RPM,
    }
    col, t, pub, _ = make(col_sup)
    await col.start()
    await col.run_cycle()
    assert b"\x01\x0d" not in t.calls
    assert list(pub.samples[0].values) == ["rpm"]


async def test_timeout_is_recorded_and_cycle_continues() -> None:
    col, _, pub, _ = make(script(**{"010d": None}))
    await col.start()
    await col.run_cycle()
    s = pub.samples[0]
    assert "speed" not in s.values and "rpm" in s.values
    assert s.errors.timeouts == 1
    assert any(e.kind == "timeout" for e in col.events)


async def test_invalid_response_wrong_pid_echo_and_mode() -> None:
    col, _, pub, _ = make(
        script(**{"010d": bytes([0x41, 0x0C, 0x1F, 0x40]), "010c": b"\x42\x0c\x00"})
    )
    await col.start()
    await col.run_cycle()
    s = pub.samples[0]
    assert s.errors.invalid == 2 and s.errors.timeouts == 0
    assert "rpm" not in s.values and "speed" not in s.values
    assert [e.kind for e in col.events].count("invalid") == 2


async def test_negative_response_counts_as_invalid() -> None:
    col, _, pub, _ = make(script(**{"010d": b"\x7f\x01\x12"}))
    await col.start()
    await col.run_cycle()
    assert pub.samples[0].errors.invalid == 1


async def test_backoff_grows_then_resumes_after_success() -> None:
    table = script(**{"010c": None, "010d": None, "0105": None, "0101": None})
    col, t, pub, clock = make(table)
    await col.start()
    start = clock.now
    await (
        col.run_cycle()
    )  # limiar 2: espera 0,1 s antes da 3a requisição, 0,2 s antes da leitura do PID 0x01
    assert clock.now - start == pytest.approx(
        0.1 + 0.2
    )  # 3a falha: 0,1 s; leitura do PID 0x01: 0,2 s
    await col.run_cycle()  # esperas de 0,4 s (teto) antes de cada uma das duas leituras
    assert clock.now - start == pytest.approx(0.1 + 0.2 + 0.4 + 0.4)
    assert any(e.kind == "backoff" for e in col.events)
    # retomada: ECU volta
    t._script.update(script())
    before = clock.now
    await col.run_cycle()
    assert len(pub.samples[-1].values) >= 2
    assert col.consecutive_failures == 0
    assert clock.now - before == pytest.approx(0.4)  # última espera antes de retomar
    mid = clock.now
    await col.run_cycle()
    assert clock.now == mid  # sem recuo depois de retomar


async def test_seq_is_continuous_even_with_empty_cycles() -> None:
    col, t, pub, _ = make(script(**{"010c": None, "010d": None, "0105": None}))
    await col.start()
    for _ in range(5):
        await col.run_cycle()
    assert [s.seq for s in pub.samples] == [0, 1, 2, 3, 4]


async def test_dtc_read_only_on_change_every_2s() -> None:
    dtc_empty = b"\x43\x00"
    dtc_one = b"\x43\x01\x03\x00"
    col, t, pub, clock = make(script(**{"03": dtc_empty}))
    await col.start()
    await col.run_cycle()
    assert t.calls.count(b"\x03") == 1  # primeira leitura
    assert len(pub.reports) == 1 and pub.reports[0].count == 0 and not pub.reports[0].mil
    clock.advance(1.0)
    await col.run_cycle()
    assert t.calls.count(b"\x01\x01") == 1  # ainda não passou 2 s
    clock.advance(1.5)
    await col.run_cycle()
    assert t.calls.count(b"\x01\x01") == 2 and t.calls.count(b"\x03") == 1  # sem mudança
    t._script[b"\x01\x01"] = b"\x41\x01" + encode_monitor_status(True, 1)
    t._script[b"\x03"] = dtc_one
    clock.advance(2.0)
    await col.run_cycle()
    assert t.calls.count(b"\x03") == 2
    r = pub.reports[-1]
    assert r.mil and r.count == 1 and r.codes[0].code == "P0300"
    assert r.codes[0].status == "stored" and r.codes[0].description


async def test_transport_closed_on_close() -> None:
    col, t, _, _ = make(script())
    await col.start()
    assert t.is_open
    await col.close()
    assert not t.is_open


async def test_run_paces_cycles_and_stops_at_max() -> None:
    col, _, pub, clock = make(script())
    await col.start()
    t0 = clock.now
    await col.run(max_cycles=3, interval_s=0.1)
    assert len(pub.samples) == 3
    assert clock.now - t0 >= 0.3 - 1e-9


async def test_publish_failure_is_recorded_not_fatal() -> None:
    class Boom(RecordingPublisher):
        async def publish_sample(self, sample: Sample) -> None:
            raise httpx.ConnectError("sem servidor")

    clock = FakeClock()
    col = Collector(
        ScriptedTransport(script()),
        Boom(),
        rates=PLAN,
        clock=clock,
        wall_clock=clock,
        sleep=clock.sleep,
    )
    await col.start()
    await col.run_cycle()
    await col.run_cycle()
    assert [e.kind for e in col.events].count("publish_failed") == 2


def test_scheduler_orders_by_priority_and_filters_supported() -> None:
    s = Scheduler(PLAN, {0x0C, 0x05})
    assert s.pids == [0x0C, 0x05]
    assert s.for_cycle(1) == [0x0C]
    assert s.for_cycle(3) == [0x0C, 0x05]


def test_default_config_has_plan_and_transport() -> None:
    cfg = CollectorConfig.from_yaml()
    assert cfg.transport in ("can_virtual", "loopback", "elm327_tcp")
    assert cfg.plan is not None and cfg.plan[0x0C].every == 1 and cfg.plan[0x05].every > 1
    assert cfg.backoff.delay(0) == 0.0 and cfg.backoff.delay(cfg.backoff.threshold) > 0


def test_backoff_caps() -> None:
    b = BackoffConfig(threshold=1, base_ms=100, max_ms=300)
    assert [b.delay(n) for n in range(0, 5)] == [0.0, 0.1, 0.2, 0.3, 0.3]


async def test_http_publisher_posts_to_ingest_routes() -> None:
    seen: list[tuple[str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.append((request.url.path, json.loads(request.content)))
        return httpx.Response(202)

    client = httpx.AsyncClient(base_url="http://srv", transport=httpx.MockTransport(handler))
    pub = HttpPublisher(client=client)
    col = Collector(ScriptedTransport(script(**{"03": b"\x43\x00"})), pub, rates=PLAN)
    await col.start()
    await col.run_cycle()
    await pub.aclose()
    assert seen[0][0] == "/api/ingest/sample"
    assert seen[0][1]["seq"] == 0
    assert "rpm" in seen[0][1]["values"]  # type: ignore[operator]
    assert any(p == "/api/ingest/dtc" for p, _ in seen)
