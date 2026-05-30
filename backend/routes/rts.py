import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.queue_manager import queue_manager
from backend.services.rts_adapter import RtsAdapter
from ._schemas import LoginRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/login")
def rts_login(req: LoginRequest):
    res = RtsAdapter.save_credentials(req.email, req.password)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/status")
def rts_status():
    return RtsAdapter.get_auth_status()


class RtsDownloadRequest(BaseModel):
    target_url: str = Field(min_length=1)
    start_ep: Optional[int] = Field(default=None, ge=1)
    end_ep: Optional[int] = Field(default=None, ge=1)
    verbose: bool = False


@router.post("/download")
async def rts_download(req: RtsDownloadRequest):
    auth = RtsAdapter.get_auth_status()
    if not auth.get("authenticated"):
        raise HTTPException(
            status_code=401,
            detail="Niste prijavljeni na RTS Planetu. Unesite kredencijale u Postavkama.",
        )
    target = req.target_url.strip()
    cmd = RtsAdapter.make_download_cmd(target, req.start_ep, req.end_ep, req.verbose)
    title = f"RTS Planeta: {target.split('/')[-1]}"
    task_id = await queue_manager.add_download("rtsplaneta", title, cmd)
    return {"success": True, "task_id": task_id}


@router.get("/video-info")
def rts_video_info(url: str = "", video_id: str = ""):
    from backend.core.services.rtsplaneta.rtsplaneta_downloader import RTSPlanetaDownloader

    vid = video_id.strip()
    if url.strip():
        try:
            vid = RTSPlanetaDownloader().extract_video_id(url.strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not vid:
        raise HTTPException(status_code=400, detail="Unesite URL ili video ID.")

    try:
        result = RtsAdapter.get_video_info(vid)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error", "Video nije pronađen"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("RTS video-info failed")
        raise HTTPException(status_code=503, detail=str(e))
