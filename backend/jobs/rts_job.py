"""In-process RTS Planeta download jobs."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import threading

from backend.config import config
from backend.core.services.rtsplaneta.rtsplaneta_downloader import RTSPlanetaDownloader
from backend.jobs.exceptions import JobCancelled
from backend.jobs.inprocess import LogFn, capture_job_output


def _check_cancelled(cancel_event: Optional[threading.Event]) -> None:
    if cancel_event and cancel_event.is_set():
        raise JobCancelled("Download cancelled by user")


def _device_path() -> str:
    wvd = config.check_binaries_status().get("device_wvd", {})
    path = wvd.get("path", "")
    if path and Path(path).exists():
        return path
    return ""


def run_rts_job(
    action: str,
    params: Dict[str, Any],
    log_fn: LogFn,
    cancel_event: Optional[threading.Event] = None,
) -> bool:
    if action != "download":
        raise RuntimeError(f"Unknown RTS job action: {action}")

    target_url = str(params.get("target_url") or "").strip()
    if not target_url:
        raise RuntimeError("RTS target_url is required.")

    start_ep = int(params.get("start_ep") or 1)
    end_ep = params.get("end_ep")
    end_ep_val = int(end_ep) if end_ep is not None else None
    output_dir = params.get("output_dir") or config.get_output_dir()

    _check_cancelled(cancel_event)

    with capture_job_output(log_fn, ["backend.core.services.rtsplaneta", ""]):
        downloader = RTSPlanetaDownloader(
            output_dir=output_dir,
            device_path=_device_path() or None,
        )
        _check_cancelled(cancel_event)
        downloader.login()
        _check_cancelled(cancel_event)

        if downloader.is_series_url(target_url):
            downloaded = downloader.download_series(
                target_url,
                start=start_ep,
                end=end_ep_val,
            )
            log_fn(f"INFO RTS serija završena: {len(downloaded)} epizoda")
            return len(downloaded) > 0

        downloader.download(target_url)
        return True
