"""In-process sniffer direct download (MPD + license from browser bridge)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from backend.config import config
from backend.jobs.inprocess import LogFn, capture_job_output


def run_sniffer_job(action: str, params: Dict[str, Any], log_fn: LogFn) -> bool:
    if action != "direct":
        log_fn(f"ERROR Nepoznata sniffer akcija: {action}")
        return False

    manifest = str(params.get("manifest_url", "")).strip()
    license_url = str(params.get("license_url", "")).strip()
    title = str(params.get("title") or "Sniffer.Download").strip()
    drm_headers = dict(params.get("drm_headers") or {})
    device_path = str(params.get("device_path") or "").strip()
    output_dir = str(params.get("output_dir") or config.get_output_dir())
    source = str(params.get("source_service") or "sniffer")

    if not manifest:
        raise RuntimeError("manifest_url je obavezan.")

    with capture_job_output(log_fn, ["EONDownloader", "backend.core.services.eon", ""]):
        from backend.core.services.eon.eon_downloader import EONDownloader

        if not device_path:
            wvd = config.check_binaries_status().get("device_wvd", {})
            device_path = wvd.get("path", "") if wvd.get("found") else ""

        dl = EONDownloader(
            output_dir=output_dir,
            device_path=device_path or None,
            workers=int(params.get("workers") or 16),
        )
        log_fn(f"INFO Sniffer direct download ({source}): {title}")
        dl.download(
            mpd_url=manifest,
            license_url=license_url,
            drm_headers=drm_headers,
            title=title,
        )
        return True
