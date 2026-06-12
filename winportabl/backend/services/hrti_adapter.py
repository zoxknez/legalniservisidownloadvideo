import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from backend.config import config
from backend.core.services.hrti import HRTIAuth, HRTIBrowser
from backend.jobs.inprocess import build_job

logger = logging.getLogger(__name__)


class HrtiAdapter:
    _browser: HRTIBrowser | None = None
    _cats_cached_val: List[Dict[str, str]] | None = None
    _cats_cached_time: float = 0.0
    _items_cached_dict: Dict[tuple, tuple] = {}
    _search_cached_dict: Dict[str, tuple] = {}
    _series_cached_dict: Dict[str, tuple] = {}
    _MAX_CACHE_ENTRIES = 256

    @classmethod
    def _browser_client(cls) -> HRTIBrowser:
        if cls._browser is None:
            cls._browser = HRTIBrowser()
        return cls._browser

    @classmethod
    def _remember(cls, cache: Dict[Any, tuple], key: Any, value: Any, timestamp: float) -> None:
        cache[key] = (timestamp, value)
        if len(cache) <= cls._MAX_CACHE_ENTRIES:
            return
        oldest = min(cache, key=lambda k: cache[k][0])
        cache.pop(oldest, None)

    @staticmethod
    def get_auth_status() -> Dict[str, Any]:
        from backend.credentials_store import get_secret
        from backend.core.services.hrti.hrti_auth import extract_customer_id_from_payload
        import json

        email = ""
        customer_id = ""
        cfg_path = Path.home() / ".hrti" / "config.json"
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                email = data.get("email") or data.get("username", "")
                customer_id = str(data.get("customer_id") or data.get("CustomerId") or "").strip()
            except Exception:
                pass

        app_creds = config.get_credentials("hrti")
        if not email:
            email = app_creds.get("email") or app_creds.get("username", "")

        password = get_secret("hrti", "password") or app_creds.get("password", "")
        token = get_secret("hrti", "token") or app_creds.get("token", "")
        if token and not customer_id:
            customer_id = extract_customer_id_from_payload(token)

        if email and password:
            return {"authenticated": True, "email": email, "auth_method": "credentials"}
        if token and customer_id:
            return {"authenticated": True, "email": email, "auth_method": "session"}
        if token:
            return {
                "authenticated": False,
                "email": email,
                "error": (
                    "HRTi token je sačuvan, ali nedostaje CustomerId. "
                    "Uvezite JSON sa token/customer_id ili se prijavite ponovo."
                ),
            }
        if email:
            return {
                "authenticated": False,
                "email": email,
                "error": "Lozinka nije sačuvana. Unesite kredencijale ponovo.",
            }
        return {"authenticated": False, "email": "", "error": "Kredencijali nisu sačuvani."}

    @staticmethod
    def save_credentials(email: str, password: str) -> Dict[str, Any]:
        try:
            auth = HRTIAuth()
            auth.login(email, password)
            auth.save_credentials(email, password)
            config.update_credentials("hrti", {"email": email, "password": password})
            return {"success": True, "email": email}
        except Exception as exc:
            logger.error("HRTi save_credentials failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @classmethod
    def list_categories(cls) -> List[Dict[str, str]]:
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
            raise

    @classmethod
    def preview_ref(cls, ref_id: str) -> Dict[str, Any]:
        now = time.time()
        cache_key = f"preview:{ref_id}"
        if cache_key in cls._series_cached_dict:
            ts, cached = cls._series_cached_dict[cache_key]
            if (now - ts) < 600.0:
                return cached
        try:
            result = cls._browser_client().preview_ref(ref_id.strip())
            cls._remember(cls._series_cached_dict, cache_key, result, now)
            return result
        except Exception as exc:
            logger.error("HRTi preview_ref failed: %s", exc)
            return {"success": False, "error": str(exc), "mode": "video", "ref_id": ref_id}

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
            cls._remember(cls._items_cached_dict, cache_key, result, now)
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
            cls._remember(cls._search_cached_dict, query, result, now)
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
            cls._remember(cls._series_cached_dict, series_uuid, result, now)
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
        ref_id = ref_id.strip()
        if not ref_id:
            raise ValueError("HRTi ref_id je obavezan.")
        return build_job(
            "hrti",
            "download",
            {
                "ref_id": ref_id,
                "title": title.strip(),
                "workers": max(1, min(workers, 64)),
                "output_dir": config.get_output_dir(),
            },
        )

    @staticmethod
    def make_download_batch_cmd(items: List[Dict[str, Any]], workers: int = 16) -> List[str]:
        if len(items) > 500:
            raise ValueError("Maksimalno 500 HRTi epizoda po batch poslu.")
        clean_items = []
        for item in items:
            ref_id = str(item.get("ref_id") or item.get("id") or "").strip()
            if not ref_id:
                continue
            clean_items.append(
                {
                    "ref_id": ref_id,
                    "title": str(item.get("title") or "").strip(),
                }
            )
        if not clean_items:
            raise ValueError("Lista HRTi epizoda je prazna.")
        return build_job(
            "hrti",
            "downloads",
            {
                "items": clean_items,
                "workers": max(1, min(workers, 64)),
                "output_dir": config.get_output_dir(),
            },
        )
