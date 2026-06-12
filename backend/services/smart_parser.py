import re
import logging
from typing import Dict, Any, Optional

from backend.services.voyo_adapter import VoyoAdapter
from backend.services.hrti_adapter import HrtiAdapter
from backend.services.eon_adapter import EonAdapter
from backend.services.rts_adapter import RtsAdapter
from backend.services.hbo_adapter import HboAdapter
from backend.services.skyshowtime_adapter import SkyShowtimeAdapter

logger = logging.getLogger(__name__)

# Regular expressions for matching Streaming URLs
VOYO_SERIES_RE = re.compile(r"voyo\.(?:rs|hr)/(?:[^/]+/)?serije/(\d+)", re.I)
VOYO_VIDEO_RE = re.compile(
    r"voyo\.(?:rs|hr)/.*_(\d+)\.html"
    r"|voyo\.(?:rs|hr)/proizvod/(\d+)"
    r"|voyo\.(?:rs|hr)/.*[?&]id=(\d+)",
    re.I,
)

HRTI_VOD_RE = re.compile(
    r"hrti\.hrt\.hr/(?:video(?:/vod)?|videostore|linear|category)/(?:show/)?([a-f0-9\-]{36})",
    re.I,
)

RTS_VIDEO_RE = re.compile(
    r"rtsplaneta\.rs/(?:[^/]+/)?video/(?:show/)?(\d+)",
    re.I,
)

EON_VOD_RE = re.compile(
    r"eon\.tv/(?:player|ondemand/detail|vod/detail|series/detail|live|channel)/([^?#]+)",
    re.I,
)

HBO_URN_RE = re.compile(
    r"(?:play\.)?(?:hbomax|max)\.com/(?:video|episode|page|feature|show|movie|series)/([^?#]+)"
    r"|(?:play\.)?(?:hbomax|max)\.com/.*/([a-f0-9\-]{36})",
    re.I,
)

SKYSHOWTIME_ASSET_RE = re.compile(
    r"skyshowtime\.com/watch/asset(/(?:movies|tv|kids)/[^?#]+)",
    re.I,
)

# Standard resolution labels (sorted highest first)
RESOLUTION_LABELS = {
    4320: "4320p (8K)",
    2160: "2160p (4K)",
    1440: "1440p (2K)",
    1080: "1080p (Full HD)",
    720:  "720p (HD)",
    480:  "480p (SD)",
    360:  "360p",
    240:  "240p",
    144:  "144p",
}


class SmartParser:
    """Detects streaming platform and extracts video/series ID and metadata."""

    @staticmethod
    def detect_service(url: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a URL to identify platform, mode, and target ID.
        
        Returns:
            Dict containing 'service', 'mode', 'target_id' or None if unmatched.
        """
        url = url.strip()
        
        # 1. Voyo
        m = VOYO_SERIES_RE.search(url)
        if m:
            return {"service": "voyo", "mode": "series", "target_id": m.group(1)}
        m = VOYO_VIDEO_RE.search(url)
        if m:
            video_id = m.group(1) or m.group(2) or m.group(3)
            return {"service": "voyo", "mode": "video", "target_id": video_id}

        # 2. SkyShowtime (before HBO/HRTi)
        if "skyshowtime.com" in url.lower():
            m = SKYSHOWTIME_ASSET_RE.search(url)
            if m:
                slug = m.group(1)
                mode = "series" if slug.startswith(("/tv/", "/kids/")) else "video"
                return {"service": "skyshowtime", "mode": mode, "target_id": url.strip()}

        # 3. HBO Max / Max (before HRTi to avoid UUID collision)
        if any(d in url.lower() for d in ("hbomax.com", "max.com")):
            m = HBO_URN_RE.search(url)
            if m:
                raw_id = m.group(1) or m.group(2)
                # Extract last UUID if path contains multiple segments
                uuid_m = re.findall(r"[a-f0-9\-]{36}", raw_id, re.I)
                video_id = uuid_m[-1] if uuid_m else raw_id.rstrip("/").rsplit("/", 1)[-1]
                return {"service": "hbomax", "mode": "video", "target_id": video_id}

        # 4. HRTi (scoped to hrti.hrt.hr domain only)
        if "hrti.hrt.hr" in url.lower():
            m = HRTI_VOD_RE.search(url)
            if m:
                return {"service": "hrti", "mode": "video", "target_id": m.group(1)}
            uuid_m = re.search(r"([a-f0-9\-]{36})", url, re.I)
            if uuid_m:
                return {"service": "hrti", "mode": "video", "target_id": uuid_m.group(1)}

        # 5. RTS Planeta
        if "rtsplaneta.rs" in url.lower():
            m = RTS_VIDEO_RE.search(url)
            if m:
                return {"service": "rts", "mode": "video", "target_id": m.group(1)}
            ep_match = re.search(r"/episode/(\d+)", url)
            if ep_match:
                return {"service": "rts", "mode": "video", "target_id": ep_match.group(1)}
            serial_match = re.search(r"/(?:serial|film)/(\d+)", url)
            if serial_match:
                return {"service": "rts", "mode": "video", "target_id": serial_match.group(1)}

        # 6. EON TV
        if "eon.tv" in url.lower():
            m = EON_VOD_RE.search(url)
            if m:
                target_id = m.group(1).rstrip("/")
                if "/live/" in url.lower() or "/channel/" in url.lower():
                    return {"service": "eon", "mode": "live", "target_id": target_id}
                if "/series/" in url.lower():
                    return {"service": "eon", "mode": "series", "target_id": target_id}
                return {"service": "eon", "mode": "vod", "target_id": target_id}
            return {"service": "eon", "mode": "vod", "target_id": url}

        # 7. Generic URLs (Universal Downloader - yt-dlp supported sites)
        if url.lower().startswith("http://") or url.lower().startswith("https://"):
            return {"service": "ytdlp", "mode": "video", "target_id": url, "generic": True}

        return None

    @staticmethod
    def _extract_ytdlp_metadata(target_id: str) -> Dict[str, Any]:
        """
        Extract full video metadata using yt-dlp including ALL available
        resolutions (up to 8K), subtitles, auto-captions, duration, and more.
        """
        try:
            import yt_dlp
            from urllib.parse import urlparse

            from backend.services.ytdlp_common import ytdlp_metadata_opts

            # Try 1: standard metadata options (uses ytdlp_cookies.txt if uploaded)
            opts = ytdlp_metadata_opts()
            info = None
            last_err = None
            
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(target_id, download=False)
            except Exception as e:
                last_err = e
                logger.warning("Standard yt-dlp metadata extraction failed, trying fallback options: %s", e)

            # Try 2: If standard fails, try using browser cookies (chrome, edge, brave, firefox)
            if not info:
                for browser in ["chrome", "edge", "brave", "firefox"]:
                    try:
                        logger.info("Retrying metadata extraction with cookies from browser: %s", browser)
                        browser_opts = {**opts, "cookiesfrombrowser": (browser, None, None, None)}
                        with yt_dlp.YoutubeDL(browser_opts) as ydl:
                            info = ydl.extract_info(target_id, download=False)
                        if info:
                            logger.info("Metadata extraction succeeded with cookies from browser: %s", browser)
                            break
                    except Exception as retry_err:
                        logger.warning("Retry with cookies from %s failed: %s", browser, retry_err)

            # Try 3: If still fails, try using impersonate chrome (without cookies)
            if not info:
                try:
                    logger.info("Retrying metadata extraction with impersonate chrome")
                    from yt_dlp.networking.impersonate import ImpersonateTarget
                    target = ImpersonateTarget.from_str("chrome")
                    imp_opts = {**opts, "impersonate": target}
                    with yt_dlp.YoutubeDL(imp_opts) as ydl:
                        info = ydl.extract_info(target_id, download=False)
                except Exception as imp_err:
                    logger.warning("Retry with impersonate failed: %s", imp_err)

            if not info:
                if last_err:
                    raise last_err
                raise ValueError("yt-dlp returned no info")

            title = info.get("title") or ""
            description = info.get("description") or ""
            if description and len(description) > 250:
                description = description[:250] + "..."
            thumbnail = info.get("thumbnail") or ""
            duration_secs = info.get("duration")
            uploader = info.get("uploader") or info.get("channel") or ""
            view_count = info.get("view_count")
            like_count = info.get("like_count")
            upload_date = info.get("upload_date")  # YYYYMMDD string

            # ── Resolve ALL available resolutions ───────────────────────────
            formats = info.get("formats") or []
            height_set: set[int] = set()

            for f in formats:
                h = f.get("height")
                # Skip audio-only streams (no height), and non-integer heights
                if h and isinstance(h, int) and h > 0:
                    # Only include actual video formats (not audio-only)
                    vcodec = f.get("vcodec") or ""
                    if vcodec and vcodec != "none":
                        height_set.add(h)

            # If no video-codec-tagged formats found, fall back to any with height
            if not height_set:
                for f in formats:
                    h = f.get("height")
                    if h and isinstance(h, int) and h > 0:
                        height_set.add(h)

            sorted_heights = sorted(height_set, reverse=True)

            # Build resolution list — use descriptive labels for known heights
            avail_res = []
            for h in sorted_heights:
                label = RESOLUTION_LABELS.get(h, f"{h}p")
                avail_res.append(label)

            # Always expose at least a basic set as fallback
            if not avail_res:
                avail_res = ["1080p (Full HD)", "720p (HD)", "480p (SD)", "360p"]

            # ── Subtitles & Auto-Captions ────────────────────────────────────
            subtitles = info.get("subtitles") or {}
            auto_subs = info.get("automatic_captions") or {}

            avail_subs = sorted(subtitles.keys())
            avail_auto = sorted(auto_subs.keys())

            # ── Extra metadata ───────────────────────────────────────────────
            domain = urlparse(target_id).netloc.replace("www.", "")
            if not title:
                title = f"Video sa {domain}"

            extra: Dict[str, Any] = {}
            if duration_secs:
                mins, secs = divmod(int(duration_secs), 60)
                hours, mins = divmod(mins, 60)
                if hours:
                    extra["duration_str"] = f"{hours}h {mins}m {secs}s"
                else:
                    extra["duration_str"] = f"{mins}m {secs}s"
                extra["duration_secs"] = duration_secs
            if uploader:
                extra["uploader"] = uploader
            if view_count is not None:
                extra["view_count"] = view_count
            if like_count is not None:
                extra["like_count"] = like_count
            if upload_date:
                try:
                    from datetime import datetime
                    dt = datetime.strptime(upload_date, "%Y%m%d")
                    extra["upload_date"] = dt.strftime("%d.%m.%Y")
                except Exception:
                    extra["upload_date"] = upload_date

            mode = "video"
            episodes = None
            entries = info.get("entries") or []
            if info.get("_type") == "playlist" or len(entries) > 1:
                ep_list = []
                for idx, ent in enumerate(entries):
                    if not ent:
                        continue
                    ep_list.append({
                        "id": ent.get("id") or str(idx + 1),
                        "title": ent.get("title") or f"Stavka {idx + 1}",
                        "season": 1,
                        "episode": idx + 1,
                    })
                if ep_list:
                    mode = "playlist"
                    episodes = ep_list
                    if not title:
                        title = info.get("title") or f"Plejlista ({len(ep_list)} stavki)"

            payload: Dict[str, Any] = {
                "success": True,
                "service": "ytdlp",
                "mode": mode,
                "target_id": target_id,
                "title": title,
                "description": description or "Preuzmite video preko univerzalnog preuzimača.",
                "thumbnail": thumbnail,
                "available_resolutions": avail_res,
                "available_subtitles": avail_subs,
                "available_auto_subtitles": avail_auto,
                **extra,
            }
            if episodes:
                payload["episodes"] = episodes
                payload["playlist_count"] = len(episodes)
            return payload

        except Exception as ex:
            logger.warning("yt-dlp metadata extraction failed: %s", ex)
            from urllib.parse import urlparse
            domain = urlparse(target_id).netloc.replace("www.", "")
            return {
                "success": True,
                "metadata_partial": True,
                "service": "ytdlp",
                "mode": "video",
                "target_id": target_id,
                "title": f"Video sa {domain}",
                "description": f"Metapodaci nisu dostupni — preuzimanje je i dalje moguće.",
                "thumbnail": ""
            }

    @staticmethod
    def get_metadata(url: str, force_service: Optional[str] = None) -> Dict[str, Any]:
        """Detect service and retrieve structured metadata for preview."""
        try:
            if force_service == "ytdlp":
                url = url.strip()
                if not url.lower().startswith(("http://", "https://")):
                    return {"success": False, "error": "URL mora počinjati sa http:// ili https://"}
                return SmartParser._extract_ytdlp_metadata(url)

            detected = SmartParser.detect_service(url)
            if not detected:
                return {"success": False, "error": "URL nije prepoznat kao podržani servis."}
            
            service = detected["service"]
            mode = detected["mode"]
            target_id = detected["target_id"]

            if service == "voyo":
                if mode == "series":
                    info = VoyoAdapter.get_series_info(int(target_id))
                    if info.get("success"):
                        return {
                            "success": True,
                            "service": "voyo",
                            "mode": "series",
                            "target_id": target_id,
                            "title": info.get("title"),
                            "description": info.get("description"),
                            "episodes": info.get("episodes"),
                            "seasons": info.get("seasons"),
                        }
                    return {"success": False, "error": info.get("error", "Greška pri preuzimanju serije.")}
                info = VoyoAdapter.get_video_info(int(target_id))
                if info.get("success"):
                    return {
                        "success": True,
                        "service": "voyo",
                        "mode": "video",
                        "target_id": target_id,
                        "title": info.get("title", f"Voyo Video {target_id}"),
                        "description": info.get("description", ""),
                        "duration_str": info.get("duration_str"),
                        "thumbnail": info.get("thumbnail"),
                        "drm_hint": bool(info.get("drm_hint", info.get("drm"))),
                        "drm": bool(info.get("drm_hint", info.get("drm"))),
                        "has_subs": bool(info.get("has_subs")),
                        "streamable": info.get("streamable"),
                        "drm_blocking": info.get("drm_blocking"),
                        "probe_ok": info.get("probe_ok"),
                        "drm_type": info.get("drm_type"),
                        "stream_reason": info.get("stream_reason"),
                    }
                return {
                    "success": True,
                    "service": "voyo",
                    "mode": "video",
                    "target_id": target_id,
                    "title": f"Voyo Video (ID: {target_id})",
                    "description": "Metapodaci nisu dostupni — preuzimanje je i dalje moguće.",
                    "metadata_partial": True,
                }

            elif service == "hrti":
                try:
                    series_info = HrtiAdapter.get_series_episodes(target_id)
                    if (series_info
                            and series_info.get("success") is not False
                            and series_info.get("items")):
                        episodes = []
                        for item in series_info["items"]:
                            episodes.append({
                                "id": item.get("id"),
                                "title": item.get("title"),
                                "season": item.get("season") or 1,
                                "episode": item.get("episode") or 0,
                                "length_mins": 0,
                                "drm": False,
                                "has_subs": False,
                            })
                        series_title = series_info.get("series_title") or f"HRTi Serija"
                        return {
                            "success": True,
                            "service": "hrti",
                            "mode": "series",
                            "target_id": target_id,
                            "title": series_title,
                            "description": "Preuzmite epizode sa HRTi.",
                            "episodes": episodes,
                            "seasons": series_info.get("seasons") or [],
                        }
                except Exception as exc:
                    logger.warning("HRTi series lookup failed for %s: %s", target_id, exc)
                return {
                    "success": True,
                    "service": "hrti",
                    "mode": "video",
                    "target_id": target_id,
                    "title": f"HRTi Video (ID: {target_id})",
                    "description": "Započnite preuzimanje filma ili emisije sa HRTi."
                }

            elif service == "eon":
                try:
                    info = EonAdapter.get_vod_info(target_id)
                    return {
                        "success": True,
                        "service": "eon",
                        "mode": mode,
                        "target_id": target_id,
                        "title": info.get("title", f"EON {mode.upper()} {target_id}"),
                        "description": info.get("description", ""),
                        "thumbnail": info.get("thumbnail", ""),
                        "episodes": info.get("episodes", [])
                    }
                except Exception:
                    return {
                        "success": True,
                        "service": "eon",
                        "mode": mode,
                        "target_id": target_id,
                        "title": f"EON {mode.upper()} (ID: {target_id})",
                        "description": "Započnite preuzimanje EON naslova."
                    }

            elif service == "rts":
                info = RtsAdapter.get_video_info(target_id)
                if info.get("success"):
                    return {
                        "success": True,
                        "service": "rts",
                        "mode": "video",
                        "target_id": target_id,
                        "title": info.get("title"),
                        "description": info.get("description") or "Započnite preuzimanje emisije ili serije sa RTS Planeta.",
                        "thumbnail": info.get("thumbnail", "")
                    }
                return {
                    "success": True,
                    "service": "rts",
                    "mode": "video",
                    "target_id": target_id,
                    "title": f"RTS Planeta Video (ID: {target_id})",
                    "description": "Započnite preuzimanje emisije ili serije sa RTS Planeta."
                }

            elif service == "hbomax":
                return {
                    "success": True,
                    "service": "hbomax",
                    "mode": "video",
                    "target_id": target_id,
                    "title": f"HBO Max Video (ID: {target_id})",
                    "description": "Započnite preuzimanje videa sa HBO Max."
                }

            elif service == "skyshowtime":
                if mode == "series":
                    info = SkyShowtimeAdapter.get_series_info(target_id)
                    if info.get("success"):
                        return {
                            "success": True,
                            "service": "skyshowtime",
                            "mode": "series",
                            "target_id": target_id,
                            "title": info.get("title", "SkyShowtime serija"),
                            "description": info.get("description", ""),
                            "episodes": [
                                {
                                    "id": ep["id"],
                                    "title": ep.get("title", ""),
                                    "season": ep.get("season", 0),
                                    "episode": ep.get("episode", 0),
                                    "length_mins": ep.get("length_mins", 0),
                                    "drm": ep.get("drm", True),
                                }
                                for ep in info.get("episodes", [])
                            ],
                        }
                meta = SkyShowtimeAdapter.get_title_metadata(target_id)
                if meta.get("success"):
                    return {
                        "success": True,
                        "service": "skyshowtime",
                        "mode": mode,
                        "target_id": target_id,
                        "title": meta.get("title", "SkyShowtime"),
                        "description": meta.get("description", "Započnite preuzimanje sa SkyShowtime."),
                    }
                return {
                    "success": True,
                    "service": "skyshowtime",
                    "mode": mode,
                    "target_id": target_id,
                    "title": "SkyShowtime",
                    "description": "Započnite preuzimanje sa SkyShowtime.",
                }

            elif service == "ytdlp":
                meta = SmartParser._extract_ytdlp_metadata(target_id)
                if detected.get("generic"):
                    meta["generic_url"] = True
                return meta

        except Exception as e:
            logger.exception("Error fetching metadata for %s", url)
            return {"success": False, "error": f"Greška tokom preuzimanja detalja: {str(e)}"}

        return {"success": False, "error": "URL nije podržan."}