"""WebSocket de actualizaciones en vivo.

En local no exigimos token en el WebSocket (acceso en tu red); las acciones que mutan
estado siguen protegidas por la API REST con token.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.bot.engine import engine
from app.bot.ws_manager import manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        # Estado inicial al conectar.
        await engine.broadcast_state()
        # Mantener viva la conexión (ignoramos lo que envíe el cliente).
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:  # noqa: BLE001
        await manager.disconnect(websocket)
