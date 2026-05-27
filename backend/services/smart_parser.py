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
                # Extract metadata dynamically using yt-dlp asynchronously
                try:
                    import yt_dlp
                    import urllib.parse
                    
                    ydl_opts = {
                        'extract_flat': True,
                        'skip_download': True,
                        'quiet': True,
                        'no_warnings': True,
                    }
                    
                    # Call yt-dlp info extraction
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(target_id, download=False)
                        
                    title = info.get("title")
                    description = info.get("description", "")
                    if description and len(description) > 200:
                        description = description[:200] + "..."
                    thumbnail = info.get("thumbnail", "")
                    
                    from urllib.parse import urlparse
                    domain = urlparse(target_id).netloc.replace("www.", "")
                    
                    if not title:
                        title = f"Video sa {domain}"
                        
                    return {
                        "success": True,
                        "service": "ytdlp",
                        "mode": "video",
                        "target_id": target_id,
                        "title": title,
                        "description": description or "Preuzmite video preko univerzalnog preuzimača.",
                        "thumbnail": thumbnail
                    }
                except Exception as ex:
                    logger.warning(f"Fast yt-dlp metadata extraction failed: {ex}")
                    from urllib.parse import urlparse
                    domain = urlparse(target_id).netloc.replace("www.", "")
                    return {
                        "success": True,
                        "service": "ytdlp",
                        "mode": "video",
                        "target_id": target_id,
                        "title": f"Video sa {domain}",
                        "description": f"Započnite preuzimanje sa adrese: {target_id[:60]}...",
                        "thumbnail": ""
                    }

        except Exception as e:
            logger.exception(f"Error fetching metadata for {url}")
            return {"success": False, "error": f"Greška tokom preuzimanja detalja: {str(e)}"}

        return {"success": False, "error": "URL nije podržan."}