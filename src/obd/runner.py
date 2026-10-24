"""Orquestração (`python -m obd run`): servidor, painel, ELM327 e coletor num só processo asyncio.

Todos compartilham o mesmo `Simulator`, então um override feito no painel muda a leitura do coletor.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import signal
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn
import yaml
from fastapi import FastAPI

from obd.collector.collector import Collector
from obd.collector.factory import build_publisher, build_transport
from obd.collector.scheduler import CollectorConfig
from obd.server.app import create_app
from obd.server.storage import SqlStorage
from obd.simulator.control_api import Simulator, create_control_app
from obd.simulator.elm327_server import Elm327Server
from obd.simulator.vehicle_model import VehicleConfig

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "default.yaml"
DEFAULT_DB = Path("data") / "obd.db"
LOCAL = "127.0.0.1"
START_TIMEOUT_S = 10.0
GRACEFUL_S = 2


@dataclass(frozen=True)
class RunOptions:
    config: Path = DEFAULT_CONFIG
    profile: str = "urbano"
    db: Path = DEFAULT_DB
    elm327: bool = True
    host: str = LOCAL
    server_port: int | None = None
    panel_port: int | None = None
    elm327_port: int | None = None


class _Uvicorn(uvicorn.Server):
    """Uvicorn sem tratamento próprio de sinais: quem encerra o processo é o `run`."""

    def install_signal_handlers(self) -> None:
        return None

    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        yield


def _serve(app: FastAPI, host: str, port: int) -> _Uvicorn:
    cfg = uvicorn.Config(
        app, host=host, port=port, log_level="warning", timeout_graceful_shutdown=GRACEFUL_S
    )
    return _Uvicorn(cfg)


async def _serve_task(server: _Uvicorn) -> None:
    try:
        await server.serve()
    except SystemExit as exc:  # uvicorn chama sys.exit(1) quando não consegue abrir a porta
        raise RuntimeError("não foi possível abrir a porta do servidor HTTP") from exc


async def _wait_started(server: _Uvicorn, task: asyncio.Task[None]) -> None:
    async with asyncio.timeout(START_TIMEOUT_S):
        while not server.started:
            if task.done():
                task.result()
                raise RuntimeError("servidor HTTP encerrou durante a inicialização")
            await asyncio.sleep(0.02)


def _load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"configuração inválida: {path}")
    return data


async def run(opts: RunOptions, stop: asyncio.Event | None = None) -> None:
    """Sobe tudo e espera `stop` (ou cancelamento); encerra na ordem inversa, sem traceback."""
    stop = stop or asyncio.Event()
    cfg = _load_config(opts.config)
    portas = cfg.get("portas", {})
    server_port = opts.server_port if opts.server_port is not None else portas.get("servidor", 8000)
    panel_port = opts.panel_port if opts.panel_port is not None else portas.get("painel", 8001)
    elm_port = opts.elm327_port if opts.elm327_port is not None else portas.get("elm327_tcp", 35000)
    if cfg.get("publisher", "http") == "http":
        alvo = LOCAL if opts.host == "0.0.0.0" else opts.host
        cfg["servidor_url"] = f"http://{alvo}:{server_port}"

    sim = Simulator(profile=opts.profile, config=VehicleConfig.from_yaml(opts.config))
    opts.db.parent.mkdir(parents=True, exist_ok=True)
    storage = await SqlStorage.create(f"sqlite+aiosqlite:///{opts.db}")

    web = _serve(create_app(storage), opts.host, server_port)
    panel = _serve(create_control_app(sim), opts.host, panel_port)
    tasks = [asyncio.create_task(_serve_task(s)) for s in (web, panel)]
    elm: Elm327Server | None = None
    collector: Collector | None = None
    collector_task: asyncio.Task[None] | None = None
    publisher = build_publisher(cfg)
    try:
        await _wait_started(web, tasks[0])
        await _wait_started(panel, tasks[1])

        # O ELM327 e o coletor (loopback) usam a mesma instância: um só lock sobre a ECU.
        coletor_cfg = CollectorConfig.from_dict(cfg.get("coletor", {}))
        kind = cfg.get("coletor", {}).get("transporte", "loopback")
        bus = build_transport("loopback", ecu=sim)
        if opts.elm327:
            elm = Elm327Server(bus, host=opts.host, port=elm_port)
            await elm.start()
        transport = (
            bus
            if kind == "loopback"
            else build_transport(kind, host=LOCAL, port=elm.port if elm else elm_port)
        )
        interval_ms = cfg.get("coletor", {}).get("intervalo_ms", 100)
        collector = Collector(
            transport,
            publisher,
            rates=coletor_cfg.plan,
            timeout_ms=cfg.get("coletor", {}).get("timeout_ms", 100),
            dtc_interval_s=cfg.get("coletor", {}).get("dtc_intervalo_s", 2.0),
        )
        await collector.start()
        collector_task = asyncio.create_task(collector.run(interval_s=interval_ms / 1000))

        print(f"dashboard: http://localhost:{server_port}/", flush=True)
        print(f"painel:    http://localhost:{panel_port}/", flush=True)
        if elm:
            print(f"ELM327:    localhost:{elm.port}", flush=True)
        waiters = {asyncio.create_task(stop.wait()), collector_task, *tasks}
        await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
        for t in (collector_task, *tasks):
            if t.done() and not t.cancelled() and t.exception() is not None:
                t.result()  # propaga a falha de um componente
        for w in waiters:
            if w not in (collector_task, *tasks):
                w.cancel()
    finally:
        if collector_task is not None:
            collector_task.cancel()
            await asyncio.gather(collector_task, return_exceptions=True)
        if collector is not None:
            await collector.close()
        if elm is not None:
            await elm.stop()
        aclose = getattr(publisher, "aclose", None)
        if aclose is not None:
            await aclose()
        for s in (web, panel):
            s.should_exit = True
        await asyncio.gather(*tasks, return_exceptions=True)
        await storage.close()


async def _main(opts: RunOptions) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    await run(opts, stop)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m obd")
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="sobe servidor, simulador e coletor")
    r.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    r.add_argument("--perfil", default="urbano")
    r.add_argument("--db", type=Path, default=DEFAULT_DB)
    r.add_argument("--sem-elm327", action="store_true")
    r.add_argument("--host", default=LOCAL, help="interface de escuta (0.0.0.0 em contêiner)")
    r.add_argument("--porta-servidor", type=int)
    r.add_argument("--porta-painel", type=int)
    r.add_argument("--porta-elm327", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    opts = RunOptions(
        config=args.config,
        profile=args.perfil,
        db=args.db,
        elm327=not args.sem_elm327,
        host=args.host,
        server_port=args.porta_servidor,
        panel_port=args.porta_painel,
        elm327_port=args.porta_elm327,
    )
    try:
        asyncio.run(_main(opts))
    except Exception as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    return 0
