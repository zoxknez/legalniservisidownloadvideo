"""In-process HRTi download jobs."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import threading

from backend.config import config
from backend.core.services.hrti.hrti_downloader import HRTIDownloader
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


def run_hrti_job(
    action: str,
    params: Dict[str, Any],
    log_fn: LogFn,
    cancel_event: Optional[threading.Event] = None,
) -> bool:
    if action != "download":
        raise RuntimeError(f"Unknown HRTi job action: {action}")

    ref_id = str(params.get("ref_id") or params.get("url") or "").strip()
    title = str(params.get("title") or "").strip()
    workers = max(1, min(int(params.get("workers") or 16), 64))
    output_dir = params.get("output_dir") or config.get_output_dir()

    if not ref_id:
        raise RuntimeError("HRTi ref_id or url is required.")

    _check_cancelled(cancel_event)

    with capture_job_output(log_fn, ["backend.core.services.hrti", ""]):
        downloader = HRTIDownloader(
            output_dir=output_dir,
            device_path=_device_path() or None,
            workers=workers,
        )
        _check_cancelled(cancel_event)
        downloader.login()
        _check_cancelled(cancel_event)
        downloader.download(ref_id, title or None)
        _check_cancelled(cancel_event)
        return True
