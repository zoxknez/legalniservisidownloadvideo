"""Adapter for universal yt-dlp downloads (Pametno preuzimanje)."""
from __future__ import annotations

import logging
import shutil
from typing import Any, Dict, List, Tuple

from backend.config import config
from backend.services.ytdlp_command_builder import (
    build_queue_metadata,
    build_queue_title,
    build_ytdlp_cmd,
)

logger = logging.getLogger(__name__)


class YtdlpAdapter:
    @staticmethod
    def get_health_status() -> Dict[str, Any]:
        node_path = shutil.which("node")
        ytdlp_version = None
        error = ""
        try:
            import yt_dlp

            ytdlp_version = yt_dlp.version.__version__
        except Exception as exc:
            error = str(exc)

        ready = bool(ytdlp_version) and bool(node_path)
        result: Dict[str, Any] = {
            "ready": ready,
            "authenticated": ready,
            "ytdlp_version": ytdlp_version,
            "node_available": bool(node_path),
            "node_path": node_path or "",
        }
        if not node_path:
            result["error"] = "Node.js nije pronađen u PATH-u (potreban za YouTube i druge sajtove)."
        elif not ytdlp_version:
            result["error"] = error or "yt-dlp biblioteka nije dostupna."
        return result

    @staticmethod
    def prepare_download(params: Dict[str, Any]) -> Tuple[List[str], str, Dict[str, Any]]:
        url = (params.get("url") or "").strip()
        if not url:
            raise ValueError("URL je obavezan.")

        subs = (params.get("subs") or "").strip()
        hardsub = bool(params.get("hardsub"))
        if hardsub and not subs:
            raise ValueError("Za ugrađivanje titlova u video (hardsub) morate izabrati bar jedan jezik titlova.")

        output_dir = config.get_output_dir()
        params = {**params, "output_dir": output_dir, "name_template": config.get_ytdlp_name_template()}

        cmd = build_ytdlp_cmd(params)
        metadata = build_queue_metadata(params)
        title = build_queue_title(url, params.get("video_title"))
        return cmd, title, metadata
