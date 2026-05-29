import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from backend.config import config
from backend.core.services.hrti import HRTIAuth, HRTIBrowser
from backend.core.services.runner import HRTI_DOWNLOADER, python_module_cmd

logger = logging.getLogger(__name__)


class HrtiAdapter:
    _browser: HRTIBrowser | None = None
    _cats_cached_val: List[str] | None = None
    _cats_cached_time: float = 0.0
    _items_cached_dict: Dict[tuple, tuple] = {}
    _search_cached_dict: Dict[str, tuple] = {}
    _series_cached_dict: Dict[str, tuple] = {}

    @classmethod
    def _browser_client(cls) -> HRTIBrowser:
        if cls._browser is None:
            cls._browser = HRTIBrowser()
        return cls._browser

    @staticmethod
    def get_auth_status() -> Dict[str, Any]:
        cfg_path = Path.home() / ".hrti" / "config.json"
        if cfg_path.exists():
            try:
                import json
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                h_email = data.get("email") or data.get("username", "")
                if h_email:
                    return {"authenticated": True, "email": h_email}
            except Exception:
                pass

        app_creds = config.get_credentials("hrti")
        email = app_creds.get("email", "")
        password = app_creds.get("password", "")
        if email and password:
            return {"authenticated": True, "email": email}
        return {"authenticated": False, "email": "", "error": "No credentials stored"}

    @staticmethod
    def save_credentials(email: str, password: str) -> Dict[str, Any]:
        try:
            auth = HRTIAuth()
            auth.save_credentials(email, password)
            config.update_credentials("hrti", {"email": email, "password": password})
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @classmethod
    def list_categories(cls) -> List[str]:
        now = time.time()
        if cls._cats_cached_val and (now - cls._cats_cached_time) < 1800.0:
            return cls._cats_cached_val
        try:
            categories = cls._browser_client().list_categories()
            cls._cats_cached_val = categories
            cls._cats_cached_time = now
            return categories
        except Exception as exc:
            logger.error("HRTi list_categories failed: %s", exc)
            return []

    @classmethod
    def get_category_items(cls, category: str, page: int = 1) -> Dict[str, Any]:
        now = time.time()
        cache_key = (category, page)
        if cache_key in cls._items_cached_dict:
            ts, cached = cls._items_cached_dict[cache_key]
            if (now - ts) < 1800.0:
                return cached
        try:
            result = cls._browser_client().list_category_items(category, page=page)
            cls._items_cached_dict[cache_key] = (now, result)
            return result
        except Exception as exc:
            logger.error("HRTi get_category_items failed: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "metadata": {"total_items": 0, "page": page, "total_pages": 0},
                "items": [],
            }

    @classmethod
    def search_items(cls, query: str) -> Dict[str, Any]:
        now = time.time()
        if query in cls._search_cached_dict:
            ts, cached = cls._search_cached_dict[query]
            if (now - ts) < 1800.0:
                return cached
        try:
            result = cls._browser_client().search_items(query)
            cls._search_cached_dict[query] = (now, result)
            return result
        except Exception as exc:
            logger.error("HRTi search_items failed: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "metadata": {"total_items": 0, "page": 1, "total_pages": 0},
                "items": [],
            }

    @classmethod
    def get_series_episodes(cls, series_uuid: str) -> Dict[str, Any]:
        now = time.time()
        if series_uuid in cls._series_cached_dict:
            ts, cached = cls._series_cached_dict[series_uuid]
            if (now - ts) < 3600.0:
                return cached
        try:
            result = cls._browser_client().list_series_episodes(series_uuid)
            cls._series_cached_dict[series_uuid] = (now, result)
            return result
        except Exception as exc:
            logger.error("HRTi get_series_episodes failed: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "metadata": {"total_items": 0, "page": 1, "total_pages": 0},
                "items": [],
            }

    @staticmethod
    def make_download_cmd(ref_id: str, title: str = "", workers: int = 16) -> List[str]:
        cmd = python_module_cmd(HRTI_DOWNLOADER, "--ref-id", ref_id)
        if title:
            cmd += ["--title", title]
        cmd += ["-o", config.get_output_dir()]
        wvd_path = config.check_binaries_status().get("device_wvd", {}).get("path", "")
        if wvd_path and os.path.exists(wvd_path):
            cmd += ["-d", wvd_path]
        if workers and workers != 16:
            cmd += ["-w", str(workers)]
        return cmd
