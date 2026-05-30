import os
import asyncio
import logging
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

    voyo, hrti, eon, rts, hbomax = await asyncio.gather(
        safe_check(voyo_task, "Voyo"),
        safe_check(hrti_task, "HRTi"),
        safe_check(eon_task, "EON"),
        safe_check(rts_task, "RTS Planeta"),
        safe_check(hbo_task, "HBO Max"),
    )

    from backend.credentials_store import all_credential_security_status

    metrics = await loop.run_in_executor(None, _get_system_metrics)

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
            "voyo": voyo,
            "hrti": hrti,
            "eon": eon,
            "rtsplaneta": rts,
            "hbomax": hbomax,
        },
        "system_metrics": metrics,
    }


class ConfigUpdate(BaseModel):
    output_dir: str = None
    transcode_mode: str = None
    binaries: Dict[str, str] = None
    sniffer: Optional[Dict[str, Any]] = None


@router.post("/api/config")
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


@router.get("/api/smart-detect")
async def smart_detect(url: str):
    loop = asyncio.get_running_loop()
    res = await asyncio.wait_for(
        loop.run_in_executor(None, SmartParser.get_metadata, url),
        timeout=60.0,
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


class SessionImportRequest(BaseModel):
    service: str
    session_data: str


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
        from backend.services.browser_cookies import sync_all_supported_services

        sync_report = sync_all_supported_services()
        services = sync_report.get("services", sync_report)
        browser_locked = bool(sync_report.get("browser_locked"))
        synced_any = any(services.values()) if isinstance(services, dict) else False

        if browser_locked and not synced_any:
            message = (
                "Chrome/Edge/Brave baza kolačića je zaključana. "
                "Zatvorite pretraživač potpuno pa pokušajte ponovo."
            )
        elif synced_any:
            message = "Sinhronizacija sesija uspešno završena!"
        else:
            message = "Nisu pronađene aktivne sesije u pretraživačima."

        return {
            "success": True,
            "report": services,
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
