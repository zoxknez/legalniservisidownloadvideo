import logging
from typing import Dict, Any, List
from pathlib import Path

from backend.core.services.voyo import VoyoAuth, VoyoConfig, VoyoDownloader
from backend.jobs.inprocess import build_job
from backend.config import config

logger = logging.getLogger(__name__)

_VOYO_CACHE = {}

class VoyoAdapter:
    @staticmethod
    def get_auth_status() -> Dict[str, Any]:
        """Check if Voyo has valid credentials and if login succeeds."""
        global _VOYO_CACHE
        from backend.credentials_store import get_secret

        vcfg = VoyoConfig()
        email, password, device_id = vcfg.get_credentials()

        if not email or not password:
            creds = config.get_credentials("voyo")
            email = creds.get("email", "") or email
            password = creds.get("password", "") or password
            if email and password:
                vcfg.set_credentials(email, password)

        stored_token = get_secret("voyo", "token")
        if not email and not stored_token:
            return {"authenticated": False, "email": "", "error": "No credentials stored"}
        if not email and stored_token:
            email = creds.get("email", "") if (creds := config.get_credentials("voyo")) else ""

        import time
        now = time.time()
        if (
            _VOYO_CACHE.get("email") == email
            and _VOYO_CACHE.get("authenticated") is True
            and (now - _VOYO_CACHE.get("last_check", 0)) < 600
        ):
            return {
                "authenticated": True,
                "email": email,
                "nickname": _VOYO_CACHE.get("nickname", ""),
                "subscribed": _VOYO_CACHE.get("subscribed", False),
                "profile_id": _VOYO_CACHE.get("profile_id", 0),
            }

        try:
            auth = VoyoAuth()
            if device_id:
                auth.state.device_id = device_id
                auth.session.headers["device-id"] = device_id

            auth.authenticate(email, password)
            vcfg.update_device_id(auth.state.device_id)

            status = {
                "authenticated": True,
                "email": email,
                "nickname": auth.state.nickname,
                "subscribed": auth.state.is_subscribed,
                "profile_id": auth.state.profile_id,
            }
            _VOYO_CACHE = {**status, "last_check": now, "authenticated": True}
            return status
        except Exception as e:
            _VOYO_CACHE = {"email": email, "last_check": now, "authenticated": False}
            return {"authenticated": False, "email": email, "error": str(e)}

    @staticmethod
    def login(email: str, password: str) -> Dict[str, Any]:
        """Verify login, save to both ~/.voyo/config.json and app settings."""
        try:
            vcfg = VoyoConfig()
            vcfg.set_credentials(email, password)
            
            auth = VoyoAuth()
            auth.login(email, password)
            vcfg.update_device_id(auth.state.device_id)
            
            # Sync with our app config
            config.update_credentials("voyo", {"email": email, "password": password})
            
            return {
                "success": True,
                "nickname": auth.state.nickname,
                "subscribed": auth.state.is_subscribed
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_profiles() -> List[Dict[str, Any]]:
        """Fetch profiles of authenticated Voyo user."""
        try:
            vcfg = VoyoConfig()
            email, password, device_id = vcfg.get_credentials()
            if not email:
                return []
            
            auth = VoyoAuth()
            if device_id:
                auth.state.device_id = device_id
                auth.session.headers['device-id'] = device_id
            
            auth.login(email, password)
            return auth.get_profiles()
        except Exception:
            return []

    @staticmethod
    def _make_auth() -> VoyoAuth:
        vcfg = VoyoConfig()
        email, password, device_id = vcfg.get_credentials()
        if not email:
            raise RuntimeError("No credentials configured")
        auth = VoyoAuth()
        if device_id:
            auth.state.device_id = device_id
            auth.session.headers["device-id"] = device_id
        auth.login(email, password)
        vcfg.update_device_id(auth.state.device_id)
        return auth

    @staticmethod
    def resolve_to_category(target: str) -> Dict[str, Any]:
        """Resolve a video URL/ID or category ID to a full category.

        If *target* is a video ID (no items in category response),
        fetches the video metadata, reads ``meta.voyokey`` (e.g. ``CAT_50``)
        and retries with that category ID.
        """
        import re
        auth = VoyoAdapter._make_auth()

        # Extract numeric id from URL or plain number
        m = re.search(r"[?&]id=(\d+)", target)
        if m:
            cat_id = int(m.group(1))
        elif target.isdigit():
            cat_id = int(target)
        else:
            m2 = re.search(r"_(\d+)\.html", target)
            cat_id = int(m2.group(1)) if m2 else None
            if cat_id is None:
                raise ValueError(f"Cannot parse Voyo ID from: {target}")

        try:
            category = auth.get_category(cat_id)
            if category.get("items"):
                return category
        except Exception:
            pass

        # Fallback: treat as video ID, extract voyokey -> category
        meta = auth.get_video_metadata(cat_id)
        inner = meta.get("meta", {})
        voyokey = inner.get("voyokey", "")
        m3 = re.search(r"CAT_(\d+)", voyokey)
        if not m3:
            raise ValueError(
                f"Video {cat_id} has no series link (voyokey={voyokey!r})"
            )
        real_cat_id = int(m3.group(1))
        return auth.get_category(real_cat_id)

    @staticmethod
    def get_series_info(series_id: int) -> Dict[str, Any]:
        """Fetch series catalog items (episodes) grouped by season."""
        import re
        try:
            category = VoyoAdapter.resolve_to_category(str(series_id))
            items = category.get("items", [])

            def _parse_season(season_str) -> int:
                if not season_str:
                    return 1
                m = re.search(r"(\d+)", str(season_str))
                return int(m.group(1)) if m else 1

            episodes = []
            for ep in items:
                inner = ep.get("meta", {})
                episodes.append({
                    "id": ep.get("id"),
                    "title": ep.get("title", ""),
                    "season": _parse_season(inner.get("season", "")),
                    "episode": inner.get("episode", 0),
                    "length_mins": ep.get("length", 0) // 60,
                    "drm": bool(ep.get("drmProtected")),
                    "has_subs": bool(ep.get("hasSubtitles")),
                })

            # Sort by season ASC, episode ASC
            episodes.sort(key=lambda e: (e["season"], e["episode"]))

            # Group into seasons
            seasons_map: Dict[int, list] = {}
            for ep in episodes:
                seasons_map.setdefault(ep["season"], []).append(ep)

            seasons_list = [
                {"season": sn, "episodes": eps}
                for sn, eps in sorted(seasons_map.items())
            ]

            return {
                "success": True,
                "title": category.get("title", f"Series {series_id}"),
                "description": category.get("description", ""),
                "nbSeasons": category.get("nbSeasons", len(seasons_list)),
                "seasons": seasons_list,
                "episodes": episodes,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def make_download_cmd(target: str, mode: str, episodes_range: str = "", resolution: str = "1080p") -> List[str]:
        """Queue an in-process Voyo download job."""
        import re
        target = target.strip()
        is_url = bool(re.match(r"^https?://", target, re.IGNORECASE))
        params: Dict[str, Any] = {
            "target": target,
            "resolution": resolution,
            "output_dir": config.get_output_dir(),
        }
        if mode == "series":
            params["episodes"] = episodes_range.strip()
            return build_job("voyo", "series", params)
        if is_url:
            return build_job("voyo", "url" if mode != "video" else "video", params)
        return build_job("voyo", "video", params)

    @staticmethod
    def download_video(video_id: int, output_dir: str = None, resolution: str = "1080p") -> bool:
        """Download a single Voyo video."""
        try:
            vcfg = VoyoConfig()
            email, password, device_id = vcfg.get_credentials()
            if not email:
                raise RuntimeError("No Voyo credentials configured")
            
            auth = VoyoAuth()
            if device_id:
                auth.state.device_id = device_id
                auth.session.headers['device-id'] = device_id
            auth.login(email, password)
            vcfg.update_device_id(auth.state.device_id)
            
            out_dir = output_dir or config.get_output_dir()
            downloader = VoyoDownloader(auth, out_dir, resolution)
            return downloader.download_video(video_id)
        except Exception as e:
            logging.error(f"Download failed: {e}")
            return False

    @staticmethod
    def download_series(series_id: int, episodes_range: str = "", 
                       output_dir: str = None, resolution: str = "1080p") -> tuple:
        """Download Voyo series episodes."""
        try:
            vcfg = VoyoConfig()
            email, password, device_id = vcfg.get_credentials()
            if not email:
                raise RuntimeError("No Voyo credentials configured")
            
            auth = VoyoAuth()
            if device_id:
                auth.state.device_id = device_id
                auth.session.headers['device-id'] = device_id
            auth.login(email, password)
            vcfg.update_device_id(auth.state.device_id)
            
            out_dir = output_dir or config.get_output_dir()
            downloader = VoyoDownloader(auth, out_dir, resolution)
            return downloader.download_series(series_id, episodes_range)
        except Exception as e:
            logging.error(f"Series download failed: {e}")
            return 0, 0
