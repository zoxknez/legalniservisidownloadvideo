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


def get_bridge_token() -> str:
    env_token = os.environ.get("VIDEODOWNLOAD_BRIDGE_TOKEN", "").strip()
    if env_token:
        return env_token
    server = config.data.get("server") or {}
    return (server.get("bridge_token") or "").strip()


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


def ensure_bridge_token() -> str:
    """Generate and persist the browser bridge token used by the userscript."""
    existing = get_bridge_token()
    if existing:
        return existing
    new_token = secrets.token_urlsafe(32)
    if "server" not in config.data:
        config.data["server"] = {}
    config.data["server"]["bridge_token"] = new_token
    config.save()
    return new_token


def set_api_key(value: str) -> None:
    """Persist API key in config.json (ignored when VIDEODOWNLOAD_API_KEY env is set)."""
    if "server" not in config.data:
        config.data["server"] = {}
    config.data["server"]["api_key"] = (value or "").strip()
    config.save()


def api_key_from_env() -> bool:
    return bool(os.environ.get("VIDEODOWNLOAD_API_KEY", "").strip())


def localhost_bypass_enabled() -> bool:
    return _env_bool("VIDEODOWNLOAD_LOCALHOST_BYPASS", True)


def cors_origins() -> List[str]:
    return _env_list(
        "VIDEODOWNLOAD_CORS_ORIGINS",
        [
            "http://127.0.0.1:8200",
            "http://localhost:8200",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
    )


def allow_drm_key_export() -> bool:
    return _env_bool("VIDEODOWNLOAD_ALLOW_DRM_KEY_EXPORT", False)
