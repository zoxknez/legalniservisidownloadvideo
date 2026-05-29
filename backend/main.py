import os
import json
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Optional, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, Response
from pydantic import BaseModel

from backend.config import config, PROJECT_ROOT
from backend.queue_manager import queue_manager
from backend.middleware.api_key import ApiKeyMiddleware, is_authorized
from backend.server_settings import (
    ensure_api_key,
    get_api_key,
    cors_origins,
    allow_drm_key_export,
)
from backend.services.voyo_adapter import VoyoAdapter
from backend.services.hrti_adapter import HrtiAdapter
from backend.services.eon_adapter import EonAdapter
from backend.services.rts_adapter import RtsAdapter
from backend.services.hbo_adapter import HboAdapter
from backend.services.smart_parser import SmartParser
from backend.services.drm_manager import drm_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.credentials_store import migrate_plaintext_config, migrate_legacy_keyring

    api_key = ensure_api_key()
    if api_key and not os.environ.get("VIDEODOWNLOAD_API_KEY"):
        logger.info(
            "API ključ generisan i sačuvan u ~/.videodownload/config.json "
            "(server.server.api_key). Postavite ga u podešavanjima frontenda ako koristite LAN pristup."
        )
    mig = migrate_plaintext_config(config)
    legacy = migrate_legacy_keyring()
    if mig.get("migrated") or mig.get("native") or legacy:
        logger.info(
            "Lozinke/tokeni premešteni u OS keyring (uklonjeni iz plain-text configa): %s",
            {**mig, "legacy_keyring": legacy},
        )

    if not drm_manager.is_ready():
        try:
            from backend.wvd_installer import auto_install_wvd

            wvd_result = auto_install_wvd(reload_drm=True)
            if wvd_result.get("success"):
                logger.info("device.wvd auto-instaliran pri startu: %s", wvd_result.get("path"))
        except Exception as exc:
            logger.debug("WVD auto-instalacija preskočena: %s", exc)

    async def _startup_browser_sync():
        try:
            from backend.services.browser_cookies import sync_all_supported_services

            loop = asyncio.get_running_loop()
            report = await loop.run_in_executor(None, sync_all_supported_services)
            if any(report.values()):
                logger.info("Browser sesije sinhronizovane pri startu: %s", report)
        except Exception as exc:
            logger.debug("Browser sync pri startu preskočen: %s", exc)

    asyncio.create_task(_startup_browser_sync())
    logger.info("Initializing background daemons...")
    scheduler_task = asyncio.create_task(queue_manager.scheduler_daemon_loop())
    yield
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Multi-Service Video Downloader API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ApiKeyMiddleware)


BRIDGE_CORS_PATHS = ("/api/bridge/", "/api/sniffer/detect")


@app.middleware("http")
async def bridge_cors_middleware(request: Request, call_next):
    """Allow bookmarklets/Tampermonkey from streaming sites to reach localhost bridge."""
    path = request.url.path
    if not any(path.startswith(p) for p in BRIDGE_CORS_PATHS):
        return await call_next(request)

    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-API-Key, Authorization",
    }
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=cors_headers)

    response = await call_next(request)
    for key, value in cors_headers.items():
        response.headers[key] = value
    return response


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "videodownloadservisi"}

# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if not is_authorized(websocket):
        await websocket.close(code=1008, reason="Unauthorized")
        return
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

    from backend.credentials_store import all_credential_security_status

    return {
        "binaries": binaries,
        "output_dir": config.get_output_dir(),
        "transcode_mode": config.get_transcode_mode(),
        "server": {
            "api_key_configured": bool(get_api_key()),
            "localhost_bypass": os.environ.get("VIDEODOWNLOAD_LOCALHOST_BYPASS", "true").lower()
            in ("1", "true", "yes", "on"),
        },
        "credentials_security": all_credential_security_status(config),
        "sniffer": config.data.get("sniffer", {"auto_download": True}),
        "services": {
            "voyo":       voyo,
            "hrti":       hrti,
            "eon":        eon,
            "rtsplaneta": rts,
            "hbomax":     hbomax
        },
        "system_metrics": metrics
    }

class SnifferPayload(BaseModel):
    service: str
    type: str  # 'manifest' or 'license'
    url: str
    headers: Dict[str, str] = None
    title: str = ""

class ConfigUpdate(BaseModel):
    output_dir: str = None
    transcode_mode: str = None
    binaries: Dict[str, str] = None
    sniffer: Optional[Dict[str, Any]] = None

@app.post("/api/config")
def update_config(data: ConfigUpdate):
    if data.output_dir:
        config.set_output_dir(data.output_dir)
    if data.transcode_mode:
        config.set_transcode_mode(data.transcode_mode)
    if data.binaries:
        for name, path in data.binaries.items():
            config.update_binary_path(name, path)
    if data.sniffer is not None:
        config.data.setdefault("sniffer", {}).update(data.sniffer)
        config.save()
    return {
        "success": True, 
        "output_dir": config.get_output_dir(), 
        "transcode_mode": config.get_transcode_mode(),
        "binaries": config.data["binaries"],
        "sniffer": config.data.get("sniffer", {}),
    }

@app.post("/api/sniffer/detect")
async def sniffer_detect(data: SnifferPayload):
    """Receive browser-sniffed resources and broadcast to React clients."""
    from backend.sniffer_service import process_sniffer_event

    return await process_sniffer_event(
        queue_manager,
        service=data.service,
        sniffer_type=data.type,
        url=data.url,
        headers=data.headers,
        title=data.title,
    )


class BridgeSessionRequest(BaseModel):
    service: Optional[str] = None
    session_data: Optional[str] = None
    batch: Optional[Dict[str, Any]] = None
    source: str = "bridge"
    reason: Optional[str] = None


@app.post("/api/bridge/session")
async def bridge_session(req: BridgeSessionRequest):
    """Tampermonkey / bookmarklet — uvoz sesije bez copy-paste u UI."""
    from backend.bridge import import_session_payload, imported_service_names

    try:
        result = import_session_payload(
            service=req.service,
            session_data=req.session_data,
            batch=req.batch,
            source=req.source or "bridge",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    services = imported_service_names(result)
    if services:
        await queue_manager.broadcast_session_import(
            services=services,
            message=result.get("message", "Sesija uvezena"),
            source=req.source or "bridge",
        )
    return result


@app.post("/api/bridge/sniffer")
async def bridge_sniffer(data: SnifferPayload):
    """Alias for Tampermonkey sniffer relay."""
    from backend.sniffer_service import process_sniffer_event

    return await process_sniffer_event(
        queue_manager,
        service=data.service,
        sniffer_type=data.type,
        url=data.url,
        headers=data.headers,
        title=data.title,
    )


@app.get("/api/bridge/userscript.js")
def bridge_userscript():
    """Serve Tampermonkey userscript with configured backend URL."""
    from backend.bridge import load_userscript

    try:
        script = load_userscript()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return Response(content=script, media_type="text/javascript; charset=utf-8")


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
    from backend.session_import import import_session_for_service, try_import_batch

    data = req.session_data.strip()
    if not data:
        raise HTTPException(status_code=400, detail="Podaci o sesiji ne smeju biti prazni.")

    try:
        batch = try_import_batch(data)
        if batch:
            return batch

        service = req.service.strip().lower()
        result = import_session_for_service(service, data)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
    # SponsorBlock Integration - automatically remove sponsor parts
    cmd.extend([
        "--sponsorblock-remove", "all"
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
    import importlib.util
    from backend.core.services.runner import HBO_DOWNLOADER
    if importlib.util.find_spec(HBO_DOWNLOADER) is None:
        raise HTTPException(
            status_code=503,
            detail=f"HBO Max engine ({HBO_DOWNLOADER}) nije dostupan.",
        )

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
    from backend.sniffer_service import process_sniffer_event

    logger.info(f"Imported sniffed resource for {req.service}: {req.type}")
    return await process_sniffer_event(
        queue_manager,
        service=req.service,
        sniffer_type=req.type,
        url=req.url,
        headers=req.headers,
        title=req.title or "",
    )


class SnifferDownloadRequest(BaseModel):
    service: str
    subs: str = "sr,hr,mk,bs,sl"


@app.get("/api/sniffer/captures")
def sniffer_captures():
    from backend.sniffer_store import sniffer_store

    return {
        "captures": sniffer_store.list_all(),
        "auto_download": config.data.get("sniffer", {}).get("auto_download", True),
    }


@app.post("/api/sniffer/download")
async def sniffer_download(req: SnifferDownloadRequest):
    """Start download from paired manifest + license for a service."""
    from backend.sniffer_download import queue_sniffer_download
    from backend.sniffer_store import sniffer_store

    capture = sniffer_store.get(req.service)
    if not capture or not capture.is_ready():
        raise HTTPException(
            status_code=400,
            detail="Manifest i/ili license nisu spremni. Pustite video dok je Tampermonkey aktivan.",
        )
    try:
        result = await queue_sniffer_download(queue_manager, capture, subs=req.subs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    sniffer_store.mark_queued(capture.service, result["task_id"])
    await queue_manager.broadcast_sniffer_download_queued(
        service=capture.service,
        task_id=result["task_id"],
        title=result["title"],
        auto=False,
    )
    return result

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

# ── DRM / Widevine API ───────────────────────────────────────────────────────

@app.get("/api/drm/health")
async def drm_health():
    """
    Full DRM/Widevine health report:
    CDM status, WVD metadata (security level L1/L3), key cache stats,
    provider certs, pywidevine version, recommendations.
    """
    loop = asyncio.get_running_loop()
    report = await loop.run_in_executor(None, drm_manager.get_health_report)
    return report

@app.post("/api/drm/reload")
async def drm_reload():
    """Force reload the CDM (useful after placing a new device.wvd file)."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, drm_manager.reload)
    report = await loop.run_in_executor(None, drm_manager.get_health_report)
    return {"success": True, "health": report}


class WvdBase64InstallRequest(BaseModel):
    base64: str


@app.get("/api/drm/wvd/discover")
async def wvd_discover():
    """List valid .wvd files found on disk."""
    from backend.wvd_installer import discover_wvd_files

    loop = asyncio.get_running_loop()
    files = await loop.run_in_executor(None, discover_wvd_files)
    return {"files": files, "canonical": str(Path.home() / ".videodownload" / "device.wvd")}


@app.post("/api/drm/wvd/auto-install")
async def wvd_auto_install():
    """Copy newest discovered device.wvd to ~/.videodownload/ and reload CDM."""
    from backend.wvd_installer import auto_install_wvd

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, auto_install_wvd)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Auto-instalacija nije uspela."))
    health = await loop.run_in_executor(None, drm_manager.get_health_report)
    return {**result, "health": health}


@app.post("/api/drm/wvd/install-base64")
async def wvd_install_base64(req: WvdBase64InstallRequest):
    """Install device.wvd from base64 (npr. nakon exporta iz alata)."""
    from backend.wvd_installer import install_wvd_from_base64

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: install_wvd_from_base64(req.base64))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Instalacija nije uspela."))
    health = await loop.run_in_executor(None, drm_manager.get_health_report)
    return {**result, "health": health}


@app.post("/api/drm/wvd/upload")
async def wvd_upload(file: UploadFile = File(...)):
    """Upload device.wvd file — validates, installs to canonical path, reloads CDM."""
    from backend.wvd_installer import install_wvd_bytes

    data = await file.read()
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: install_wvd_bytes(data))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Upload nije uspeo."))
    health = await loop.run_in_executor(None, drm_manager.get_health_report)
    return {**result, "health": health}

@app.post("/api/drm/cache/clear")
def drm_cache_clear():
    """Invalidate all cached Widevine content keys."""
    drm_manager.key_cache.invalidate_all()
    return {"success": True, "message": "Key cache ociscen."}

@app.get("/api/drm/cache/stats")
def drm_cache_stats():
    """Return key cache statistics."""
    return drm_manager.key_cache.stats()

class DrmPrefetchCertRequest(BaseModel):
    service: str
    license_url: str
    headers: Optional[Dict[str, str]] = None

@app.post("/api/drm/prefetch-cert")
async def drm_prefetch_cert(req: DrmPrefetchCertRequest):
    """
    Pre-fetch Widevine provider service certificate for a specific service.
    Improves license request performance and privacy (encrypts client ID).
    """
    loop = asyncio.get_running_loop()
    ok = await loop.run_in_executor(
        None,
        lambda: drm_manager.prefetch_provider_cert(
            req.service, req.license_url, req.headers
        )
    )
    if ok:
        return {"success": True, "message": f"Provider sertifikat preuzet za '{req.service}'."}
    return {"success": False, "message": "Prefetch nije uspio (server mozda ne podrzava service cert)."}

class DrmTestKeysRequest(BaseModel):
    mpd_url: str
    license_url: str
    headers: Optional[Dict[str, str]] = None
    service: str = "manual"

@app.post("/api/drm/test-keys")
async def drm_test_keys(req: DrmTestKeysRequest):
    """
    Test Widevine key exchange: fetch MPD, extract all PSSHs, get content keys.
    Returns the decryption keys (kid:key pairs) for diagnostics.
    """
    if not allow_drm_key_export():
        raise HTTPException(
            status_code=403,
            detail="Izvoz DRM ključeva je onemogućen. Postavite VIDEODOWNLOAD_ALLOW_DRM_KEY_EXPORT=true za dijagnostiku.",
        )
    if not drm_manager.is_ready():
        raise HTTPException(status_code=503, detail="CDM nije spreman. Dodajte device.wvd fajl.")

    def _run():
        import requests as _requests
        # 1. Fetch MPD
        hdrs = req.headers or {}
        resp = _requests.get(req.mpd_url, headers=hdrs, timeout=20)
        resp.raise_for_status()
        mpd_text = resp.text

        # 2. Extract all PSSHs
        pssh_list = drm_manager.extract_all_pssh_from_mpd(mpd_text)
        if not pssh_list:
            raise RuntimeError("Nije pronasao nijedan Widevine PSSH u MPD manifestu.")

        # 3. Get keys (with multi-PSSH fallback)
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


@app.get("/api/transcoder/diagnose")
def transcoder_diagnose():
    """
    Query system GPU and available hardware-accelerated video encoders.
    """
    from backend.services.transcoder import get_transcode_diagnostics
    return get_transcode_diagnostics()


# ── IPTV Server Proxy ─────────────────────────────────────────────────────────


@app.get("/api/iptv/playlist.m3u")
def get_iptv_playlist(request: Request):
    """Generates extended M3U8 local IPTV playlist with standard EPG and logos."""
    channels = []
    
    # 1. Load EON channels from local catalog
    try:
        channels_file = PROJECT_ROOT / "eon_channels.json"
        if channels_file.exists():
            with open(channels_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "channels" in data:
                    channels = data["channels"]
    except Exception as e:
        logger.error(f"Error loading IPTV channels: {e}")

    # Fallback/dynamic channels list if catalog is empty
    if not channels:
        channels = [
            {"name": "RTS 1", "url": ""},
            {"name": "RTS 2", "url": ""},
            {"name": "HRT 1", "url": ""},
            {"name": "HRT 2", "url": ""},
            {"name": "Nova S", "url": ""},
            {"name": "N1 HD", "url": ""}
        ]

    base_url = str(request.base_url).rstrip("/")
    m3u_lines = ["#EXTM3U"]
    
    for ch in channels:
        name = ch.get("name", "Unknown Channel")
        logo = ""
        # Harmonic/Harmonious logo metadata
        if "rts" in name.lower():
            logo = "https://rts.rs/images/logo.png"
        elif "voyo" in name.lower():
            logo = "https://voyo.rs/assets/images/voyo-logo.png"
        elif "hrt" in name.lower():
            logo = "https://hrt.hr/images/logo.png"
        elif "n1" in name.lower():
            logo = "https://rs.n1info.com/wp-content/themes/n1-custom/assets/images/n1-logo.svg"
            
        logo_attr = f' tvg-logo="{logo}"' if logo else ""
        group = "EON TV" if "eon" in name.lower() or "rts" in name.lower() or "n1" in name.lower() else "Local IPTV"
        
        m3u_lines.append(f'#EXTINF:-1 tvg-id="{name.lower().replace(" ", "-")}"{logo_attr} group-title="{group}",{name}')
        m3u_lines.append(f"{base_url}/api/iptv/stream/eon/{name}")
        
    return Response(content="\n".join(m3u_lines), media_type="application/x-mpegurl")


@app.get("/api/iptv/stream/{service}/{channel_id}")
def stream_iptv_channel(service: str, channel_id: str):
    """Proxies the live stream HLS chunks dynamically using FFmpeg to support any player."""
    import subprocess
    import shutil
    
    service = service.strip().lower()
    channel_id = channel_id.strip()
    
    if service != "eon":
        raise HTTPException(status_code=400, detail="Service not supported yet.")
        
    try:
        # Resolve live stream details
        stream_info = EonAdapter.resolve_stream(channel_id, "live")
        mpd_url = stream_info.get("mpd_url")
        if not mpd_url:
            raise HTTPException(status_code=404, detail="Live stream could not be resolved.")
    except Exception as e:
        logger.error(f"Error resolving EON stream for {channel_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    ffmpeg_bin = config.get_binary_path("ffmpeg") or "ffmpeg"
    
    # Configure precise sync and reconnection flags for robust chunk streaming
    cmd = [
        ffmpeg_bin, "-hide_banner", "-loglevel", "warning", "-y",
        "-reconnect", "1", "-reconnect_streamed", "1",
        "-i", mpd_url,
        "-c", "copy",
        "-async", "1", "-vsync", "-1", "-fflags", "+genpts+igndts",
        "-f", "mpegts",
        "pipe:1"
    ]
    
    logger.info(f"Starting live stream proxy via FFmpeg for: {channel_id}")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    
    def segment_generator():
        try:
            while True:
                chunk = process.stdout.read(40960) # 40KB blocks
                if not chunk:
                    break
                yield chunk
        except Exception as exc:
            logger.warning(f"IPTV client disconnected from stream {channel_id}: {exc}")
        finally:
            process.kill()
            process.wait()
            logger.info(f"Released FFmpeg proxy resources for: {channel_id}")
            
    return StreamingResponse(segment_generator(), media_type="video/mp2t")

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
