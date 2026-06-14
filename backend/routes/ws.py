import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.middleware.api_key import is_authorized
from backend.queue_manager import queue_manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/ws-ticket")
async def get_websocket_ticket():
    from backend.middleware.api_key import create_ws_ticket
    token = create_ws_ticket()
    return {"ticket": token}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if not is_authorized(websocket):
        await websocket.close(code=1008, reason="Unauthorized")
        return
    await queue_manager.register_websocket(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        queue_manager.unregister_websocket(websocket)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        queue_manager.unregister_websocket(websocket)
