import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional, Any, List
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
from backend.services.smart_parser import SmartParser

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

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing background daemons...")
    asyncio.create_task(queue_manager.scheduler_daemon_loop())

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

def get_system_metrics():
    import psutil
    import shutil
    try:
        # Disk Space
        output_dir = config.get_output_dir()
        total_b, used_b, free_b = shutil.disk_usage(output_dir)
        disk_pct = round((used_b / total_b) * 100, 1) if total_b > 0 else 0
        
        # CPU
        cpu_pct = psutil.cpu_percent(interval=None)
        
        # RAM
        virtual_mem = psutil.virtual_memory()
        ram_total = virtual_mem.total
        ram_used = virtual_mem.used
        ram_free = virtual_mem.available
        ram_pct = virtual_mem.percent
        
        return {
            "disk": {
                "total": total_b,
                "used": used_b,
                "free": free_b,
                "percent": disk_pct
            },
            "cpu": {
                "percent": cpu_pct
            },
            "ram": {
                "total": ram_total,
                "used": ram_used,
                "free": ram_free,
                "percent": ram_pct
            }
        }
    except Exception as e:
        logger.error(f"Error fetching system metrics: {e}")
        return None

@app.get("/api/status")
async def get_system_status():
    """Returns credential status for all downloaders and paths status for tools (parallel with timeouts)."""
    binaries = config.check_binaries_status()

    # Run all service auth checks in parallel using executor to not block the event loop
    loop = asyncio.get_running_loop()
    voyo_task   = loop.run_in_executor(None, VoyoAdapter.get_auth_status)
    hrti_task   = loop.run_in_executor(None, HrtiAdapter.get_auth_status)
    eon_task    = loop.run_in_executor(None, EonAdapter.get_auth_status)
    rts_task    = loop.run_in_executor(None, RtsAdapter.get_auth_status)
    hbomax_task = loop.run_in_executor(None, HboAdapter.get_auth_status)

    async def safe_check(task, name):
        try:
            res = await asyncio.wait_for(task, timeout=7.0)
            if isinstance(res, Exception):
                return {"authenticated": False, "error": str(res)}
            return res
        except asyncio.TimeoutError:
            logger.warning(f"Timeout checking status for service: {name}")
            return {"authenticated": False, "error": "Servis trenutno ne odgovara (timeout)"}
        except Exception as e:
            return {"authenticated": False, "error": str(e)}

    voyo, hrti, eon, rts, hbomax = await asyncio.gather(
        safe_check(voyo_task, "Voyo"),
        safe_check(hrti_task, "HRTi"),
        safe_check(eon_task, "EON"),
        safe_check(rts_task, "RTS Planeta"),
        safe_check(hbomax_task, "HBO Max")
    )

    metrics = get_system_metrics()

    return {
        "binaries": binaries,
        "output_dir": config.get_output_dir(),
        "services": {
            "voyo":       voyo,
            "hrti":       hrti,
            "eon":        eon,
            "rtsplaneta": rts,
            "hbomax":     hbomax
        },
        "system_metrics": metrics
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

class SnifferPayload(BaseModel):
    service: str
    type: str  # 'manifest' or 'license'
    url: str
    headers: Dict[str, str] = None
    title: str = ""

@app.post("/api/sniffer/detect")
async def sniffer_detect(data: SnifferPayload):
    """Receive browser-sniffed resources and broadcast to React clients."""
    await queue_manager.broadcast_sniffer(
        service=data.service,
        sniffer_type=data.type,
        url=data.url,
        headers=data.headers,
        title=data.title
    )
    return {"success": True}

class ScheduledRecordingRequest(BaseModel):
    channel_name: str
    title: str
    start_time: str
    duration: int

@app.post("/api/scheduler/schedule")
async def schedule_recording(req: ScheduledRecordingRequest):
    """Schedule a new IPTV recording."""
    task_id = await queue_manager.add_scheduled_recording(
        channel_name=req.channel_name,
        title=req.title,
        start_time=req.start_time,
        duration=req.duration
    )
    return {"success": True, "task_id": task_id}

@app.get("/api/scheduler/list")
def list_scheduled():
    """List all scheduled IPTV recordings."""
    return queue_manager.list_scheduled_recordings()

class CancelScheduledRequest(BaseModel):
    id: str

@app.post("/api/scheduler/cancel")
async def cancel_scheduled(req: CancelScheduledRequest):
    """Cancel a pending scheduled recording."""
    await queue_manager.cancel_scheduled_recording(req.id)
    return {"success": True}



# ── Smart Detection & Session Sync Routes ──────────────────────────────────────

@app.get("/api/smart-detect")
async def smart_detect(url: str):
    """Detect streaming service and extract metadata from URL (async, non-blocking)."""
    loop = asyncio.get_running_loop()
    res = await asyncio.wait_for(
        loop.run_in_executor(None, SmartParser.get_metadata, url),
        timeout=60.0
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

class SessionImportRequest(BaseModel):
    service: str
    session_data: str

@app.post("/api/config/import-session")
def import_session(req: SessionImportRequest):
    """Import active browser session / token to bypass CAPTCHAs."""
    service = req.service.strip().lower()
    data = req.session_data.strip()

    if not data:
        raise HTTPException(status_code=400, detail="Podaci o sesiji ne smeju biti prazni.")

    try:
        if service == "voyo":
            from backend.core.services.voyo.auth import VoyoConfig
            vcfg = VoyoConfig()
            token = data
            if data.startswith("{"):
                try:
                    js = json.loads(data)
                    token = js.get("token") or js.get("secure_streaming_token") or data
                except:
                    pass
            vcfg._cfg["token"] = token
            vcfg.save()
            
            # Sync in-memory cache
            from backend.services.voyo_adapter import _VOYO_CACHE
            import time
            _VOYO_CACHE["token"] = token
            _VOYO_CACHE["last_check"] = time.time()
            return {"success": True, "message": "Voyo token uspešno uvezen!"}

        elif service == "hrti":
            cfg_path = Path.home() / ".hrti" / "config.json"
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            token = data
            if data.startswith("{"):
                try:
                    js = json.loads(data)
                    token = js.get("token") or js.get("secure_streaming_token") or data
                except:
                    pass
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump({"token": token}, f, indent=2)
            return {"success": True, "message": "HRTi token uspešno uvezen!"}

        elif service == "rtsplaneta" or service == "rts":
            from backend.core.services.rtsplaneta.rtsplaneta_auth import RTSPlanetaConfig
            rcfg = RTSPlanetaConfig()
            token = data
            if data.startswith("{"):
                try:
                    js = json.loads(data)
                    token = js.get("token") or js.get("secure_streaming_token") or data
                except:
                    pass
            rcfg.config["token"] = token
            rcfg.config["secure_streaming_token"] = token
            rcfg.save()
            return {"success": True, "message": "RTS Planeta token uspešno uvezen!"}

        elif service == "hbomax":
            token_path = Path.home() / ".hbomax" / "token.json"
            token_path.parent.mkdir(parents=True, exist_ok=True)
            if data.startswith("{"):
                try:
                    js = json.loads(data)
                    if "access_token" not in js and "token" in js:
                        js["access_token"] = js["token"]
                    if "access_token" in js and isinstance(js["access_token"], str):
                        js["access_token"] = js["access_token"].replace("Bearer ", "").strip()
                    with open(token_path, "w", encoding="utf-8") as f:
                        json.dump(js, f, indent=2)
                except:
                    clean_data = data.replace("Bearer ", "").strip()
                    with open(token_path, "w", encoding="utf-8") as f:
                        json.dump({"access_token": clean_data}, f, indent=2)
            else:
                clean_data = data.replace("Bearer ", "").strip()
                with open(token_path, "w", encoding="utf-8") as f:
                    json.dump({"access_token": clean_data}, f, indent=2)
            config.update_credentials("hbomax", {"token": data})
            return {"success": True, "message": "HBO Max token uspešno uvezen!"}

        else:
            raise HTTPException(status_code=400, detail=f"Uvoz sesije nije podržan za servis: {service}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Greška tokom uvoza sesije: {e}")

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

class YtdlpDownloadRequest(BaseModel):
    url: str
    resolution: str = "1080p"
    subs: str = ""
    audio_only: bool = False
    use_aria2: bool = False

@app.post("/api/ytdlp/download")
async def ytdlp_download(req: YtdlpDownloadRequest):
    import os
    from urllib.parse import urlparse
    
    url = req.url.strip()
    output_dir = config.get_output_dir()
    
    cmd = [
        "python", "-m", "yt_dlp",
        url,
        "--no-playlist"
    ]
    
    if req.audio_only:
        output_tmpl = os.path.join(output_dir, "%(title)s.mp3")
        cmd.extend([
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", output_tmpl
        ])
    else:
        output_tmpl = os.path.join(output_dir, "%(title)s.%(ext)s")
        # Parse resolution — handles plain "1080p", descriptive "2160p (4K)", "best", etc.
        import re as _re
        _res_match = _re.search(r"(\d+)p", req.resolution)
        if _res_match:
            res_val = _res_match.group(1)
            format_spec = (
                f"bestvideo[height<={res_val}][vcodec^=avc]+bestaudio[acodec^=mp4a]/"
                f"bestvideo[height<={res_val}]+bestaudio/"
                f"best[height<={res_val}]/best"
            )
        else:
            format_spec = "bestvideo+bestaudio/best"
        cmd.extend([
            "-f", format_spec,
            "-o", output_tmpl,
            "--merge-output-format", "mp4"
        ])
        
    if req.subs:
        cmd.extend([
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs", req.subs,
            "--embed-subs"
        ])
        
    if req.use_aria2:
        aria2_status = config.check_binaries_status().get("aria2c", {})
        if aria2_status.get("found"):
            cmd.extend([
                "--external-downloader", aria2_status.get("path"),
                "--external-downloader-args", "aria2c:-j 16 -x 16 -s 16 -k 1M"
            ])
            
    domain = urlparse(url).netloc.replace("www.", "")
    title = f"Univerzalni ({domain}): {url[:40]}"
    task_id = await queue_manager.add_download("ytdlp", title, cmd)
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

class HboDirectDownloadRequest(BaseModel):
    manifest_url: str
    license_url: str
    title: str = ""
    subs: str = "sr,hr,mk,bs,sl"

@app.post("/api/hbo/download-direct")
async def hbo_download_direct(req: HboDirectDownloadRequest):
    """Bypass Mode: Download using directly pasted Manifest + License URLs."""
    cmd = HboAdapter.make_download_direct_cmd(
        req.manifest_url, req.license_url, req.title, req.subs
    )
    display_title = req.title.strip() if req.title.strip() else f"HBO Max Direct: {req.manifest_url[:40]}…"
    task_id = await queue_manager.add_download("hbomax", display_title, cmd)
    return {"success": True, "task_id": task_id}

# ── Download Queue Operations ───────────────────────────────────────────────

class CancelRequest(BaseModel):
    id: str

@app.post("/api/queue/cancel")
async def cancel_download(req: CancelRequest):
    await queue_manager.cancel_download(req.id)
    return {"success": True}

@app.post("/api/queue/retry")
async def retry_download(req: CancelRequest):
    success = await queue_manager.retry_download(req.id)
    if not success:
        raise HTTPException(status_code=400, detail="Zadatak se ne može pokrenuti ponovo.")
    return {"success": True}

@app.post("/api/queue/clear")
async def clear_completed():
    await queue_manager.clear_completed()
    return {"success": True}

# ── Zero-Friction Sniffer & Browser Auto-Sync ──────────────────────────────────

class SnifferImportRequest(BaseModel):
    service: str
    type: str  # "manifest" | "license"
    url: str
    headers: Optional[Dict[str, str]] = None
    title: Optional[str] = ""

@app.post("/api/sniffer/import")
async def sniffer_import(req: SnifferImportRequest):
    """Import a sniffed resource and broadcast it via WebSocket to the React client."""
    logger.info(f"Imported sniffed resource for {req.service}: {req.type}")
    await queue_manager.broadcast_sniffer(
        service=req.service,
        sniffer_type=req.type,
        url=req.url,
        headers=req.headers,
        title=req.title or ""
    )
    return {"success": True}

@app.post("/api/config/auto-sync-browser")
async def auto_sync_browser():
    """Trigger Chromium browser session/cookie auto-extraction and update configs."""
    try:
        from backend.services.browser_cookies import sync_all_supported_services
        sync_report = sync_all_supported_services()
        
        # Check if at least one service was successfully synced
        synced_any = any(sync_report.values())
        
        return {
            "success": True,
            "report": sync_report,
            "synced_any": synced_any,
            "message": "Sinhronizacija sesija uspešno završena!" if synced_any else "Nisu pronađene aktivne sesije u pretraživačima."
        }
    except Exception as e:
        logger.error(f"Error during browser auto-sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── Static File Serving ────────────────────────────────────────────────────────


static_dir = PROJECT_ROOT / "backend" / "static"

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
