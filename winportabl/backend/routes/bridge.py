from typing import Dict, Optional, Any

import hmac

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from backend.queue_manager import queue_manager
from backend.server_settings import ensure_bridge_token, get_api_key
from ._schemas import SnifferPayload

router = APIRouter()


class BridgeSessionRequest(BaseModel):
    service: Optional[str] = None
    session_data: Optional[str] = None
    batch: Optional[Dict[str, Any]] = None
    source: str = "bridge"
    reason: Optional[str] = None


def _authorize_bridge_request(request: Request) -> None:
    expected = ensure_bridge_token()
    provided = request.headers.get("x-vds-bridge-token", "").strip()
    if provided and hmac.compare_digest(provided, expected):
        return

    api_key = get_api_key()
    provided_api_key = request.headers.get("x-api-key", "").strip()
    if api_key and provided_api_key and hmac.compare_digest(provided_api_key, api_key):
        return

    raise HTTPException(
        status_code=401,
        detail="Neautorizovan bridge zahtev. Instalirajte svež userscript iz podešavanja.",
    )


@router.post("/session")
async def bridge_session(req: BridgeSessionRequest, request: Request):
    from backend.bridge import import_session_payload, imported_service_names

    _authorize_bridge_request(request)
    try:
        result = import_session_payload(
            service=req.service,
            session_data=req.session_data,
            batch=req.batch,
            source=req.source or "bridge",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    services = imported_service_names(result)
    if services:
        await queue_manager.broadcast_session_import(
            services=services,
            message=result.get("message", "Sesija uvezena"),
            source=req.source or "bridge",
        )
    return result


@router.post("/sniffer")
async def bridge_sniffer(data: SnifferPayload, request: Request):
    from backend.sniffer_service import process_sniffer_event

    _authorize_bridge_request(request)
    return await process_sniffer_event(
        queue_manager,
        service=data.service,
        sniffer_type=data.type,
        url=data.url,
        headers=data.headers,
        title=data.title,
    )


@router.get("/userscript.js")
def bridge_userscript():
    from backend.bridge import load_userscript

    try:
        script = load_userscript()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return Response(content=script, media_type="text/javascript; charset=utf-8")
