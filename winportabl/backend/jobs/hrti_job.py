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
    if action not in {"download", "downloads"}:
        raise RuntimeError(f"Unknown HRTi job action: {action}")

    ref_id = str(params.get("ref_id") or params.get("url") or "").strip()
    title = str(params.get("title") or "").strip()
    workers = max(1, min(int(params.get("workers") or 16), 64))
    output_dir = params.get("output_dir") or config.get_output_dir()

    if action == "download" and not ref_id:
        raise RuntimeError("HRTi ref_id or url is required.")
    if action == "downloads" and not params.get("items"):
        raise RuntimeError("HRTi items list is required.")

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

        if action == "download":
            downloader.download(ref_id, title or None)
            _check_cancelled(cancel_event)
            return True

        raw_items = params.get("items") or []
        items = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            item_ref = str(item.get("ref_id") or item.get("id") or "").strip()
            if not item_ref:
                continue
            items.append(
                {
                    "ref_id": item_ref,
                    "title": str(item.get("title") or "").strip(),
                }
            )
        if not items:
            raise RuntimeError("HRTi items list is required.")

        success = 0
        total = len(items)
        for idx, item in enumerate(items, 1):
            _check_cancelled(cancel_event)
            label = item["title"] or item["ref_id"]
            log_fn(f"INFO HRTi epizoda {idx}/{total}: {label}")
            try:
                downloader.download(item["ref_id"], item["title"] or None)
                success += 1
            except Exception as exc:
                log_fn(f"ERROR HRTi epizoda nije uspela: {label} ({exc})")

        _check_cancelled(cancel_event)
        log_fn(f"INFO HRTi batch zavrsen: {success}/{total} epizoda")
        return total > 0 and success == total
