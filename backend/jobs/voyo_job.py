"""In-process Voyo download jobs."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional
import threading

from backend.services.voyo_adapter import VoyoAdapter
from backend.jobs.exceptions import JobCancelled
from backend.jobs.inprocess import LogFn, capture_job_output


def _check_cancelled(cancel_event: Optional[threading.Event]) -> None:
    if cancel_event and cancel_event.is_set():
        raise JobCancelled("Download cancelled by user")


def run_voyo_job(
    action: str,
    params: Dict[str, Any],
    log_fn: LogFn,
    cancel_event: Optional[threading.Event] = None,
) -> bool:
    resolution = params.get("resolution") or "1080p"
    target = str(params.get("target", "")).strip()
    episodes = str(params.get("episodes") or "").strip()
    series_title = str(params.get("series_title") or "").strip()
    is_url = bool(re.match(r"^https?://", target, re.IGNORECASE))

    _check_cancelled(cancel_event)

    with capture_job_output(log_fn, ["VoyoDownloader", "backend.core.services.voyo", ""]):
        downloader = VoyoAdapter.create_downloader(resolution)
        _check_cancelled(cancel_event)

        if action == "video":
            _check_cancelled(cancel_event)
            if is_url:
                ok = downloader.download_video_url(target)
            else:
                ok = downloader.download_video(int(target))
            _check_cancelled(cancel_event)
            if not ok:
                raise RuntimeError(f"Voyo video download failed: {target}")
            return True

        if action == "series":
            _check_cancelled(cancel_event)
            if is_url:
                ok_count, total = downloader.download_series_url(target, episodes)
            else:
                ok_count, total = downloader.download_series(int(target), episodes)
            _check_cancelled(cancel_event)
            log_fn(f"INFO Voyo serija završena: {ok_count}/{total} epizoda")
            return total > 0 and ok_count == total

        if action == "videos":
            raw_ids = params.get("video_ids") or []
            video_ids = [int(video_id) for video_id in raw_ids if str(video_id).strip()]
            if not video_ids:
                raise RuntimeError("Voyo video_ids list is required.")
            success = 0
            total = len(video_ids)
            for idx, video_id in enumerate(video_ids, 1):
                _check_cancelled(cancel_event)
                log_fn(f"INFO Voyo epizoda {idx}/{total}: video {video_id}")
                if downloader.download_video(
                    video_id,
                    series_title=series_title,
                ):
                    success += 1
                else:
                    log_fn(f"ERROR Voyo epizoda nije uspela: video {video_id}")
            _check_cancelled(cancel_event)
            log_fn(f"INFO Voyo batch zavrsen: {success}/{total} epizoda")
            return total > 0 and success == total

        if action == "url":
            _check_cancelled(cancel_event)
            ok = downloader.download_video_url(target)
            _check_cancelled(cancel_event)
            if not ok:
                raise RuntimeError(f"Voyo URL download failed: {target}")
            return True

        raise RuntimeError(f"Unknown Voyo job action: {action}")
