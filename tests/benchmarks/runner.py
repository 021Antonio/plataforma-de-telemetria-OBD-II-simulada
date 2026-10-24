"""Executor de ensaios: sobe simulador, coletor e servidor, aplica o cenário e mede.

Tudo roda em um só processo, em tarefas `asyncio` (decisão em docs/duvidas.md): a ECU registra
o valor real de cada resposta e só neste processo dá para juntá-lo ao `Sample` pelo `seq`. O
coletor nunca vê o valor real: a junção fica em `TruthTransport` e `TruthPublisher`.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import platform
import socket
import sqlite3
import sys
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import uvicorn

from obd.collector.collector import Collector
from obd.collector.mqtt_publisher import MqttPublisher
from obd.collector.publisher import HttpPublisher, Publisher
from obd.collector.scheduler import PidRate
from obd.mqtt_common import AiomqttLink, MqttLink
from obd.protocol.frames import ID_ENGINE_RESPONSE, ID_FUNCTIONAL
from obd.protocol.pids import PIDS
from obd.protocol.schemas import DtcReport, Sample
from obd.server.app import create_app
from obd.server.stats import compute_stats
from obd.server.storage import DUPLICATE, SqlStorage
from obd.simulator.control_api import Simulator
from obd.transport.loopback import LoopbackTransport

from .stats import summarize

# Ordem de entrada dos PIDs nos ensaios com menos de 10 (E3).
TEN_PIDS = (0x0C, 0x0B, 0x11, 0x0D, 0x04, 0x05, 0x0F, 0x2F, 0x42, 0x06)
RESULT_ROOT = Path("runs")
P2_MS = 50.0  # RNF04: P2 da ISO 15765-4
CYCLE_LIMIT_MS = 150.0  # RNF01
LATENCY_P95_LIMIT_MS = 50.0  # RNF02
MQTT_HOST, MQTT_PORT = "localhost", 1883

Clock = Callable[[], float]


@dataclass(frozen=True)
class Scenario:
    label: str
    duration_s: float
    pids: tuple[int, ...] = TEN_PIDS
    delay_ms: tuple[int, int] = (7, 13)  # 10 ms ± 3 ms
    frame_loss: float = 0.0
    fault_code: str | None = None
    fault_at_s: float = 0.0  # instante da falha, contado do início da coleta
    channel: str = "http"  # http | mqtt
    seed_model: int = 1
    seed_ecu: int = 1
    profile: str = "urbano"
    timeout_ms: int = 100
    interval_ms: float = 100.0


@dataclass
class RunOutput:
    scenario: Scenario
    rows: list[dict[str, Any]]
    metrics: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)


# ---- junção do valor real ------------------------------------------------------------------


class TruthTransport:
    """Repassa ao transporte real e anota o valor real que a ECU registrou para cada PID."""

    def __init__(self, inner: LoopbackTransport, log: list[tuple[int, float]]) -> None:
        self._inner = inner
        self._log = log
        self.pending: dict[int, float] = {}

    @property
    def name(self) -> str:
        return "can_virtual"  # fonte registrada nas amostras (o loopback faz o papel do barramento)

    async def open(self) -> None:
        await self._inner.open()

    async def close(self) -> None:
        await self._inner.close()

    async def request(self, payload: bytes, timeout_ms: int = 100) -> bytes | None:
        before = len(self._log)
        resp = await self._inner.request(payload, timeout_ms)
        if len(self._log) > before and len(payload) == 2 and payload[0] == 0x01:
            self.pending[payload[1]] = self._log[-1][1]
        return resp


class TruthPublisher:
    """Guarda os valores reais por `seq` e a hora em que a falha foi vista pelo coletor."""

    def __init__(
        self, inner: Publisher, transport: TruthTransport, clock: Clock, fault_code: str | None
    ) -> None:
        self._inner = inner
        self._transport = transport
        self._clock = clock
        self._fault_code = fault_code
        self.truth: dict[int, dict[int, float]] = {}
        self.attempted = 0
        self.delivered = 0
        self.fault_seen_at: float | None = None

    async def publish_sample(self, sample: Sample) -> None:
        self.truth[sample.seq] = dict(self._transport.pending)
        self._transport.pending.clear()
        self.attempted += 1
        await self._inner.publish_sample(sample)
        self.delivered += 1

    async def publish_dtcs(self, report: DtcReport) -> None:
        if self.fault_seen_at is None and any(c.code == self._fault_code for c in report.codes):
            self.fault_seen_at = self._clock()
        await self._inner.publish_dtcs(report)


def truth_series(
    *,
    seed_model: int,
    seed_ecu: int,
    duration: float,
    step: float = 0.05,
    profile: str = "urbano",
    pids: Sequence[int] = TEN_PIDS,
) -> list[tuple[float, ...]]:
    """Valores reais do modelo a cada `step` s de relógio simulado (sem tempo real)."""
    now = [0.0]
    sim = Simulator(lambda: now[0], profile=profile, seed_model=seed_model, seed_ecu=seed_ecu)
    out: list[tuple[float, ...]] = []
    for i in range(int(duration / step) + 1):
        now[0] = i * step
        out.append(tuple(sim.model.value(p) for p in pids))
    return out


# ---- infraestrutura do ensaio --------------------------------------------------------------


def _free_socket() -> socket.socket:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    return sock


async def _mqtt_link_factory() -> tuple[Callable[[], MqttLink], str]:
    """Mosquitto em localhost:1883 se houver; senão o broker em memória (registrado no JSON)."""
    try:
        probe = AiomqttLink(MQTT_HOST, MQTT_PORT, client_id="ensaio-sonda")
        await probe.connect()
        await probe.close()
        return (lambda: AiomqttLink(MQTT_HOST, MQTT_PORT)), "mosquitto"
    except (ConnectionError, OSError):
        try:
            from fakes import FakeBroker
        except ImportError:  # `python -m tests.benchmarks.eN`: tests/ não está no caminho
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from fakes import FakeBroker

        broker = FakeBroker()
        return broker.link, "memória (broker simulado: não há Mosquitto em localhost:1883)"


async def _wait_for(predicate: Callable[[], Awaitable[bool]], timeout_s: float) -> bool:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if await predicate():
            return True
        await asyncio.sleep(0.05)
    return await predicate()


async def run_scenario(sc: Scenario, out_dir: Path, *, db_name: str) -> RunOutput:
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / db_name
    db_path.unlink(missing_ok=True)
    storage = await SqlStorage.create(f"sqlite+aiosqlite:///{db_path}")

    # Simulador. O relógio é monotônico; as falhas são agendadas em tempo absoluto dele.
    sim = Simulator(
        time.monotonic, profile=sc.profile, seed_model=sc.seed_model, seed_ecu=sc.seed_ecu
    )
    sim.ecu.set_response_delay(*sc.delay_ms)
    sim.faults.set_frame_loss(sc.frame_loss)
    transport = TruthTransport(LoopbackTransport(sim.ecu, clock=time.monotonic), sim.ecu.log)

    # Servidor.
    link_factory: Callable[[], MqttLink] | None = None
    broker = "-"
    if sc.channel == "mqtt":
        link_factory, broker = await _mqtt_link_factory()
    app = create_app(storage, mqtt_link=link_factory)
    sock = _free_socket()
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    server_task = asyncio.create_task(server.serve(sockets=[sock]))
    while not server.started:
        await asyncio.sleep(0.01)

    inner: Publisher
    http_client: httpx.AsyncClient | None = None
    if sc.channel == "http":
        http_client = httpx.AsyncClient(base_url=f"http://127.0.0.1:{sock.getsockname()[1]}")
        inner = HttpPublisher(client=http_client)
    elif sc.channel == "mqtt":
        assert link_factory is not None
        inner = MqttPublisher(link_factory, "simulado")
    else:
        raise ValueError(f"canal desconhecido: {sc.channel!r}")
    publisher = TruthPublisher(inner, transport, time.monotonic, sc.fault_code)

    collector = Collector(
        transport,
        publisher,
        rates={pid: PidRate(1, i) for i, pid in enumerate(sc.pids)},
        timeout_ms=sc.timeout_ms,
    )
    await collector.start()
    t0 = time.monotonic()
    fault_at: float | None = None
    if sc.fault_code is not None:
        fault_at = t0 + sc.fault_at_s
        sim.faults.schedule_dtc(sc.fault_code, at=fault_at)
    interval = sc.interval_ms / 1000
    while (now := time.monotonic()) - t0 < sc.duration_s:
        await collector.run_cycle()
        rest = interval - (time.monotonic() - now)
        if rest > 0:
            await asyncio.sleep(rest)
    elapsed = time.monotonic() - t0

    async def all_stored() -> bool:
        return len(await storage.stored_samples()) >= publisher.delivered

    await _wait_for(all_stored, 5.0)  # o assinante MQTT pode estar atrasado em relação ao coletor

    stored = await storage.stored_samples()
    run_id = stored[0].run_id if stored else 0
    rows_stat = await storage.sample_rows(run_id)
    duplicated = await storage.count_comm_events(run_id, DUPLICATE) if stored else 0
    server_stats = compute_stats(rows_stat, duplicated=duplicated, now=time.time())

    if http_client is not None:
        await http_client.aclose()
    if isinstance(inner, MqttPublisher):
        await inner.aclose()
    await collector.close()
    server.should_exit = True
    await server_task
    sock.close()
    await storage.close()

    rows = _reading_rows(sc.label, stored, publisher.truth)
    _fill_true_values(db_path, publisher.truth, stored)

    metrics = _metrics(
        sc, rows, stored, publisher, server_stats.lost, duplicated, elapsed, fault_at
    )
    metrics["canal"] = sc.channel
    if sc.channel == "mqtt":
        metrics["broker"] = broker
    metrics["eventos_coletor"] = _count_events(collector)
    return RunOutput(sc, rows, metrics)


def _count_events(collector: Collector) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ev in collector.events:
        counts[ev.kind] = counts.get(ev.kind, 0) + 1
    return counts


def _reading_rows(
    label: str, stored: list[Any], truth: dict[int, dict[int, float]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in sorted(stored, key=lambda s: s.sample.seq):
        s = item.sample
        for name, pv in s.values.items():
            pid = int(pv.pid, 16)
            true = truth.get(s.seq, {}).get(pid)
            if true is None:
                continue
            rows.append(
                {
                    "run": label,
                    "seq": s.seq,
                    "ts_pub": s.ts,
                    "ts_recv": item.ts_recv,
                    "latency_ms": item.latency_ms,
                    "cycle_ms": s.cycle_ms,
                    "pid": pv.pid,
                    "name": name,
                    "unit": pv.unit,
                    "value": pv.value,
                    "true_value": true,
                    "error": abs(pv.value - true),
                    "resolution": PIDS[pid].resolution,
                    "rtt_ms": pv.rtt_ms,
                }
            )
    return rows


def _fill_true_values(db_path: Path, truth: dict[int, dict[int, float]], stored: list[Any]) -> None:
    """Grava `readings.true_value` (só o executor de ensaios preenche essa coluna)."""
    updates = [
        (value, item.sample.seq, f"0x{pid:02X}")
        for item in stored
        for pid, value in truth.get(item.sample.seq, {}).items()
        if any(pv.pid == f"0x{pid:02X}" for pv in item.sample.values.values())
    ]
    with sqlite3.connect(db_path) as db:
        db.executemany(
            "UPDATE readings SET true_value = ? WHERE pid = ? AND sample_id = "
            "(SELECT id FROM samples WHERE seq = ?)",
            [(v, pid, seq) for v, seq, pid in updates],
        )


def _metrics(
    sc: Scenario,
    rows: list[dict[str, Any]],
    stored: list[Any],
    publisher: TruthPublisher,
    gaps: int,
    duplicated: int,
    elapsed: float,
    fault_at: float | None,
) -> dict[str, Any]:
    samples = [s.sample for s in stored]
    received = len(samples)
    by_pid: dict[str, dict[str, Any]] = {}
    for name in sorted({r["name"] for r in rows}):
        sel = [r for r in rows if r["name"] == name]
        res = sel[0]["resolution"]
        errors = [r["error"] for r in sel]
        by_pid[name] = {
            "pid": sel[0]["pid"],
            "resolucao": res,
            "leituras": len(sel),
            "taxa_hz": len(sel) / elapsed,
            "erro": summarize(errors).as_dict(),
            "rtt_ms": summarize([r["rtt_ms"] for r in sel]).as_dict(),
            "acima_de_meia_resolucao": sum(1 for e in errors if e > res / 2 + 1e-9),
        }
    m: dict[str, Any] = {
        "duracao_s": elapsed,
        "ciclos": received,
        "ciclos_por_s": received / elapsed,
        "leituras": len(rows),
        "leituras_por_s": len(rows) / elapsed,
        "publicadas": publisher.delivered,
        "recebidas": received,
        "perdas": publisher.delivered - received + gaps,
        "perdas_por_lacuna_de_seq": gaps,
        "duplicacoes": duplicated,
        "timeouts": sum(s.errors.timeouts for s in samples),
        "invalidas": sum(s.errors.invalid for s in samples),
        "erro_acima_de_meia_resolucao": sum(p["acima_de_meia_resolucao"] for p in by_pid.values()),
        "por_pid": by_pid,
        "deteccao_falha_s": (
            publisher.fault_seen_at - fault_at
            if fault_at is not None and publisher.fault_seen_at is not None
            else None
        ),
        "recuperacao": _recovery(samples, sc.pids),
    }
    if rows:
        m["rtt_ms"] = summarize([r["rtt_ms"] for r in rows]).as_dict()
    if samples:
        m["ciclo_ms"] = summarize([s.cycle_ms for s in samples]).as_dict()
        m["latencia_ms"] = summarize([s.latency_ms for s in stored]).as_dict()
        m["rnf"] = _rnf(m)
    return m


def _recovery(samples: Sequence[Sample], pids: Sequence[int]) -> dict[str, int]:
    """Maior sequência de ciclos seguidos sem leitura de um mesmo PID (0 = nunca faltou)."""
    worst = 0
    for pid in pids:
        key = f"0x{pid:02X}"
        run = 0
        for s in sorted(samples, key=lambda x: x.seq):
            if any(pv.pid == key for pv in s.values.values()):
                run = 0
            else:
                run += 1
                worst = max(worst, run)
    return {"max_ciclos_sem_leitura": worst}


def _rnf(m: dict[str, Any]) -> dict[str, Any]:
    """RNF01 a RNF04 (docs/spec/01-visao-requisitos.md), medidos nesta execução."""
    cycle, latency = m["ciclo_ms"], m["latencia_ms"]
    rtt: dict[str, float] | None = m.get("rtt_ms")
    return {
        "RNF01_ciclo_p95_ms": cycle["p95"],
        "RNF01_ok": cycle["p95"] <= CYCLE_LIMIT_MS,
        "RNF02_latencia_p95_ms": latency["p95"],
        "RNF02_ok": latency["p95"] <= LATENCY_P95_LIMIT_MS,
        "RNF03_perdas": m["perdas"],
        "RNF03_ok": m["perdas"] == 0,
        "RNF04_ids": {
            "requisicao": f"0x{ID_FUNCTIONAL:03X}",
            "resposta": f"0x{ID_ENGINE_RESPONSE:03X}",
        },
        "RNF04_rtt_max_ms": rtt["max"] if rtt else None,
        "RNF04_ok": rtt is not None and rtt["max"] <= P2_MS and ID_FUNCTIONAL < 0x800,
    }


# ---- saída ---------------------------------------------------------------------------------


def machine_info() -> dict[str, Any]:
    return {
        "node": platform.node(),
        "so": platform.platform(),
        "python": sys.version.split()[0],
        "cpu": platform.processor() or platform.machine(),
        "nucleos": os.cpu_count(),
    }


def write_outputs(
    name: str,
    out_dir: Path,
    results: Sequence[RunOutput],
    *,
    config: dict[str, Any],
    csv_rows: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """`<nome>.csv` (uma linha por leitura) e `<nome>.json` (configuração, sementes, métricas)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = csv_rows if csv_rows is not None else [r for res in results for r in res.rows]
    stem = name.lower()
    if rows:
        with (out_dir / f"{stem}.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    doc: dict[str, Any] = {
        "ensaio": name.upper(),
        "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "maquina": machine_info(),
        "config": config,
        "runs": [
            {
                "label": res.scenario.label,
                "config": asdict(res.scenario),
                "metrics": res.metrics,
                **res.extra,
            }
            for res in results
        ],
    }
    (out_dir / f"{stem}.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return doc


def default_out_dir() -> Path:
    return RESULT_ROOT / datetime.now().strftime("%Y-%m-%d")


def parse_args(description: str, argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--duration", type=float, default=None, help="segundos por execução")
    p.add_argument("--out", type=Path, default=None, help="pasta de saída (padrão runs/<data>)")
    p.add_argument("--no-plots", action="store_true", help="não gera os gráficos")
    return p.parse_args(argv)


def print_table(doc: dict[str, Any]) -> None:
    for run in doc["runs"]:
        m = run["metrics"]
        if "ciclo_ms" in m:
            print(
                f"{doc['ensaio']} {run['label']:>10}  ciclo p95={m['ciclo_ms']['p95']:.1f} ms  "
                f"rtt p95={m.get('rtt_ms', {}).get('p95', float('nan')):.1f} ms  "
                f"lat p95={m['latencia_ms']['p95']:.1f} ms  perdas={m['perdas']}  "
                f"dup={m['duplicacoes']}  timeouts={m['timeouts']}  "
                f"erro>r/2={m['erro_acima_de_meia_resolucao']}  det={m['deteccao_falha_s']}"
            )
        else:
            print(f"{doc['ensaio']} {run['label']:>10}  {json.dumps(m, ensure_ascii=False)[:200]}")
