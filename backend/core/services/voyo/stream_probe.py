"""Voyo stream availability — probe via videoUrlV2 (authoritative over catalog flags)."""
from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .auth import VoyoAuth

VOYO_WIDEVINE_MSG = "Widevine DRM — preuzimanje nije podržano."
VOYO_UNAVAILABLE_MSG = "Stream nije dostupan za preuzimanje."


def classify_url_info(url_info: Dict[str, Any]) -> Dict[str, Any]:
    """Classify a videoUrlV2 response."""
    license_val = url_info.get("license")
    has_license = license_val not in (None, "", "null", False)
    info_code = url_info.get("infoCode", 0)
    try:
        info_code = int(info_code)
    except (TypeError, ValueError):
        info_code = -1
    url = (url_info.get("url") or "").strip()

    if has_license:
        return {
            "streamable": False,
            "drm_blocking": True,
            "drm_type": "widevine",
            "reason": VOYO_WIDEVINE_MSG,
        }
    if info_code != 0 or not url:
        info_txt = (url_info.get("info") or "").strip()
        detail = f"infoCode={info_code}"
        if info_txt:
            detail = f"{detail}, {info_txt}"
        return {
            "streamable": False,
            "drm_blocking": True,
            "drm_type": "unavailable",
            "reason": f"{VOYO_UNAVAILABLE_MSG} ({detail})",
        }
    return {
        "streamable": True,
        "drm_blocking": False,
        "drm_type": "none",
        "reason": "",
    }


def check_streamable(auth: "VoyoAuth", video_id: int) -> Dict[str, Any]:
    """Probe whether a video can be downloaded (AES-128 HLS path)."""
    try:
        url_info = auth.get_video_url(int(video_id))
        result = classify_url_info(url_info)
        result["probe_ok"] = True
        return result
    except Exception as exc:
        return {
            "streamable": False,
            "drm_blocking": False,
            "drm_type": "unknown",
            "reason": str(exc),
            "probe_ok": False,
        }
