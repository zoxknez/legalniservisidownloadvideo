import tempfile
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.queue_manager import queue_manager
from backend.services.skyshowtime_adapter import SkyShowtimeAdapter

router = APIRouter()


class SkyLoginRequest(BaseModel):
    cookies_text: Optional[str] = None
    cookies: Optional[Dict[str, str]] = None


@router.post("/login")
async def skyshowtime_login(req: SkyLoginRequest):
    if req.cookies_text:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(req.cookies_text)
            temp_path = f.name
        cmd = SkyShowtimeAdapter.make_login_cmd(cookie_file=temp_path)
        title = "SkyShowtime Login (cookies.txt)"
    elif req.cookies:
        cmd = SkyShowtimeAdapter.make_login_cmd(cookies=req.cookies)
        title = "SkyShowtime Login (Auto-sync)"
    else:
        raise HTTPException(status_code=400, detail="Nedostaju podaci za prijavu (kolačići).")

    task_id = await queue_manager.add_download("skyshowtime", title, cmd)
    return {"success": True, "task_id": task_id}


@router.post("/sync-browser")
async def skyshowtime_sync_browser():
    from backend.services.browser_cookies import browser_sync_supported, sync_skyshowtime_from_browser_cookies

    if not browser_sync_supported():
        raise HTTPException(
            status_code=400,
            detail=(
                "Automatska sinhronizacija iz pretraživača je dostupna samo na Windows-u "
                "(Chrome/Edge/Brave + DPAPI)."
            ),
        )

    synced = sync_skyshowtime_from_browser_cookies()
    status = SkyShowtimeAdapter.get_auth_status()
    if synced and status.get("authenticated"):
        return {
            "success": True,
            "authenticated": True,
            "message": "SkyShowtime sesija je uspešno sinhronizovana iz pretraživača.",
            **status,
        }

    raise HTTPException(
        status_code=400,
        detail=(
            "Nisu pronađeni SkyShowtime kolačići. Ulogujte se na skyshowtime.com u Chrome, "
            "Edge ili Brave pretraživaču i zatvorite ga pre ponovnog pokušaja."
        ),
    )


@router.get("/status")
def skyshowtime_status():
    return SkyShowtimeAdapter.get_auth_status()


@router.get("/resolve")
def skyshowtime_resolve(target: str = ""):
    if not target.strip():
        raise HTTPException(status_code=400, detail="Unesite URL serije.")
    try:
        result = SkyShowtimeAdapter.resolve_to_series(target.strip())
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/series")
def skyshowtime_series(target: str = ""):
    if not target.strip():
        raise HTTPException(status_code=400, detail="Unesite URL serije.")
    result = SkyShowtimeAdapter.get_series_info(target.strip())
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Serija nije pronađena."))
    return result


class SkyDownloadRequest(BaseModel):
    url: str = Field(min_length=1)
    season: Optional[int] = None
    start_ep: int = 1
    end_ep: int = 999
    vcodec: Literal["H264", "H265"] = "H264"
    quality: Literal["SDR", "HDR10", "DV"] = "SDR"
    audio_lang: Optional[str] = None
    episode_refs: Optional[List[str]] = None


@router.post("/download")
async def skyshowtime_download(req: SkyDownloadRequest):
    status = SkyShowtimeAdapter.get_auth_status()
    if not status.get("authenticated"):
        raise HTTPException(
            status_code=401,
            detail="Niste prijavljeni na SkyShowtime. Prvo se prijavite uvozom kolačića.",
        )

    if req.episode_refs:
        cmd = SkyShowtimeAdapter.make_download_batch_cmd(
            url=req.url.strip(),
            episode_refs=req.episode_refs,
            vcodec=req.vcodec,
            quality=req.quality,
            audio_lang=req.audio_lang,
        )
        title = f"SkyShowtime: {len(req.episode_refs)} epizoda"
        task_id = await queue_manager.add_download("skyshowtime", title, cmd)
        return {"success": True, "queued": len(req.episode_refs), "task_id": task_id}

    cmd = SkyShowtimeAdapter.make_download_cmd(
        url=req.url.strip(),
        season=req.season,
        start_ep=req.start_ep,
        end_ep=req.end_ep,
        vcodec=req.vcodec,
        quality=req.quality,
        audio_lang=req.audio_lang,
    )
    title = f"SkyShowtime: {req.url.strip()}"
    task_id = await queue_manager.add_download("skyshowtime", title, cmd)
    return {"success": True, "task_id": task_id}


class SkyDirectDownloadRequest(BaseModel):
    manifest_url: str = Field(min_length=10)
    license_url: str = Field(min_length=10)
    title: str = ""
    license_token: str = ""
    vcodec: Literal["H264", "H265"] = "H264"
    quality: Literal["SDR", "HDR10", "DV"] = "SDR"
    audio_lang: Optional[str] = None


@router.post("/download-direct")
async def skyshowtime_download_direct(req: SkyDirectDownloadRequest):
    status = SkyShowtimeAdapter.get_auth_status()
    if not status.get("authenticated"):
        raise HTTPException(
            status_code=401,
            detail="Niste prijavljeni na SkyShowtime. Prvo se prijavite.",
        )
    cmd = SkyShowtimeAdapter.make_download_direct_cmd(
        manifest_url=req.manifest_url.strip(),
        license_url=req.license_url.strip(),
        title=req.title.strip(),
        license_token=req.license_token.strip(),
        vcodec=req.vcodec,
        quality=req.quality,
        audio_lang=req.audio_lang,
    )
    display_title = req.title.strip() if req.title.strip() else f"SkyShowtime Direct: {req.manifest_url[:40]}…"
    task_id = await queue_manager.add_download("skyshowtime", display_title, cmd)
    return {"success": True, "task_id": task_id}
