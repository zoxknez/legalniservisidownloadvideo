"""In-process Voyo download jobs."""
from __future__ import annotations

import re
from typing import Any, Dict

from backend.config import config
from backend.core.services.voyo import VoyoAuth, VoyoConfig, VoyoDownloader
from backend.jobs.inprocess import LogFn, capture_job_output


def _authenticated_downloader(resolution: str) -> VoyoDownloader:
    vcfg = VoyoConfig()
    email, password, device_id = vcfg.get_credentials()
    if not email or not password:
        creds = config.get_credentials("voyo")
        email = creds.get("email", "")
        password = creds.get("password", "")
        if email and password:
            vcfg.set_credentials(email, password)
    if not email or not password:
        raise RuntimeError("Voyo credentials are not configured.")

    auth = VoyoAuth()
    if device_id:
        auth.state.device_id = device_id
        auth.session.headers["device-id"] = device_id
    auth.login(email, password)
    vcfg.update_device_id(auth.state.device_id)

    out_dir = config.get_output_dir()
    return VoyoDownloader(auth, out_dir, resolution)


def run_voyo_job(action: str, params: Dict[str, Any], log_fn: LogFn) -> bool:
    resolution = params.get("resolution") or "1080p"
    target = str(params.get("target", "")).strip()
    episodes = str(params.get("episodes") or "").strip()
    is_url = bool(re.match(r"^https?://", target, re.IGNORECASE))

    with capture_job_output(log_fn, ["VoyoDownloader", "backend.core.services.voyo", ""]):
        downloader = _authenticated_downloader(resolution)

        if action == "video":
            if is_url:
                ok = downloader.download_video_url(target)
            else:
                ok = downloader.download_video(int(target))
            if not ok:
                raise RuntimeError(f"Voyo video download failed: {target}")
            return True

        if action == "series":
            if is_url:
                ok_count, total = downloader.download_series_url(target, episodes)
            else:
                ok_count, total = downloader.download_series(int(target), episodes)
            log_fn(f"INFO Voyo serija završena: {ok_count}/{total} epizoda")
            return ok_count > 0

        if action == "url":
            ok = downloader.download_video_url(target)
            if not ok:
                raise RuntimeError(f"Voyo URL download failed: {target}")
            return True

        raise RuntimeError(f"Unknown Voyo job action: {action}")
