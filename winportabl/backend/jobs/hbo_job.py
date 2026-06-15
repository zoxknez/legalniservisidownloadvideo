"""In-process HBO Max download/login jobs."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import threading

from backend.config import config
from backend.core.services.hbomax.hbomax_auth import HBOMaxAuth
from backend.core.services.hbomax.hbomax_downloader import HBOMaxDownloader
from backend.jobs.exceptions import JobCancelled
from backend.jobs.inprocess import LogFn, capture_job_output


def _check_cancelled(cancel_event: Optional[threading.Event]) -> None:
    if cancel_event and cancel_event.is_set():
        raise JobCancelled("Download cancelled by user")


def _parse_subs(raw: str) -> List[str]:
    subs_raw = (raw or "").strip().lower()
    if subs_raw in ("none", "no", ""):
        return ["none"]
    if subs_raw == "all":
        return ["all"]
    return [s.strip() for s in subs_raw.split(",") if s.strip()]


def _parse_audio_mode(raw: str) -> str:
    mode = (raw or "all").strip().lower()
    return "first" if mode in ("first", "single", "one") else "all"


def _device_path() -> str:
    wvd = config.check_binaries_status().get("device_wvd", {})
    path = wvd.get("path", "")
    if path and Path(path).exists():
        return path
    return ""


def _build_downloader(
    market: str,
    workers: int = 16,
    output_dir: Optional[str] = None,
) -> HBOMaxDownloader:
    bins = config.check_binaries_status()
    dl = HBOMaxDownloader(
        market=market,
        output_dir=output_dir or config.get_output_dir(),
        device_path=_device_path(),
        workers=workers,
    )
    mp4 = bins.get("mp4decrypt", {}).get("path")
    mkv = bins.get("mkvmerge", {}).get("path")
    if mp4:
        dl.mp4decrypt_path = mp4
    if mkv:
        dl.mkvmerge_path = mkv
    return dl


def run_hbo_job(
    action: str,
    params: Dict[str, Any],
    log_fn: LogFn,
    cancel_event: Optional[threading.Event] = None,
) -> bool:
    market = (params.get("market") or config.get_credentials("hbomax").get("market") or "emea").strip()
    workers = int(params.get("workers") or 16)
    output_dir = params.get("output_dir")

    _check_cancelled(cancel_event)

    with capture_job_output(log_fn, ["HBOMaxDownloader", "backend.core.services.hbomax", ""]):
        if action == "login":
            config.update_credentials("hbomax", {"market": market})
            auth = HBOMaxAuth(market=market)
            auth.login()
            log_fn("INFO HBO Max login završen — token sačuvan.")
            return True

        if action == "direct":
            dl = _build_downloader(market, workers, output_dir)
            wanted_subs = _parse_subs(params.get("subs", "all"))
            audio_mode = _parse_audio_mode(params.get("audio", "all"))
            manifest = str(params.get("manifest_url", "")).strip()
            license_url = str(params.get("license_url", "")).strip()
            title = str(params.get("title") or "").strip()
            if not manifest or not license_url:
                raise RuntimeError("manifest_url i license_url su obavezni.")
            dl.download_direct(manifest, license_url, title, wanted_subs, audio_mode)
            return True

        auth = HBOMaxAuth(market=market)
        if not auth.is_authenticated():
            raise RuntimeError(
                "Niste prijavljeni na HBO Max. Pokrenite login iz UI-a prije preuzimanja."
            )

        dl = _build_downloader(market, workers, output_dir)
        wanted_subs = _parse_subs(params.get("subs", "all"))
        audio_mode = _parse_audio_mode(params.get("audio", "all"))

        if action == "video":
            video_id = str(params.get("video_id", "")).strip()
            if not video_id:
                raise RuntimeError("video_id je obavezan.")
            dl.download(video_id, wanted_subs, audio_mode)
            return True

        raise RuntimeError(f"Unknown HBO job action: {action}")
