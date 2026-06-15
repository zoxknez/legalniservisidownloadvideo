import ipaddress
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.queue_manager import queue_manager
from backend.services.hbo_adapter import HboAdapter

router = APIRouter()
MAX_DIRECT_URL_LEN = 4096


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
    subs: str = "all"
    audio: str = "all"
    market: Literal["emea", "latam", "us"] = "emea"


@router.post("/download")
async def hbo_download(req: HboDownloadRequest):
    status = HboAdapter.get_auth_status()
    if not status.get("authenticated"):
        raise HTTPException(
            status_code=401,
            detail="Niste prijavljeni na HBO Max. Pokrenite login prvo.",
        )
    cmd = HboAdapter.make_download_cmd(
        req.video_id.strip(), req.subs, req.market, req.audio
    )
    title = f"HBO Max: {req.video_id.strip()}"
    task_id = await queue_manager.add_download("hbomax", title, cmd)
    return {"success": True, "task_id": task_id}


class HboDirectDownloadRequest(BaseModel):
    manifest_url: str = Field(min_length=10, max_length=MAX_DIRECT_URL_LEN)
    license_url: str = Field(min_length=10, max_length=MAX_DIRECT_URL_LEN)
    title: str = ""
    subs: str = "all"
    audio: str = "all"


def _validate_public_https_url(value: str, label: str) -> str:
    url = value.strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().lower()
    if parsed.scheme != "https" or not host:
        raise HTTPException(status_code=400, detail=f"{label} mora biti javni HTTPS URL.")
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise HTTPException(status_code=400, detail=f"{label} ne sme pokazivati na lokalnu mrezu.")
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(status_code=400, detail=f"{label} ne sme pokazivati na lokalnu mrezu.")
    except ValueError:
        if "." not in host:
            raise HTTPException(status_code=400, detail=f"{label} mora imati javni domen.")
    return url


@router.post("/download-direct")
async def hbo_download_direct(req: HboDirectDownloadRequest):
    manifest_url = _validate_public_https_url(req.manifest_url, "Manifest URL")
    license_url = _validate_public_https_url(req.license_url, "License URL")
    cmd = HboAdapter.make_download_direct_cmd(
        manifest_url, license_url, req.title, req.subs, req.audio
    )
    display_title = req.title.strip() if req.title.strip() else f"HBO Max Direct: {manifest_url[:40]}…"
    task_id = await queue_manager.add_download("hbomax", display_title, cmd)
    return {"success": True, "task_id": task_id}
