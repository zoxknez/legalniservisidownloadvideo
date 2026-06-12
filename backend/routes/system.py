import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import config
from backend.queue_manager import queue_manager
from backend.server_settings import get_api_key
from backend.services.voyo_adapter import VoyoAdapter
from backend.services.hrti_adapter import HrtiAdapter
from backend.services.eon_adapter import EonAdapter
from backend.services.rts_adapter import RtsAdapter
from backend.services.hbo_adapter import HboAdapter
from backend.services.skyshowtime_adapter import SkyShowtimeAdapter
from backend.services.ytdlp_adapter import YtdlpAdapter
from backend.services.smart_parser import SmartParser

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_system_metrics():
    import psutil
    import shutil
    try:
        output_dir = config.get_output_dir()
        total_b, used_b, free_b = shutil.disk_usage(output_dir)
        disk_pct = round((used_b / total_b) * 100, 1) if total_b > 0 else 0
        cpu_pct = psutil.cpu_percent(interval=None)
        virtual_mem = psutil.virtual_memory()
        return {
            "disk": {"total": total_b, "used": used_b, "free": free_b, "percent": disk_pct},
            "cpu": {"percent": cpu_pct},
            "ram": {
                "total": virtual_mem.total,
                "used": virtual_mem.used,
                "free": virtual_mem.available,
                "percent": virtual_mem.percent,
            },
        }
    except Exception as e:
        logger.error("Error fetching system metrics: %s", e)
        return None


@router.get("/api/health")
async def health_check():
    return {"success": True, "status": "ok", "service": "videodownloadservisi"}


@router.get("/api/status")
async def get_system_status():
    loop = asyncio.get_running_loop()
    binaries = await loop.run_in_executor(None, config.check_binaries_status)

    voyo_task = loop.run_in_executor(None, VoyoAdapter.get_auth_status)
    hrti_task = loop.run_in_executor(None, HrtiAdapter.get_auth_status)
    eon_task = loop.run_in_executor(None, EonAdapter.get_auth_status)
    rts_task = loop.run_in_executor(None, RtsAdapter.get_auth_status)
    hbo_task = loop.run_in_executor(None, HboAdapter.get_auth_status)
    sky_task = loop.run_in_executor(None, SkyShowtimeAdapter.get_auth_status)
    ytdlp_task = loop.run_in_executor(None, YtdlpAdapter.get_health_status)

    async def safe_check(task, name):
        try:
            res = await asyncio.wait_for(task, timeout=7.0)
            if isinstance(res, Exception):
                return {"authenticated": False, "error": str(res)}
            return res
        except asyncio.TimeoutError:
            logger.warning("Timeout checking status for service: %s", name)
            return {"authenticated": False, "error": "Servis trenutno ne odgovara (timeout)"}
        except Exception as e:
            return {"authenticated": False, "error": str(e)}

    voyo, hrti, eon, rts, hbomax, skyshowtime, ytdlp = await asyncio.gather(
        safe_check(voyo_task, "Voyo"),
        safe_check(hrti_task, "HRTi"),
        safe_check(eon_task, "EON"),
        safe_check(rts_task, "RTS Planeta"),
        safe_check(hbo_task, "HBO Max"),
        safe_check(sky_task, "SkyShowtime"),
        safe_check(ytdlp_task, "Univerzalno"),
    )

    from backend.credentials_store import all_credential_security_status

    metrics = await loop.run_in_executor(None, _get_system_metrics)

    from backend.services.drm_manager import drm_manager

    drm_report = await loop.run_in_executor(None, drm_manager.get_health_report)
    wvd_meta = drm_report.get("wvd_metadata") or {}
    drm_status = {
        "cdm_ready": drm_report.get("cdm_ready", False),
        "legacy_mode": drm_report.get("legacy_mode", False),
        "wvd_file": drm_report.get("wvd_file"),
        "security_level_name": wvd_meta.get("security_level_name"),
        "key_cache_alive": (drm_report.get("key_cache") or {}).get("alive_entries", 0),
    }

    from backend.services.browser_cookies import browser_sync_supported

    return {
        "binaries": binaries,
        "output_dir": config.get_output_dir(),
        "transcode_mode": config.get_transcode_mode(),
        "ytdlp_name_template": config.get_ytdlp_name_template(),
        "max_concurrent_downloads": config.get_max_concurrent_downloads(),
        "output_format": config.get_output_format(),
        "browser_sync_supported": browser_sync_supported(),
        "server": {
            "api_key_configured": bool(get_api_key()),
            "localhost_bypass": os.environ.get("VIDEODOWNLOAD_LOCALHOST_BYPASS", "true").lower()
            in ("1", "true", "yes", "on"),
        },
        "credentials_security": all_credential_security_status(config),
        "sniffer": config.data.get("sniffer", {"auto_download": True}),
        "voyo_ignore_catalog_drm_hint": config.get_voyo_ignore_catalog_drm_hint(),
        "services": {
            "voyo": voyo,
            "hrti": hrti,
            "eon": eon,
            "rtsplaneta": rts,
            "hbomax": hbomax,
            "skyshowtime": skyshowtime,
            "ytdlp": ytdlp,
        },
        "system_metrics": metrics,
        "drm": drm_status,
    }


class ConfigUpdate(BaseModel):
    output_dir: str = None
    transcode_mode: str = None
    binaries: Dict[str, str] = None
    sniffer: Optional[Dict[str, Any]] = None
    ytdlp_name_template: Optional[str] = None
    max_concurrent_downloads: Optional[int] = None
    voyo_ignore_catalog_drm_hint: Optional[bool] = None
    output_format: Optional[str] = None


_VALID_TRANSCODE = frozenset({"off", "hevc", "av1"})


@router.post("/api/config")
def update_config(data: ConfigUpdate):
    if data.output_dir is not None:
        out = (data.output_dir or "").strip()
        if not out:
            raise HTTPException(status_code=400, detail="Izlazni folder ne sme biti prazan.")
        try:
            Path(out).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise HTTPException(status_code=400, detail=f"Ne mogu kreirati output folder: {exc}") from exc
        config.set_output_dir(out)
    if data.transcode_mode is not None:
        mode = (data.transcode_mode or "off").strip().lower()
        if mode not in _VALID_TRANSCODE:
            raise HTTPException(
                status_code=400,
                detail=f"Nepoznat transcode_mode '{mode}'. Dozvoljeno: off, hevc, av1.",
            )
        config.set_transcode_mode(mode)
    if data.ytdlp_name_template is not None:
        config.set_ytdlp_name_template(data.ytdlp_name_template)
    if data.max_concurrent_downloads is not None:
        config.set_max_concurrent_downloads(data.max_concurrent_downloads)
    wvd_updated = False
    if data.binaries:
        for name, path in data.binaries.items():
            config.update_binary_path(name, path)
            if name == "device_wvd":
                wvd_updated = True
        if wvd_updated:
            try:
                from backend.services.drm_manager import drm_manager

                drm_manager.reload()
            except Exception as exc:
                logger.warning("CDM reload after device_wvd update failed: %s", exc)
    if data.sniffer is not None:
        config.data.setdefault("sniffer", {}).update(data.sniffer)
        config.save()
    if data.voyo_ignore_catalog_drm_hint is not None:
        config.set_voyo_ignore_catalog_drm_hint(data.voyo_ignore_catalog_drm_hint)
    if data.output_format is not None:
        config.set_output_format(data.output_format)
    return {
        "success": True,
        "output_dir": config.get_output_dir(),
        "transcode_mode": config.get_transcode_mode(),
        "ytdlp_name_template": config.get_ytdlp_name_template(),
        "max_concurrent_downloads": config.get_max_concurrent_downloads(),
        "output_format": config.get_output_format(),
        "binaries": config.data["binaries"],
        "sniffer": config.data.get("sniffer", {}),
        "voyo_ignore_catalog_drm_hint": config.get_voyo_ignore_catalog_drm_hint(),
    }


@router.get("/api/smart-detect")
async def smart_detect(url: str, force: Optional[str] = None):
    url = url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL parametar je obavezan.")
    if force and force not in ("ytdlp",):
        raise HTTPException(status_code=400, detail=f"Nepoznat force parametar: {force}")
    loop = asyncio.get_running_loop()
    try:
        res = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: SmartParser.get_metadata(url, force_service=force)),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Analiza URL-a je istekla (timeout 60s).")
    except Exception as exc:
        logger.exception("smart-detect error for %s", url)
        raise HTTPException(status_code=503, detail=f"Greška pri analizi: {exc}")
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


class SessionImportRequest(BaseModel):
    service: str
    session_data: str


class CredentialsClearRequest(BaseModel):
    service: str


class ApiKeyUpdate(BaseModel):
    api_key: str


@router.post("/api/credentials/migrate")
def migrate_credentials():
    """Move plaintext secrets from config.json / native files into OS keyring."""
    from backend.credentials_store import migrate_legacy_keyring, migrate_plaintext_config

    try:
        report = migrate_plaintext_config(config)
        legacy = migrate_legacy_keyring()
        return {"success": True, "report": report, "legacy_moved": legacy}
    except Exception as e:
        logger.exception("credential migrate failed")
        raise HTTPException(status_code=500, detail=f"Greška pri migraciji: {e}") from e


@router.post("/api/credentials/clear")
def clear_credentials(req: CredentialsClearRequest):
    from backend.credentials_store import clear_service_credentials

    try:
        result = clear_service_credentials(req.service, config)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("clear credentials failed for %s", req.service)
        raise HTTPException(status_code=500, detail=f"Greška pri brisanju kredencijala: {e}") from e


@router.post("/api/config/api-key")
def update_api_key(body: ApiKeyUpdate):
    from backend.server_settings import api_key_from_env, set_api_key

    if api_key_from_env():
        raise HTTPException(
            status_code=409,
            detail="API ključ je podešen preko VIDEODOWNLOAD_API_KEY — promenite ga u okruženju servera.",
        )
    key = (body.api_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="API ključ ne sme biti prazan.")
    set_api_key(key)
    return {"success": True, "api_key_configured": True}


@router.post("/api/config/import-session")
def import_session(req: SessionImportRequest):
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


@router.post("/api/config/auto-sync-browser")
async def auto_sync_browser():
    try:
        from backend.services.browser_cookies import browser_sync_supported, sync_all_supported_services

        if not browser_sync_supported():
            return {
                "success": False,
                "unsupported_platform": True,
                "synced_any": False,
                "browser_locked": False,
                "services": {s: False for s in ("voyo", "hrti", "rtsplaneta", "eon", "skyshowtime")},
                "message": (
                    "Automatska sinhronizacija iz pretraživača je dostupna samo na Windows-u "
                    "(Chrome/Edge/Brave + DPAPI)."
                ),
            }

        sync_report = sync_all_supported_services()
        services = sync_report.get("services", {})
        browser_locked = bool(sync_report.get("browser_locked"))
        synced_any = any(services.values()) if isinstance(services, dict) else False

        if browser_locked and not synced_any:
            message = (
                "Chrome/Edge/Brave baza kolačića je zaključana. "
                "Zatvorite pretraživač potpuno pa pokušajte ponovo."
            )
        elif synced_any:
            synced_names = [k.upper() for k, v in services.items() if v]
            message = f"Sinhronizacija uspešna za: {', '.join(synced_names)}."
            if services.get("eon"):
                message += (
                    " EON: sačuvani su browser kolačići — serial i broj uređaja i dalje "
                    "podešavate ručno ispod."
                )
        else:
            message = "Nisu pronađene aktivne sesije u pretraživačima."

        return {
            "success": synced_any or not browser_locked,
            "report": services,
            "services": services,
            "synced_any": synced_any,
            "browser_locked": browser_locked,
            "message": message,
        }
    except Exception as e:
        logger.error("Error during browser auto-sync: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/open-output-folder")
def open_output_folder():
    import subprocess
    import sys
    from pathlib import Path

    path = Path(config.get_output_dir())
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise HTTPException(status_code=400, detail=f"Output folder cannot be created: {exc}") from exc

    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Cannot open folder: {exc}") from exc

    return {"success": True, "path": str(path)}


@router.post("/api/system/update-ytdlp")
async def update_ytdlp():
    import sys
    import subprocess

    logger.info("Starting yt-dlp update process...")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "install", "-U", "yt-dlp",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="ignore")
        success = (proc.returncode == 0)

        if success:
            logger.info("yt-dlp updated successfully.")
            message = "yt-dlp je uspešno ažuriran na najnoviju verziju."
        else:
            logger.error(f"yt-dlp update failed: {output}")
            message = "Ažuriranje yt-dlp-a nije uspelo."

        return {
            "success": success,
            "message": message,
            "output": output
        }
    except Exception as e:
        logger.error(f"Error during yt-dlp update: {e}")
        raise HTTPException(status_code=500, detail=f"Greška tokom ažuriranja: {str(e)}")
