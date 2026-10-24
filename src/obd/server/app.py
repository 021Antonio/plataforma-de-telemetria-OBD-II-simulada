"""Fábrica da aplicação FastAPI do servidor da plataforma (porta 8000)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from obd.mqtt_common import LinkFactory
from obd.server.mqtt_subscriber import MqttSubscriber
from obd.server.routes import build_router
from obd.server.state import ServerState
from obd.server.storage import Storage
from obd.server.ws import build_ws_router

DASHBOARD_DIR = Path(__file__).resolve().parents[1] / "web" / "dashboard"


def create_app(
    storage: Storage,
    clock: Callable[[], float] = time.time,
    *,
    mqtt_link: LinkFactory | None = None,
) -> FastAPI:
    """`mqtt_link` liga o assinante MQTT (publisher: mqtt); sem ele só o HTTP grava."""
    state = ServerState(storage=storage, clock=clock)
    subscriber = MqttSubscriber(mqtt_link, state) if mqtt_link is not None else None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if subscriber is not None:
            subscriber.start()
        try:
            yield
        finally:
            if subscriber is not None:
                await subscriber.stop()

    app = FastAPI(title="Plataforma de telemetria OBD-II", lifespan=lifespan)
    app.include_router(build_router(state))
    app.include_router(build_ws_router(state))
    # Montado por último: o `/` estático não pode engolir as rotas da API.
    if DASHBOARD_DIR.is_dir():
        app.mount("/", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")
    return app
