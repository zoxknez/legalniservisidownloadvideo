"""In-process EON TV download jobs."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional
import threading

from backend.config import config
from backend.core.services.eon.eon_downloader import (
    handle_live_download,
    handle_series,
    handle_vod_download,
)
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


def _base_args(params: Dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        output=params.get("output_dir") or config.get_output_dir(),
        device_wvd=_device_path() or None,
        workers=int(params.get("workers") or 16),
        verbose=True,
        quality=params.get("quality") or "best",
        subs=params.get("subs") or False,
        license_url=params.get("license_url") or "",
        title=params.get("title") or "",
        player=params.get("player_path") or "",
        play=bool(params.get("play")),
        json=False,
        list_episodes=False,
    )


def run_eon_job(
    action: str,
    params: Dict[str, Any],
    log_fn: LogFn,
    cancel_event: Optional[threading.Event] = None,
) -> bool:
    _check_cancelled(cancel_event)

    with capture_job_output(log_fn, ["backend.core.services.eon", ""]):
        args = _base_args(params)
        args.cancel_event = cancel_event

        if action == "vod":
            args.vod = str(params.get("target") or "").strip()
            if not args.vod:
                raise RuntimeError("EON VOD target is required.")
            _check_cancelled(cancel_event)
            code = handle_vod_download(args)
        elif action == "series":
            args.series = str(params.get("target") or "").strip()
            args.episodes = str(params.get("episodes") or "").strip()
            if not args.series:
                raise RuntimeError("EON series target is required.")
            _check_cancelled(cancel_event)
            code = handle_series(args)
        elif action == "live":
            args.channel = str(params.get("target") or "").strip()
            args.duration = int(params.get("duration") or 60)
            if not args.channel:
                raise RuntimeError("EON live channel is required.")
            _check_cancelled(cancel_event)
            code = handle_live_download(args)
        else:
            raise RuntimeError(f"Unknown EON job action: {action}")

        _check_cancelled(cancel_event)
        if code != 0:
            raise RuntimeError(f"EON download failed with exit code {code}")
        return True
