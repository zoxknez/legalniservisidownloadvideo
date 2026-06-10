from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.queue_manager import queue_manager
from backend.services.hbo_adapter import HboAdapter

router = APIRouter()


class HboLoginRequest(BaseModel):
    market: Literal["emea", "latam", "us"] = "emea"


@router.post("/login")
async def hbo_login(req: HboLoginRequest):
    import importlib.util
    from backend.core.services.runner import HBO_DOWNLOADER

    if importlib.util.find_spec(HBO_DOWNLOADER) is None:
        raise HTTPException(
            status_code=503,
            detail=f"HBO Max engine ({HBO_DOWNLOADER}) nije dostupan.",
        )
    cmd = HboAdapter.make_login_cmd(req.market)
    title = "HBO Max Login Session"
    task_id = await queue_manager.add_download("hbomax", title, cmd)
    return {"success": True, "task_id": task_id}


@router.get("/status")
def hbo_status():
    return HboAdapter.get_auth_status()


class HboDownloadRequest(BaseModel):
    video_id: str = Field(min_length=1)
    subs: str = "sr,hr,mk,bs,sl"
    market: Literal["emea", "latam", "us"] = "emea"


@router.post("/download")
async def hbo_download(req: HboDownloadRequest):
    status = HboAdapter.get_auth_status()
    if not status.get("authenticated"):
        raise HTTPException(
            status_code=401,
            detail="Niste prijavljeni na HBO Max. Pokrenite login prvo.",
        )
    cmd = HboAdapter.make_download_cmd(req.video_id.strip(), req.subs, req.market)
    title = f"HBO Max: {req.video_id.strip()}"
    task_id = await queue_manager.add_download("hbomax", title, cmd)
    return {"success": True, "task_id": task_id}


class HboDirectDownloadRequest(BaseModel):
    manifest_url: str = Field(min_length=10)
    license_url: str = Field(min_length=10)
    title: str = ""
    subs: str = "sr,hr,mk,bs,sl"


@router.post("/download-direct")
async def hbo_download_direct(req: HboDirectDownloadRequest):
    cmd = HboAdapter.make_download_direct_cmd(req.manifest_url, req.license_url, req.title, req.subs)
    display_title = req.title.strip() if req.title.strip() else f"HBO Max Direct: {req.manifest_url[:40]}…"
    task_id = await queue_manager.add_download("hbomax", display_title, cmd)
    return {"success": True, "task_id": task_id}
