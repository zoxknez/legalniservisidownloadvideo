import logging
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import config
from backend.queue_manager import queue_manager
from ._schemas import SnifferPayload

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/detect")
async def sniffer_detect(data: SnifferPayload):
    from backend.sniffer_service import process_sniffer_event

    return await process_sniffer_event(
        queue_manager,
        service=data.service,
        sniffer_type=data.type,
        url=data.url,
        headers=data.headers,
        title=data.title,
    )


class SnifferImportRequest(BaseModel):
    service: str
    type: str
    url: str
    headers: Optional[Dict[str, str]] = None
    title: Optional[str] = ""


@router.post("/import")
async def sniffer_import(req: SnifferImportRequest):
    from backend.sniffer_service import process_sniffer_event

    logger.info("Imported sniffed resource for %s: %s", req.service, req.type)
    return await process_sniffer_event(
        queue_manager,
        service=req.service,
        sniffer_type=req.type,
        url=req.url,
        headers=req.headers,
        title=req.title or "",
    )


@router.get("/captures")
def sniffer_captures():
    from backend.sniffer_store import sniffer_store

    return {
        "captures": sniffer_store.list_all(),
        "auto_download": config.data.get("sniffer", {}).get("auto_download", True),
    }


class SnifferDownloadRequest(BaseModel):
    service: str
    subs: str = "sr,hr,mk,bs,sl"


@router.post("/download")
async def sniffer_download(req: SnifferDownloadRequest):
    from backend.sniffer_download import queue_sniffer_download
    from backend.sniffer_store import sniffer_store

    capture = sniffer_store.get(req.service)
    if not capture or not capture.is_ready():
        raise HTTPException(
            status_code=400,
            detail="Manifest i/ili license nisu spremni. Pustite video dok je Tampermonkey aktivan.",
        )
    try:
        result = await queue_sniffer_download(queue_manager, capture, subs=req.subs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    sniffer_store.mark_queued(capture.service, result["task_id"])
    await queue_manager.broadcast_sniffer_download_queued(
        service=capture.service,
        task_id=result["task_id"],
        title=result["title"],
        auto=False,
    )
    return result
