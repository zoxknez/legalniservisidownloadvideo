import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.config import config
from backend.core.services.skyshowtime.skyshowtime_auth import SkyShowtimeAuth, SkyConfig
from backend.core.services.skyshowtime.skyshowtime_downloader import SkyShowtimeDownloader
from backend.jobs.inprocess import build_job

logger = logging.getLogger(__name__)

_SERIES_BASE_RE = re.compile(r"(/(?:tv|kids)/[^/]+/[^/]+)")


class SkyShowtimeAdapter:
    @staticmethod
    def _make_authenticated_downloader() -> SkyShowtimeDownloader:
        auth = SkyShowtimeAuth()
        auth.ensure_authenticated()
        dl = SkyShowtimeDownloader()
        dl.auth = auth
        return dl

    @staticmethod
    def sync_auth_to_config(auth: Optional[SkyShowtimeAuth] = None) -> None:
        auth = auth or SkyShowtimeAuth()
        from backend.credentials_store import set_secret

        if auth.state.user_token:
            set_secret("skyshowtime", "token", auth.state.user_token)
        config.update_credentials(
            "skyshowtime",
            {
                "territory": auth.territory,
                "expiry": auth.state.token_expiry or "",
            },
        )

    @staticmethod
    def get_auth_status() -> Dict[str, Any]:
        auth = SkyShowtimeAuth()
        authenticated = auth.is_authenticated()
        token_path = ""
        expiry = ""

        if SkyConfig.TOKEN_CACHE.exists():
            token_path = str(SkyConfig.TOKEN_CACHE.resolve())
            try:
                with open(SkyConfig.TOKEN_CACHE) as f:
                    data = json.load(f)
                    expiry = data.get("token_expiry", "")
            except Exception:
                pass

        cfg = config.get_credentials("skyshowtime")
        territory = auth.territory or cfg.get("territory") or SkyConfig.TERRITORY

        return {
            "authenticated": authenticated,
            "token_path": token_path,
            "token_expiry": expiry or cfg.get("expiry", ""),
            "territory": territory,
        }

    @staticmethod
    def _resolve_series_node(target: str) -> Tuple[Dict[str, Any], str]:
        dl = SkyShowtimeAdapter._make_authenticated_downloader()
        slug = SkyShowtimeDownloader._extract_slug(target)

        def _has_seasons(node: Dict[str, Any]) -> bool:
            items = node.get("relationships", {}).get("items", {}).get("data", [])
            if isinstance(items, dict):
                items = [items]
            return bool(items)

        data = dl._get_title_info(slug)
        if _has_seasons(data):
            return data, slug

        match = _SERIES_BASE_RE.match(slug)
        if match and match.group(1) != slug:
            base_slug = match.group(1)
            data = dl._get_title_info(base_slug)
            if _has_seasons(data):
                return data, base_slug

        raise ValueError("Nije serija ili nema epizoda u katalogu.")

    @staticmethod
    def _episode_entry(ep_node: Dict[str, Any]) -> Dict[str, Any]:
        attrs = ep_node.get("attributes", {})
        season = int(attrs.get("seasonNumber") or attrs.get("season") or 0)
        episode = int(attrs.get("episodeNumber") or attrs.get("episode") or 0)
        formats = attrs.get("formats", {})
        fmt = formats.get("HD") or formats.get("SD") or {}
        return {
            "id": f"{season}:{episode}",
            "title": attrs.get("title", ""),
            "season": season,
            "episode": episode,
            "length_mins": int((attrs.get("duration") or attrs.get("runtime") or 0) // 60),
            "drm": True,
            "has_subs": True,
            "content_id": fmt.get("contentId", ""),
            "variant_id": attrs.get("providerVariantId", ""),
        }

    @staticmethod
    def get_series_info(target: str) -> Dict[str, Any]:
        try:
            data, slug = SkyShowtimeAdapter._resolve_series_node(target)
            dl = SkyShowtimeAdapter._make_authenticated_downloader()
            raw_eps = dl._collect_episodes(data, season_num=None, start_ep=1, end_ep=9999)
            episodes = [SkyShowtimeAdapter._episode_entry(ep) for ep in raw_eps]

            seasons_map: Dict[int, list] = {}
            for ep in episodes:
                seasons_map.setdefault(ep["season"], []).append(ep)

            seasons_list = [
                {"season": sn, "episodes": eps}
                for sn, eps in sorted(seasons_map.items())
            ]

            attrs = data.get("attributes", {})
            return {
                "success": True,
                "title": attrs.get("title", "SkyShowtime serija"),
                "description": attrs.get("synopsis") or attrs.get("description", ""),
                "nbSeasons": len(seasons_list),
                "seasons": seasons_list,
                "episodes": episodes,
                "slug": slug,
                "series_url": f"https://www.skyshowtime.com/watch/asset{slug}",
            }
        except Exception as exc:
            logger.exception("SkyShowtime get_series_info failed")
            return {"success": False, "error": str(exc)}

    @staticmethod
    def resolve_to_series(target: str) -> Dict[str, Any]:
        info = SkyShowtimeAdapter.get_series_info(target)
        if not info.get("success"):
            raise ValueError(info.get("error") or "Nije moguće pronaći seriju.")
        return info

    @staticmethod
    def get_title_metadata(target: str) -> Dict[str, Any]:
        """Lightweight title lookup for movies or series landing pages."""
        try:
            dl = SkyShowtimeAdapter._make_authenticated_downloader()
            slug = SkyShowtimeDownloader._extract_slug(target)
            data = dl._get_title_info(slug)
            attrs = data.get("attributes", {})
            is_series = bool(data.get("relationships", {}).get("items", {}).get("data"))
            return {
                "success": True,
                "title": attrs.get("title", "SkyShowtime"),
                "description": attrs.get("synopsis") or attrs.get("description", ""),
                "is_series": is_series,
                "slug": slug,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def make_login_cmd(cookie_file: Optional[str] = None, cookies: Optional[Dict[str, str]] = None) -> List[str]:
        return build_job("skyshowtime", "login", {"cookie_file": cookie_file, "cookies": cookies})

    @staticmethod
    def make_download_cmd(
        url: str,
        season: Optional[int] = None,
        start_ep: int = 1,
        end_ep: int = 999,
        vcodec: str = "H264",
        quality: str = "SDR",
        audio_lang: Optional[str] = None,
        episode_refs: Optional[List[str]] = None,
    ) -> List[str]:
        params: Dict[str, Any] = {
            "url": url,
            "season": season,
            "start_ep": start_ep,
            "end_ep": end_ep,
            "vcodec": vcodec,
            "quality": quality,
            "audio_lang": audio_lang,
            "output_dir": config.get_output_dir(),
        }
        if episode_refs:
            params["episode_refs"] = episode_refs
            return build_job("skyshowtime", "episodes", params)
        return build_job("skyshowtime", "video", params)

    @staticmethod
    def make_download_batch_cmd(
        url: str,
        episode_refs: List[str],
        vcodec: str = "H264",
        quality: str = "SDR",
        audio_lang: Optional[str] = None,
    ) -> List[str]:
        refs = [r.strip() for r in episode_refs if r and str(r).strip()]
        if not refs:
            raise ValueError("Lista SkyShowtime epizoda je prazna.")
        return SkyShowtimeAdapter.make_download_cmd(
            url=url,
            vcodec=vcodec,
            quality=quality,
            audio_lang=audio_lang,
            episode_refs=refs,
        )

    @staticmethod
    def make_download_direct_cmd(
        manifest_url: str,
        license_url: str,
        title: str = "",
        license_token: str = "",
        vcodec: str = "H264",
        quality: str = "SDR",
        audio_lang: Optional[str] = None,
    ) -> List[str]:
        return build_job(
            "skyshowtime",
            "direct",
            {
                "manifest_url": manifest_url,
                "license_url": license_url,
                "license_token": license_token,
                "title": title,
                "vcodec": vcodec,
                "quality": quality,
                "audio_lang": audio_lang,
                "output_dir": config.get_output_dir(),
            },
        )
