import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.queue_manager import queue_manager
from backend.services.voyo_adapter import VoyoAdapter
from ._schemas import LoginRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/login")
def voyo_login(req: LoginRequest):
    res = VoyoAdapter.login(req.email, req.password, variant=req.variant)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/status")
def voyo_status():
    return VoyoAdapter.get_auth_status()


@router.get("/profiles")
def voyo_profiles():
    try:
        return VoyoAdapter.get_profiles()
    except Exception as e:
        logger.exception("Failed to fetch Voyo profiles")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/series/{series_id}")
def voyo_series_info(series_id: int):
    try:
        res = VoyoAdapter.get_series_info(series_id)
        if not res.get("success"):
            raise HTTPException(status_code=404, detail=res.get("error"))
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch Voyo series info")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/resolve")
def voyo_resolve(target: str = ""):
    """Resolve a video URL/ID to its parent series info."""
    if not target.strip():
        raise HTTPException(status_code=400, detail="Unesite URL ili ID serije.")
    try:
        category = VoyoAdapter.resolve_to_category(target.strip())
        cat_id = category.get("id")
        if cat_id:
            res = VoyoAdapter.get_series_info(cat_id)
            if res.get("success"):
                return res
        raise HTTPException(status_code=404, detail="Nije moguće pronaći seriju.")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Voyo resolve failed")
        raise HTTPException(status_code=500, detail=str(e))


class VoyoDownloadRequest(BaseModel):
    target: str = Field(min_length=1)
    mode: Literal["video", "series"]
    episodes: str = ""
    resolution: str = "1080p"
    video_ids: Optional[List[int]] = None


@router.post("/download")
async def voyo_download(req: VoyoDownloadRequest):
    auth = VoyoAdapter.get_auth_status()
    if not auth.get("authenticated"):
        raise HTTPException(
            status_code=401,
            detail="Niste prijavljeni na Voyo. Unesite kredencijale u Postavkama.",
        )

    if req.video_ids and req.mode == "series":
        cmd = VoyoAdapter.make_download_batch_cmd(req.video_ids, resolution=req.resolution)
        title = f"Voyo: {len(req.video_ids)} epizoda"
        task_id = await queue_manager.add_download("voyo", title, cmd)
        return {"success": True, "queued": len(req.video_ids), "task_id": task_id}

    cmd = VoyoAdapter.make_download_cmd(
        req.target.strip(), req.mode, req.episodes.strip(), req.resolution
    )
    title = f"Voyo: {req.target.strip()} ({req.mode})"
    task_id = await queue_manager.add_download("voyo", title, cmd)
    return {"success": True, "task_id": task_id}
