import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.config import config, PROJECT_ROOT
from backend.queue_manager import queue_manager
from backend.services.voyo_adapter import VoyoAdapter
from backend.services.hrti_adapter import HrtiAdapter
from backend.services.eon_adapter import EonAdapter
from backend.services.rts_adapter import RtsAdapter
from backend.services.hbo_adapter import HboAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Multi-Service Video Downloader API")

# Enable CORS for development (React runs on 5173, FastAPI on 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await queue_manager.register_websocket(websocket)
    try:
        while True:
            # Keep connection alive, wait for client messages if any
            data = await websocket.receive_text()
            # We don't expect client commands over WS yet, but can handle them if needed
    except WebSocketDisconnect:
        queue_manager.unregister_websocket(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        queue_manager.unregister_websocket(websocket)

# ── General Routes ────────────────────────────────────────────────────────────

@app.get("/api/status")
def get_system_status():
    """Returns credential status for all downloaders and paths status for tools."""
    binaries = config.check_binaries_status()
    
    return {
        "binaries": binaries,
        "output_dir": config.get_output_dir(),
        "services": {
            "voyo": VoyoAdapter.get_auth_status(),
            "hrti": HrtiAdapter.get_auth_status(),
            "eon": EonAdapter.get_auth_status(),
            "rtsplaneta": RtsAdapter.get_auth_status(),
            "hbomax": HboAdapter.get_auth_status()
        }
    }

class ConfigUpdate(BaseModel):
    output_dir: str = None
    binaries: Dict[str, str] = None

@app.post("/api/config")
def update_config(data: ConfigUpdate):
    if data.output_dir:
        config.set_output_dir(data.output_dir)
    if data.binaries:
        for name, path in data.binaries.items():
            config.update_binary_path(name, path)
    return {"success": True, "output_dir": config.get_output_dir(), "binaries": config.data["binaries"]}

# ── Voyo RS Routes ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/api/voyo/login")
def voyo_login(req: LoginRequest):
    res = VoyoAdapter.login(req.email, req.password)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@app.get("/api/voyo/profiles")
def voyo_profiles():
    return VoyoAdapter.get_profiles()

@app.get("/api/voyo/series/{series_id}")
def voyo_series_info(series_id: int):
    res = VoyoAdapter.get_series_info(series_id)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("error"))
    return res

class VoyoDownloadRequest(BaseModel):
    target: str   # ID or URL
    mode: str     # video, series
    episodes: str = ""
    resolution: str = "1080p"

@app.post("/api/voyo/download")
async def voyo_download(req: VoyoDownloadRequest):
    cmd = VoyoAdapter.make_download_cmd(req.target, req.mode, req.episodes, req.resolution)
    title = f"Voyo: {req.target} ({req.mode})"
    task_id = await queue_manager.add_download("voyo", title, cmd)
    return {"success": True, "task_id": task_id}

# ── HRTi Routes ───────────────────────────────────────────────────────────────

@app.post("/api/hrti/login")
def hrti_login(req: LoginRequest):
    res = HrtiAdapter.save_credentials(req.email, req.password)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@app.get("/api/hrti/categories")
def hrti_categories():
    return HrtiAdapter.list_categories()

@app.get("/api/hrti/category-items")
def hrti_category_items(category: str, page: int = 1):
    return HrtiAdapter.get_category_items(category, page)

@app.get("/api/hrti/search")
def hrti_search(query: str):
    return HrtiAdapter.search_items(query)

@app.get("/api/hrti/series/{series_uuid}")
def hrti_series_episodes(series_uuid: str):
    return HrtiAdapter.get_series_episodes(series_uuid)

class HrtiDownloadRequest(BaseModel):
    ref_id: str
    title: str = ""
    workers: int = 16

@app.post("/api/hrti/download")
async def hrti_download(req: HrtiDownloadRequest):
    cmd = HrtiAdapter.make_download_cmd(req.ref_id, req.title, req.workers)
    title = f"HRTi: {req.title or req.ref_id}"
    task_id = await queue_manager.add_download("hrti", title, cmd)
    return {"success": True, "task_id": task_id}

# ── EON TV Routes ─────────────────────────────────────────────────────────────

class EonLoginRequest(BaseModel):
    username: str
    password: str
    serial: str
    number: str

@app.post("/api/eon/login")
def eon_login(req: EonLoginRequest):
    res = EonAdapter.save_device(req.username, req.password, req.serial, req.number)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@app.get("/api/eon/health")
def eon_health():
    return EonAdapter.get_health()

@app.get("/api/eon/api-status")
def eon_api_status():
    try:
        return EonAdapter.api_status()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@app.post("/api/eon/api-login")
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

@app.post("/api/eon/refresh-token")
def eon_refresh_token():
    try:
        return EonAdapter.refresh_api_token()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to refresh EON token")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/eon/channels")
def eon_channels():
    try:
        return EonAdapter.list_channels()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to list EON channels")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/eon/episodes/{series_id}")
def eon_episodes(series_id: str):
    try:
        return EonAdapter.list_episodes(series_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to list EON episodes")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/eon/search")
def eon_search(query: str):
    try:
        return EonAdapter.search_vod(query)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to search EON VOD")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/eon/epg")
def eon_epg(channel: str):
    try:
        return EonAdapter.get_epg(channel)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to fetch EON EPG")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/eon/vod-info")
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

@app.post("/api/eon/catalogs/init")
def eon_init_catalogs():
    try:
        return EonAdapter.ensure_catalog_templates()
    except Exception as e:
        logger.exception("Failed to initialize EON catalog templates")
        raise HTTPException(status_code=500, detail=str(e))

class EonDownloadRequest(BaseModel):
    mode: str # vod, series, live
    target: str
    duration: int = 60
    episodes: str = ""
    play: bool = False
    player_path: str = ""

@app.post("/api/eon/download")
async def eon_download(req: EonDownloadRequest):
    try:
        cmd = EonAdapter.make_download_cmd(
            req.mode, req.target, req.duration, req.episodes, req.play, req.player_path
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    title = f"EON {req.mode.upper()}: {req.target}"
    task_id = await queue_manager.add_download("eon", title, cmd)
    return {"success": True, "task_id": task_id}

# ── RTS Planeta Routes ────────────────────────────────────────────────────────

@app.post("/api/rts/login")
def rts_login(req: LoginRequest):
    res = RtsAdapter.save_credentials(req.email, req.password)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

class RtsDownloadRequest(BaseModel):
    target_url: str
    start_ep: int = None
    end_ep: int = None
    verbose: bool = False

@app.post("/api/rts/download")
async def rts_download(req: RtsDownloadRequest):
    cmd = RtsAdapter.make_download_cmd(req.target_url, req.start_ep, req.end_ep, req.verbose)
    title = f"RTS Planeta: {req.target_url.split('/')[-1]}"
    task_id = await queue_manager.add_download("rtsplaneta", title, cmd)
    return {"success": True, "task_id": task_id}

# ── HBO Max Routes ────────────────────────────────────────────────────────────

class HboLoginRequest(BaseModel):
    market: str = "emea"

@app.post("/api/hbo/login")
async def hbo_login(req: HboLoginRequest):
    script_path = PROJECT_ROOT / "hbomax_downloader.py"
    if not script_path.exists():
        config.update_credentials("hbomax", {"token": "mock_token", "market": req.market})
        return {"success": True, "mock": True}

    cmd = HboAdapter.make_login_cmd(req.market)
    title = "HBO Max Login Session"
    # Launch interactive login in queue manager so the user can see code and instructions in the logs!
    task_id = await queue_manager.add_download("hbomax", title, cmd)
    return {"success": True, "task_id": task_id}

class HboDownloadRequest(BaseModel):
    video_id: str
    subs: str = "sr,hr,mk,bs,sl"

@app.post("/api/hbo/download")
async def hbo_download(req: HboDownloadRequest):
    cmd = HboAdapter.make_download_cmd(req.video_id, req.subs)
    title = f"HBO Max: {req.video_id}"
    task_id = await queue_manager.add_download("hbomax", title, cmd)
    return {"success": True, "task_id": task_id}

# ── Download Queue Operations ───────────────────────────────────────────────

class CancelRequest(BaseModel):
    id: str

@app.post("/api/queue/cancel")
async def cancel_download(req: CancelRequest):
    await queue_manager.cancel_download(req.id)
    return {"success": True}

@app.post("/api/queue/clear")
async def clear_completed():
    await queue_manager.clear_completed()
    return {"success": True}

# ── Static File Serving ────────────────────────────────────────────────────────

static_dir = Path("d:/ProjektiApp/videodownloadservisi/backend/static")

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Fallback to index.html for UI routing
    @app.get("/{fallback_path:path}")
    def serve_frontend(fallback_path: str):
        # Allow API routes to fail naturally
        if fallback_path.startswith("api/") or fallback_path.startswith("ws"):
            raise HTTPException(status_code=404, detail="Not Found")
            
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "API is running. Frontend static build is empty."}
else:
    @app.get("/")
    def read_root():
        return {"message": "API is running. Place React build inside backend/static to serve UI."}
