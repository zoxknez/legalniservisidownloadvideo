import logging
import re
import time
from pathlib import Path
from typing import Dict, Any, List

from backend.core.services.voyo import VoyoAuth, VoyoConfig, VoyoDownloader, check_streamable
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
        variant = vcfg.get_variant()
        app_creds = config.get_credentials("voyo")
        if app_creds.get("email") or app_creds.get("token"):
            variant = app_creds.get("variant", "") or variant

        if not email or not password:
            email = app_creds.get("email", "") or email
            password = app_creds.get("password", "") or password
            if email and password:
                vcfg.set_credentials(email, password, variant=variant)

        stored_token = get_secret("voyo", "token")
        if not email and not stored_token:
            return {"authenticated": False, "email": "", "error": "No credentials stored", "variant": variant}
        if not email and stored_token:
            email = creds.get("email", "") if (creds := config.get_credentials("voyo")) else ""

        now = time.time()
        if (
            _VOYO_CACHE.get("email") == email
            and _VOYO_CACHE.get("variant") == variant
            and _VOYO_CACHE.get("authenticated") is True
            and (now - _VOYO_CACHE.get("last_check", 0)) < 600
        ):
            return {
                "authenticated": True,
                "email": email,
                "nickname": _VOYO_CACHE.get("nickname", ""),
                "subscribed": _VOYO_CACHE.get("subscribed", False),
                "profile_id": _VOYO_CACHE.get("profile_id", 0),
                "variant": variant,
            }

        try:
            auth = VoyoAuth()
            auth.set_variant(variant)
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
                "variant": variant,
            }
            _VOYO_CACHE = {**status, "last_check": now, "authenticated": True}
            return status
        except Exception as e:
            _VOYO_CACHE = {"email": email, "variant": variant, "last_check": now, "authenticated": False}
            return {"authenticated": False, "email": email, "error": str(e), "variant": variant}

    @staticmethod
    def login(email: str, password: str, variant: str = "rs") -> Dict[str, Any]:
        """Verify login, save to both ~/.voyo/config.json and app settings."""
        global _VOYO_CACHE
        variant = (variant or "rs").lower()
        try:
            vcfg = VoyoConfig()
            vcfg.set_credentials(email, password, variant=variant)
            
            auth = VoyoAuth()
            auth.set_variant(variant)
            auth.login(email, password)
            vcfg.update_device_id(auth.state.device_id)
            
            config.update_credentials("voyo", {"email": email, "password": password, "variant": variant})

            _VOYO_CACHE = {
                "email": email,
                "variant": variant,
                "authenticated": True,
                "nickname": auth.state.nickname,
                "subscribed": auth.state.is_subscribed,
                "profile_id": auth.state.profile_id,
                "last_check": time.time(),
            }
            
            return {
                "success": True,
                "nickname": auth.state.nickname,
                "subscribed": auth.state.is_subscribed
            }
        except Exception as e:
            _VOYO_CACHE = {}
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_profiles() -> Dict[str, Any]:
        """Fetch profiles of authenticated Voyo user."""
        try:
            auth = VoyoAdapter._make_auth()
            profiles = auth.get_profiles()
            return {
                "success": True,
                "profiles": profiles,
                "active_profile_id": auth.state.profile_id,
            }
        except Exception as e:
            return {"success": False, "profiles": [], "active_profile_id": 0, "error": str(e)}

    @staticmethod
    def set_active_profile(profile_id: int) -> Dict[str, Any]:
        """Switch Voyo profile and persist selection."""
        global _VOYO_CACHE
        profile_id = int(profile_id)
        try:
            auth = VoyoAdapter._make_auth()
            auth.select_profile(profile_id)
            vcfg = VoyoConfig()
            vcfg.set_profile_id(profile_id)
            creds = config.get_credentials("voyo")
            config.update_credentials(
                "voyo",
                {**creds, "profile_id": profile_id},
            )
            _VOYO_CACHE = {
                **_VOYO_CACHE,
                "profile_id": auth.state.profile_id,
                "last_check": time.time(),
                "authenticated": True,
            }
            return {"success": True, "profile_id": auth.state.profile_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def assert_video_streamable(video_id: int) -> None:
        auth = VoyoAdapter._make_auth()
        probe = check_streamable(auth, int(video_id))
        if probe.get("drm_blocking"):
            raise ValueError(probe.get("reason") or "Stream nije dostupan za preuzimanje.")

    @staticmethod
    def assert_videos_streamable(video_ids: List[int]) -> None:
        auth = VoyoAdapter._make_auth()
        blocked: List[int] = []
        reasons: Dict[int, str] = {}
        for raw_id in video_ids:
            vid = int(raw_id)
            probe = check_streamable(auth, vid)
            if probe.get("drm_blocking"):
                blocked.append(vid)
                reasons[vid] = probe.get("reason") or ""
        if blocked:
            ids = ", ".join(str(i) for i in blocked)
            sample_reason = reasons.get(blocked[0], "")
            raise ValueError(f"Stream nije dostupan za preuzimanje (ID: {ids}). {sample_reason}".strip())

    @staticmethod
    def _make_auth() -> VoyoAuth:
        from backend.credentials_store import get_secret

        vcfg = VoyoConfig()
        email, password, device_id = vcfg.get_credentials()
        variant = vcfg.get_variant()
        app_creds = config.get_credentials("voyo")
        if app_creds.get("email") or app_creds.get("token"):
            variant = app_creds.get("variant", "") or variant
        if not email and not get_secret("voyo", "token"):
            email = app_creds.get("email", "") or email
            password = app_creds.get("password", "") or password
        if not email and not get_secret("voyo", "token"):
            raise RuntimeError("Voyo kredencijali nisu podešeni.")
        auth = VoyoAuth()
        auth.set_variant(variant)
        if device_id:
            auth.state.device_id = device_id
            auth.session.headers["device-id"] = device_id
        auth.authenticate(email, password)
        vcfg.update_device_id(auth.state.device_id)
        profile_id = vcfg.get_profile_id()
        if profile_id and profile_id != auth.state.profile_id:
            auth.select_profile(profile_id)
        return auth

    @staticmethod
    def parse_target_id(target: str) -> int | None:
        from backend.core.services.voyo.downloader import _parse_id

        return _parse_id(target)

    @staticmethod
    def create_downloader(resolution: str = "1080p") -> VoyoDownloader:
        auth = VoyoAdapter._make_auth()
        return VoyoDownloader(auth, config.get_output_dir(), resolution)

    @staticmethod
    def get_video_info(video_id: int, *, probe: bool = True) -> Dict[str, Any]:
        """Fetch metadata and optionally probe stream availability for a Voyo video."""
        try:
            auth = VoyoAdapter._make_auth()
            meta = auth.get_video_metadata(video_id)
            inner = meta.get("meta", {}) or {}
            length_sec = meta.get("length") or inner.get("length") or 0
            mins = int(length_sec) // 60 if length_sec else 0
            duration_str = f"{mins} min" if mins else None
            thumb = meta.get("image") or meta.get("thumbnail") or inner.get("image")
            drm_hint = bool(meta.get("drmProtected"))
            payload: Dict[str, Any] = {
                "success": True,
                "id": video_id,
                "title": meta.get("title", f"Video {video_id}"),
                "description": meta.get("description", ""),
                "duration_str": duration_str,
                "thumbnail": thumb,
                "drm_hint": drm_hint,
                "drm": drm_hint,
                "has_subs": bool(meta.get("hasSubtitles")),
            }
            if probe:
                stream = check_streamable(auth, video_id)
                payload.update({
                    "streamable": stream.get("streamable"),
                    "drm_blocking": stream.get("drm_blocking"),
                    "probe_ok": stream.get("probe_ok"),
                    "drm_type": stream.get("drm_type"),
                    "stream_reason": stream.get("reason"),
                })
            return payload
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def resolve_to_category(target: str) -> Dict[str, Any]:
        """Resolve a video URL/ID or category ID to a full category.

        If *target* is a video ID (no items in category response),
        fetches the video metadata, reads ``meta.voyokey`` (e.g. ``CAT_50``)
        and retries with that category ID.
        """
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
                    "drm_hint": bool(ep.get("drmProtected")),
                    "drm": bool(ep.get("drmProtected")),
                    "drm_blocking": False,
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
    def make_download_batch_cmd(
        video_ids: List[int],
        resolution: str = "1080p",
        series_title: str = "",
    ) -> List[str]:
        ids = [int(video_id) for video_id in video_ids if str(video_id).strip()]
        if not ids:
            raise ValueError("Lista Voyo epizoda je prazna.")
        params: Dict[str, Any] = {
            "video_ids": ids,
            "resolution": resolution,
            "output_dir": config.get_output_dir(),
        }
        if series_title:
            params["series_title"] = series_title
        return build_job("voyo", "videos", params)

    @staticmethod
    def download_video(video_id: int, output_dir: str = None, resolution: str = "1080p") -> bool:
        """Download a single Voyo video."""
        try:
            downloader = VoyoAdapter.create_downloader(resolution)
            if output_dir:
                downloader.output_dir = Path(output_dir)
            return downloader.download_video(video_id)
        except Exception as e:
            logger.error("Voyo download failed: %s", e)
            return False

    @staticmethod
    def download_series(
        series_id: int,
        episodes_range: str = "",
        output_dir: str = None,
        resolution: str = "1080p",
    ) -> tuple:
        """Download Voyo series episodes."""
        try:
            downloader = VoyoAdapter.create_downloader(resolution)
            if output_dir:
                downloader.output_dir = Path(output_dir)
            return downloader.download_series(series_id, episodes_range)
        except Exception as e:
            logger.error("Voyo series download failed: %s", e)
            return 0, 0
