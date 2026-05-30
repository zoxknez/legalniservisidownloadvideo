from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.queue_manager import queue_manager
from backend.services.rts_adapter import RtsAdapter
from ._schemas import LoginRequest

router = APIRouter()


@router.post("/login")
def rts_login(req: LoginRequest):
    res = RtsAdapter.save_credentials(req.email, req.password)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


class RtsDownloadRequest(BaseModel):
    target_url: str
    start_ep: Optional[int] = None
    end_ep: Optional[int] = None
    verbose: bool = False


@router.post("/download")
async def rts_download(req: RtsDownloadRequest):
    cmd = RtsAdapter.make_download_cmd(req.target_url, req.start_ep, req.end_ep, req.verbose)
    title = f"RTS Planeta: {req.target_url.split('/')[-1]}"
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
        raise HTTPException(status_code=400, detail="Provide url or video_id query parameter.")

    result = RtsAdapter.get_video_info(vid)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Video not found"))
    return result
