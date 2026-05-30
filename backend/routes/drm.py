import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from backend.server_settings import allow_drm_key_export
from backend.services.drm_manager import drm_manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def drm_health():
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, drm_manager.get_health_report)


@router.post("/reload")
async def drm_reload():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, drm_manager.reload)
    report = await loop.run_in_executor(None, drm_manager.get_health_report)
    return {"success": True, "health": report}


@router.get("/wvd/discover")
async def wvd_discover():
    from backend.wvd_installer import discover_wvd_files

    loop = asyncio.get_running_loop()
    files = await loop.run_in_executor(None, discover_wvd_files)
    return {"files": files, "canonical": str(Path.home() / ".videodownload" / "device.wvd")}


@router.post("/wvd/auto-install")
async def wvd_auto_install():
    from backend.wvd_installer import auto_install_wvd

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, auto_install_wvd)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Auto-instalacija nije uspela."))
    health = await loop.run_in_executor(None, drm_manager.get_health_report)
    return {**result, "health": health}


class WvdBase64InstallRequest(BaseModel):
    base64: str


@router.post("/wvd/install-base64")
async def wvd_install_base64(req: WvdBase64InstallRequest):
    from backend.wvd_installer import install_wvd_from_base64

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: install_wvd_from_base64(req.base64))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Instalacija nije uspela."))
    health = await loop.run_in_executor(None, drm_manager.get_health_report)
    return {**result, "health": health}


@router.post("/wvd/upload")
async def wvd_upload(file: UploadFile = File(...)):
    from backend.wvd_installer import install_wvd_bytes

    data = await file.read()
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: install_wvd_bytes(data))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Upload nije uspeo."))
    health = await loop.run_in_executor(None, drm_manager.get_health_report)
    return {**result, "health": health}


@router.post("/cache/clear")
def drm_cache_clear():
    drm_manager.key_cache.invalidate_all()
    return {"success": True, "message": "Key cache ociscen."}


@router.get("/cache/stats")
def drm_cache_stats():
    return drm_manager.key_cache.stats()


class DrmPrefetchCertRequest(BaseModel):
    service: str
    license_url: str
    headers: Optional[Dict[str, str]] = None


@router.post("/prefetch-cert")
async def drm_prefetch_cert(req: DrmPrefetchCertRequest):
    loop = asyncio.get_running_loop()
    ok = await loop.run_in_executor(
        None,
        lambda: drm_manager.prefetch_provider_cert(req.service, req.license_url, req.headers),
    )
    if ok:
        return {"success": True, "message": f"Provider sertifikat preuzet za '{req.service}'."}
    return {"success": False, "message": "Prefetch nije uspio (server mozda ne podrzava service cert)."}


class DrmTestKeysRequest(BaseModel):
    mpd_url: str
    license_url: str
    headers: Optional[Dict[str, str]] = None
    service: str = "manual"


@router.post("/test-keys")
async def drm_test_keys(req: DrmTestKeysRequest):
    if not allow_drm_key_export():
        raise HTTPException(
            status_code=403,
            detail="Izvoz DRM ključeva je onemogućen. Postavite VIDEODOWNLOAD_ALLOW_DRM_KEY_EXPORT=true za dijagnostiku.",
        )
    if not drm_manager.is_ready():
        raise HTTPException(status_code=503, detail="CDM nije spreman. Dodajte device.wvd fajl.")

    def _run():
        import requests as _requests

        hdrs = req.headers or {}
        resp = _requests.get(req.mpd_url, headers=hdrs, timeout=20)
        resp.raise_for_status()
        pssh_list = drm_manager.extract_all_pssh_from_mpd(resp.text)
        if not pssh_list:
            raise RuntimeError("Nije pronasao nijedan Widevine PSSH u MPD manifestu.")
        lic_headers = {"Content-Type": "application/octet-stream", **hdrs}
        keys = drm_manager.get_keys_multi_pssh(pssh_list, req.license_url, lic_headers, req.service)
        return {"pssh_count": len(pssh_list), "psshs": pssh_list, "keys": keys}

    loop = asyncio.get_running_loop()
    try:
        result = await asyncio.wait_for(loop.run_in_executor(None, _run), timeout=30.0)
        return {"success": True, **result}
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Timeout pri dobavljanju licence (30s).")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
