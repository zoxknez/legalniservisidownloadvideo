"""
Runtime server settings: environment variables with config.json fallback.
"""
from __future__ import annotations

import os
import secrets
from typing import List

from backend.config import config

_TRUE = frozenset({"1", "true", "yes", "on"})


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


def _env_list(name: str, default: List[str]) -> List[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return [p.strip() for p in raw.split(",") if p.strip()]


def get_api_key() -> str:
    env_key = os.environ.get("VIDEODOWNLOAD_API_KEY", "").strip()
    if env_key:
        return env_key
    server = config.data.get("server") or {}
    return (server.get("api_key") or "").strip()


def ensure_api_key() -> str:
    """Generate and persist API key on first run if none is configured."""
    existing = get_api_key()
    if existing:
        return existing
    new_key = secrets.token_urlsafe(32)
    if "server" not in config.data:
        config.data["server"] = {}
    config.data["server"]["api_key"] = new_key
    config.save()
    return new_key


def localhost_bypass_enabled() -> bool:
    return _env_bool("VIDEODOWNLOAD_LOCALHOST_BYPASS", True)


def cors_origins() -> List[str]:
    return _env_list(
        "VIDEODOWNLOAD_CORS_ORIGINS",
        [
            "http://127.0.0.1:8000",
            "http://localhost:8000",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
    )


def allow_drm_key_export() -> bool:
    return _env_bool("VIDEODOWNLOAD_ALLOW_DRM_KEY_EXPORT", False)
