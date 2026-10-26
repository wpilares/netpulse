import asyncio
import contextlib
from typing import Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from netpulse_api.live import (
    SLOW_CONSUMER_CLOSE_CODE,
    SLOW_CONSUMER_REASON,
    LiveKpiBroadcaster,
    Subscription,
)


class ClientMessage(BaseModel):
    type: Literal["ping"]


async def answer_client_messages(websocket: WebSocket) -> None:
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


async def forward_frames(websocket: WebSocket, subscription: Subscription) -> None:
    with contextlib.suppress(WebSocketDisconnect):
        async for frame in subscription:
            await websocket.send_json(frame.model_dump(mode="json"))
        if subscription.dropped:
            await websocket.close(code=SLOW_CONSUMER_CLOSE_CODE, reason=SLOW_CONSUMER_REASON)


async def stop_forwarding(sender: asyncio.Task[None]) -> None:
    sender.cancel()
    await asyncio.wait({sender})
    if not sender.cancelled():
        sender.result()


def build_telemetry_router(
    version: str, *, broadcaster: LiveKpiBroadcaster | None = None
) -> APIRouter:
    router = APIRouter(tags=["telemetry"])

    @router.websocket("/ws/telemetry")
    async def telemetry(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({"type": "hello", "version": version})
        if broadcaster is None:
            await answer_client_messages(websocket)
            return
        subscription = broadcaster.subscribe()
        sender = asyncio.create_task(forward_frames(websocket, subscription))
        try:
            await answer_client_messages(websocket)
        finally:
            broadcaster.unsubscribe(subscription)
            await stop_forwarding(sender)

    return router
