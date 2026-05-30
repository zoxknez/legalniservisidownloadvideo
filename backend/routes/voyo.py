from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.queue_manager import queue_manager
from backend.services.voyo_adapter import VoyoAdapter
from ._schemas import LoginRequest

router = APIRouter()


@router.post("/login")
def voyo_login(req: LoginRequest):
    res = VoyoAdapter.login(req.email, req.password)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/profiles")
def voyo_profiles():
    return VoyoAdapter.get_profiles()


@router.get("/series/{series_id}")
def voyo_series_info(series_id: int):
    res = VoyoAdapter.get_series_info(series_id)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("error"))
    return res


@router.get("/resolve")
def voyo_resolve(target: str = ""):
    """Resolve a video URL/ID to its parent series info."""
    if not target.strip():
        raise HTTPException(status_code=400, detail="Provide a target URL or ID")
    try:
        category = VoyoAdapter.resolve_to_category(target)
        cat_id = category.get("id")
        if cat_id:
            res = VoyoAdapter.get_series_info(cat_id)
            if res.get("success"):
                return res
        raise HTTPException(status_code=404, detail="Could not resolve series")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class VoyoDownloadRequest(BaseModel):
    target: str
    mode: str
    episodes: str = ""
    resolution: str = "1080p"
    video_ids: Optional[List[int]] = None


@router.post("/download")
async def voyo_download(req: VoyoDownloadRequest):
    if req.video_ids and req.mode == "series":
        for vid in req.video_ids:
            cmd = VoyoAdapter.make_download_cmd(str(vid), "video", resolution=req.resolution)
            title = f"Voyo: video {vid}"
            await queue_manager.add_download("voyo", title, cmd)
        return {"success": True, "queued": len(req.video_ids)}

    cmd = VoyoAdapter.make_download_cmd(req.target, req.mode, req.episodes, req.resolution)
    title = f"Voyo: {req.target} ({req.mode})"
    task_id = await queue_manager.add_download("voyo", title, cmd)
    return {"success": True, "task_id": task_id}
