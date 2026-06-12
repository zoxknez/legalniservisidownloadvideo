"""Shared yt-dlp configuration for metadata extraction and CLI downloads."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from backend.config import CONFIG_DIR

YTDLP_CLI_NETWORK_ARGS: List[str] = [
    "--js-runtimes", "node",
    "--remote-components", "ejs:github",
    "--retries", "5",
    "--fragment-retries", "5",
    "--retry-sleep", "exp=1:4",
]


def get_ytdlp_cookies_path() -> Path:
    return CONFIG_DIR / "ytdlp_cookies.txt"


def cookies_file_configured() -> bool:
    path = get_ytdlp_cookies_path()
    return path.is_file() and path.stat().st_size > 0


def ytdlp_metadata_opts() -> Dict[str, Any]:
    """Python API options for yt_dlp.YoutubeDL (skip_download metadata)."""
    opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "js_runtimes": {"node": {}},
        "remote_components": {"ejs:github"},
        "listformats": False,
        "format": "bestvideo*+bestaudio/best",
        "age_limit": None,
        "youtube_include_dash_manifest": True,
        "youtube_include_hls_manifest": True,
    }
    if cookies_file_configured():
        opts["cookiefile"] = str(get_ytdlp_cookies_path())
    return opts
