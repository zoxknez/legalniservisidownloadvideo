import os
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import config, PROJECT_ROOT
from backend.queue_manager import queue_manager
from backend.middleware.api_key import ApiKeyMiddleware
from backend.server_settings import ensure_api_key, cors_origins
from backend.services.drm_manager import drm_manager
from backend.routes import register_routes

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

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
            if isinstance(report, dict) and report.get("services"):
                if any(report["services"].values()):
                    logger.info("Browser sesije sinhronizovane pri startu: %s", report["services"])
            elif isinstance(report, dict) and any(report.values()):
                logger.info("Browser sesije sinhronizovane pri startu: %s", report)
        except Exception as exc:
            logger.debug("Browser sync pri startu preskočen: %s", exc)

    asyncio.create_task(_startup_browser_sync())
    logger.info("Initializing background daemons...")
    scheduler_task = asyncio.create_task(queue_manager.scheduler_daemon_loop())
    await queue_manager.resume_pending_downloads()
    yield
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass


# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(title="Multi-Service Video Downloader API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ApiKeyMiddleware)


# ── Bridge CORS middleware ────────────────────────────────────────────────────

BRIDGE_CORS_PATHS = ("/api/bridge/", "/api/sniffer/detect")


@app.middleware("http")
async def bridge_cors_middleware(request: Request, call_next):
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


# ── Register all route modules ────────────────────────────────────────────────

register_routes(app)


# ── Static file serving ──────────────────────────────────────────────────────

static_dir = PROJECT_ROOT / "backend" / "static"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/{fallback_path:path}")
    def serve_frontend(fallback_path: str):
        if fallback_path.startswith("api/") or fallback_path.startswith("ws"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "API is running. Frontend static build is empty."}
else:
    @app.get("/")
    def read_root():
        return {"message": "API is running. Place React build inside backend/static to serve UI."}
