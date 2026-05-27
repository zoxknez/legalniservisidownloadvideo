import re
import logging
from typing import Dict, Any, Optional

from backend.services.voyo_adapter import VoyoAdapter
from backend.services.hrti_adapter import HrtiAdapter
from backend.services.eon_adapter import EonAdapter
from backend.services.rts_adapter import RtsAdapter
from backend.services.hbo_adapter import HboAdapter

logger = logging.getLogger(__name__)

# Regular expressions for matching Streaming URLs
VOYO_SERIES_RE = re.compile(r"voyo\.rs/(?:[^/]+/)?serije/(\d+)", re.I)
VOYO_VIDEO_RE = re.compile(r"voyo\.rs/.*_(\d+)\.html|voyo\.rs/proizvod/(\d+)", re.I)

HRTI_VOD_RE = re.compile(r"hrti\.hrt\.hr/(?:video|videostore|linear)/show/([a-f0-9\-]{36})", re.I)
HRTI_UUID_RE = re.compile(r"([a-f0-9\-]{36})", re.I)

RTS_VIDEO_RE = re.compile(r"rtsplaneta\.rs/(?:[^/]+/)?video/show/(\d+)", re.I)

EON_VOD_RE = re.compile(r"eon\.tv/player/([a-f0-9\-]+)", re.I)

HBO_URN_RE = re.compile(r"hbomax\.com/(?:video|episode|page|feature)/([^?#]+)|max\.com/show/([^?#]+)", re.I)

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
            video_id = m.group(1) or m.group(2)
            return {"service": "voyo", "mode": "video", "target_id": video_id}

        # 2. HRTi
        m = HRTI_VOD_RE.search(url)
        if m:
            return {"service": "hrti", "mode": "video", "target_id": m.group(1)}
        m = HRTI_UUID_RE.search(url)
        if m:
            return {"service": "hrti", "mode": "video", "target_id": m.group(1)}

        # 3. RTS Planeta
        if "rtsplaneta.rs" in url.lower():
            ep_match = re.search(r"/episode/(\d+)", url)
            if ep_match:
                return {"service": "rts", "mode": "video", "target_id": ep_match.group(1)}
            show_match = re.search(r"/(?:video|show)/show/(\d+)|/video/(\d+)", url)
            if show_match:
                vid_id = show_match.group(1) or show_match.group(2)
                return {"service": "rts", "mode": "video", "target_id": vid_id}
            serial_match = re.search(r"/serial/(\d+)", url)
            if serial_match:
                return {"service": "rts", "mode": "video", "target_id": serial_match.group(1)}

        # 4. EON TV
        m = EON_VOD_RE.search(url)
        if m:
            return {"service": "eon", "mode": "vod", "target_id": m.group(1)}

        # 5. HBO Max
        m = HBO_URN_RE.search(url)
        if m:
            video_id = m.group(1) or m.group(2)
            return {"service": "hbomax", "mode": "video", "target_id": video_id}

        # 6. Generic URLs (Universal Downloader - yt-dlp supported sites)
        if url.lower().startswith("http://") or url.lower().startswith("https://"):
            return {"service": "ytdlp", "mode": "video", "target_id": url}

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

            # Use 'all' format to get every available format stream
            ydl_opts = {
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
                # Request all formats so we see every available resolution
                'listformats': False,
                # Don't limit format selection — we want the full formats list
                'format': 'bestvideo*+bestaudio/best',
                # Don't apply any geo-restrictions or age-gate filter
                'age_limit': None,
                # Include all formats in the extraction
                'youtube_include_dash_manifest': True,
                'youtube_include_hls_manifest': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target_id, download=False)

            if not info:
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

            return {
                "success": True,
                "service": "ytdlp",
                "mode": "video",
                "target_id": target_id,
                "title": title,
                "description": description or "Preuzmite video preko univerzalnog preuzimača.",
                "thumbnail": thumbnail,
                "available_resolutions": avail_res,
                "available_subtitles": avail_subs,
                "available_auto_subtitles": avail_auto,
                **extra
            }

        except Exception as ex:
            logger.warning(f"yt-dlp metadata extraction failed: {ex}")
            from urllib.parse import urlparse
            domain = urlparse(target_id).netloc.replace("www.", "")
            return {
                "success": True,
                "service": "ytdlp",
                "mode": "video",
                "target_id": target_id,
                "title": f"Video sa {domain}",
                "description": f"Započnite preuzimanje sa adrese: {target_id[:80]}",
                "thumbnail": ""
            }

    @staticmethod
    def get_metadata(url: str) -> Dict[str, Any]:
        """Detect service and retrieve structured metadata for preview."""
        try:
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
                            "episodes": info.get("episodes")
                        }
                    return {"success": False, "error": info.get("error", "Greška pri preuzimanju serije.")}
                else:
                    return {
                        "success": True,
                        "service": "voyo",
                        "mode": "video",
                        "target_id": target_id,
                        "title": f"Voyo Video (ID: {target_id})",
                        "description": "Započnite preuzimanje Voyo videa."
                    }

            elif service == "hrti":
                series_info = HrtiAdapter.get_series_episodes(target_id)
                if series_info and series_info.get("items"):
                    episodes = []
                    for item in series_info["items"]:
                        episodes.append({
                            "id": item.get("id"),
                            "title": item.get("title"),
                            "season": 1,
                            "episode": 0,
                            "length_mins": 0,
                            "drm": False,
                            "has_subs": False
                        })
                    return {
                        "success": True,
                        "service": "hrti",
                        "mode": "series",
                        "target_id": target_id,
                        "title": f"HRTi Serija (ID: {target_id})",
                        "description": "Preuzmite epizode sa HRTi.",
                        "episodes": episodes
                    }
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
                        "mode": "vod",
                        "target_id": target_id,
                        "title": info.get("title", f"EON VOD {target_id}"),
                        "description": info.get("description", ""),
                        "thumbnail": info.get("thumbnail", ""),
                        "episodes": info.get("episodes", [])
                    }
                except Exception:
                    return {
                        "success": True,
                        "service": "eon",
                        "mode": "vod",
                        "target_id": target_id,
                        "title": f"EON VOD (ID: {target_id})",
                        "description": "Započnite preuzimanje EON VOD naslova."
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

            elif service == "ytdlp":
                return SmartParser._extract_ytdlp_metadata(target_id)

        except Exception as e:
            logger.exception(f"Error fetching metadata for {url}")
            return {"success": False, "error": f"Greška tokom preuzimanja detalja: {str(e)}"}

        return {"success": False, "error": "URL nije podržan."}