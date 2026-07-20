"""Queue downloads from paired sniffer captures (manifest + license)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import config
from backend.jobs.inprocess import build_job
from backend.services.hbo_adapter import HboAdapter
from backend.services.http_client import normalize_drm_headers
from backend.services.skyshowtime_adapter import SkyShowtimeAdapter
from backend.sniffer_store import SnifferCapture, _norm_service

logger = logging.getLogger(__name__)


def _device_path() -> str:
    wvd = config.check_binaries_status().get("device_wvd", {})
    path = wvd.get("path", "")
    return path if path and Path(path).exists() else ""


def _service_default_headers(svc: str) -> Dict[str, str]:
    """Browser-like Origin/Referer defaults when sniffer missed them."""
    origins = {
        "hbomax": ("https://www.max.com", "https://www.max.com/"),
        "skyshowtime": ("https://www.skyshowtime.com", "https://www.skyshowtime.com/"),
        "hrti": ("https://hrti.hrt.hr", "https://hrti.hrt.hr/"),
        "rtsplaneta": ("https://rtsplaneta.rs", "https://rtsplaneta.rs/"),
        "eon": ("https://eon.tv", "https://eon.tv/"),
        "voyo": ("https://voyo.rs", "https://voyo.rs/"),
    }
    origin, referer = origins.get(svc, ("", ""))
    out: Dict[str, str] = {}
    if origin:
        out["Origin"] = origin
        out["Referer"] = referer
    return out


def build_sniffer_drm_headers(capture: SnifferCapture) -> Dict[str, str]:
    """Merge normalized sniffer headers with service Origin/Referer defaults."""
    svc = _norm_service(capture.service)
    headers = _service_default_headers(svc)
    headers.update(normalize_drm_headers(capture.headers or {}))
    return headers


def build_sniffer_download_cmd(
    capture: SnifferCapture,
    *,
    subs: str = "all",
    audio: str = "all",
) -> List[str]:
    svc = _norm_service(capture.service)
    manifest = capture.manifest_url.strip()
    license_url = (capture.license_url or "").strip()
    title = capture.title.strip() or f"{svc} Sniffer"
    drm_headers = build_sniffer_drm_headers(capture)

    if not manifest:
        raise ValueError("Manifest URL nije snifovan.")

    # Dedicated direct pipelines (API-native license headers / tokens).
    if svc in ("hbomax", "hbo"):
        if not license_url:
            raise ValueError("License URL nije snifovan (potreban za HBO Max).")
        return HboAdapter.make_download_direct_cmd(manifest, license_url, title, subs, audio)

    if svc == "skyshowtime":
        if not license_url:
            raise ValueError("License URL nije snifovan (potreban za SkyShowtime).")
        license_token = (
            drm_headers.get("X-License-Token")
            or (capture.headers or {}).get("X-License-Token")
            or (capture.headers or {}).get("x-license-token")
            or ""
        )
        return SkyShowtimeAdapter.make_download_direct_cmd(
            manifest,
            license_url,
            title,
            license_token=license_token,
        )

    # Service-aware generic MPD+license path (not always labeled as "eon").
    # Uses EONDownloader as shared DASH/CENC engine but tags source_service for
    # license cert cache, logging, and default headers.
    return build_job(
        "sniffer",
        "direct",
        {
            "source_service": svc,
            "manifest_url": manifest,
            "license_url": license_url,
            "title": title,
            "drm_headers": drm_headers,
            "output_dir": config.get_output_dir(),
            "device_path": _device_path(),
        },
    )


def capture_display_title(capture: SnifferCapture) -> str:
    svc = _norm_service(capture.service).upper()
    title = capture.title.strip()
    if title:
        return f"{svc}: {title}"
    base = capture.manifest_url.rsplit("/", 1)[-1][:48]
    return f"{svc} Sniffer: {base}"


async def queue_sniffer_download(
    queue_manager,
    capture: SnifferCapture,
    *,
    subs: str = "all",
    audio: str = "all",
) -> Dict[str, Any]:
    cmd = build_sniffer_download_cmd(capture, subs=subs, audio=audio)
    title = capture_display_title(capture)
    task_id = await queue_manager.add_download(_norm_service(capture.service), title, cmd)
    return {"success": True, "task_id": task_id, "title": title}
