from typing import Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError


class ClientMessage(BaseModel):
    type: Literal["ping"]


def build_telemetry_router(version: str) -> APIRouter:
    router = APIRouter(tags=["telemetry"])

    @router.websocket("/ws/telemetry")
    async def telemetry(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({"type": "hello", "version": version})
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    ClientMessage.model_validate_json(raw)
                except ValidationError:
                    await websocket.send_json({"type": "error", "reason": "unsupported message"})
                    continue
                await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            return

    return router
