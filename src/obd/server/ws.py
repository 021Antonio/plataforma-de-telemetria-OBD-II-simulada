"""WebSocket /ws/stream: reenvia os últimos 60 s ao conectar e depois transmite ao vivo."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from obd.server.state import ServerState

REPLAY_S = 60.0


def build_ws_router(state: ServerState) -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws/stream")
    async def stream(websocket: WebSocket) -> None:
        await websocket.accept()
        # Inscreve antes de ler o histórico: nada publicado depois do instante do replay se perde.
        queue = state.hub.subscribe()
        since = state.clock() - REPLAY_S
        try:
            for stored in await state.storage.stored_samples(since=since):
                await websocket.send_json({"type": "sample", "data": stored.sample.model_dump()})
            for report in await state.storage.dtc_reports(since=since):
                await websocket.send_json({"type": "dtc", "data": report.model_dump()})
            while True:
                await websocket.send_json(await queue.get())
        except (WebSocketDisconnect, RuntimeError):
            pass  # cliente saiu durante o envio
        finally:
            state.hub.unsubscribe(queue)

    return router
