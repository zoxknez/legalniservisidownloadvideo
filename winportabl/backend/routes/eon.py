import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.queue_manager import queue_manager
from backend.services.eon_adapter import EonAdapter

router = APIRouter()
logger = logging.getLogger(__name__)


class EonLoginRequest(BaseModel):
    username: str
    password: str
    serial: str
    number: str


@router.post("/login")
def eon_login(req: EonLoginRequest):
    res = EonAdapter.save_device(req.username, req.password, req.serial, req.number)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/health")
def eon_health():
    return EonAdapter.get_health()


@router.get("/api-status")
def eon_api_status():
    try:
        return EonAdapter.api_status()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/api-login")
def eon_api_login(req: EonLoginRequest):
    try:
        return EonAdapter.api_login(req.username, req.password, req.serial, req.number)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to run EON API login")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-token")
def eon_refresh_token():
    try:
        return EonAdapter.refresh_api_token()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to refresh EON token")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channels")
def eon_channels():
    try:
        return EonAdapter.list_channels()
    except (FileNotFoundError, RuntimeError) as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to list EON channels")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/episodes/{series_id}")
def eon_episodes(series_id: str):
    try:
        return EonAdapter.list_episodes(series_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (FileNotFoundError, RuntimeError) as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to list EON episodes")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
def eon_search(query: str):
    try:
        return EonAdapter.search_vod(query)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to search EON VOD")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/epg")
def eon_epg(channel: str):
    try:
        return EonAdapter.get_epg(channel)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to fetch EON EPG")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vod-info")
def eon_vod_info(target: str):
    try:
        return EonAdapter.get_vod_info(target)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to fetch EON VOD info")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/catalogs/init")
def eon_init_catalogs():
    try:
        return EonAdapter.ensure_catalog_templates()
    except Exception as e:
        logger.exception("Failed to initialize EON catalog templates")
        raise HTTPException(status_code=500, detail=str(e))


class EonDownloadRequest(BaseModel):
    mode: Literal["vod", "series", "live"] = "vod"
    target: str = Field(min_length=1)
    duration: int = Field(default=60, ge=0)
    episodes: str = ""
    play: bool = False
    player_path: str = ""


@router.post("/download")
async def eon_download(req: EonDownloadRequest):
    health = EonAdapter.get_health()
    if not health.get("ready"):
        raise HTTPException(
            status_code=503,
            detail=health.get("error") or "EON nije spreman. Proverite konfiguraciju i dependencies.",
        )
    try:
        cmd = EonAdapter.make_download_cmd(
            req.mode, req.target.strip(), req.duration, req.episodes.strip(), req.play, req.player_path.strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (FileNotFoundError, RuntimeError) as e:
        raise HTTPException(status_code=503, detail=str(e))
    title = f"EON {req.mode.upper()}: {req.target.strip()}"
    task_id = await queue_manager.add_download("eon", title, cmd)
    return {"success": True, "task_id": task_id}
