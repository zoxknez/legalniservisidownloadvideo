#!/usr/bin/env python3
"""
EON TV Video Downloader
Supports VOD, Series, and Live content with Widevine DRM (CENC) decryption.

Usage:
    # Save device credentials
    python eon_downloader.py -u user@email.com -p Password --device-serial SERIAL --device-number NUMBER --save-device

    # Health check
    python eon_downloader.py --health

    # List channels
    python eon_downloader.py --list-channels

    # Download VOD (DRM-protected DASH)
    python eon_downloader.py --vod "https://example.com/manifest.mpd" --license-url "https://lic.example.com/wv"

    # Live capture with DRM
    python eon_downloader.py --live -c "Channel Name" --duration 120

    # Series download
    python eon_downloader.py --series "12345" --episodes "1-5"
"""

import argparse
import base64
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import requests
import xmltodict

from backend.utils.cancellable_subprocess import raise_if_cancelled, run as run_subprocess
from backend.utils.media_validation import promote_validated_media, temporary_media_path

from .eon_auth import (
    CONFIG_DIR,
    EonAuthError,
    api_request,
    api_status,
    device_profile_status,
    login_api,
    refresh_api_token,
    save_device_profile,
    token_status,
)

logger = logging.getLogger(__name__)

# Centralized DRM Manager (shared singleton with key caching, multi-PSSH support)
try:
    from backend.services.drm_manager import drm_manager as _drm_manager
    _USE_CENTRAL_DRM = True
except ImportError:
    _USE_CENTRAL_DRM = False
    _drm_manager = None

APP_ROOT = Path(__file__).resolve().parent
CHANNEL_CATALOG_FILES = [APP_ROOT / "eon_channels.json", CONFIG_DIR / "eon_channels.json"]
SERIES_CATALOG_FILES = [APP_ROOT / "eon_series.json", CONFIG_DIR / "eon_series.json"]
VOD_CATALOG_FILES = [APP_ROOT / "eon_vod.json", CONFIG_DIR / "eon_vod.json"]
EPG_CATALOG_FILES = [APP_ROOT / "eon_epg.json", CONFIG_DIR / "eon_epg.json"]

SAFE_MESSAGE = (
    "EON engine with full Widevine DRM decryption support. "
    "Supports VOD, Series, and Live stream download with automatic "
    "PSSH extraction, license exchange, decryption, and muxing."
)

DIRECT_MEDIA_EXTENSIONS = (
    ".m3u8",
    ".mpd",
    ".mp4",
    ".m4v",
    ".mov",
    ".webm",
    ".mkv",
    ".ts",
)

WIDEVINE_SYSTEM_ID = "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"


class EonSafeError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Widevine CDM wrapper (same pattern as hrti_downloader.py)
# ---------------------------------------------------------------------------

class WidevineCDM:
    """Wrapper around pywidevine for Widevine license exchange."""

    def __init__(self, device_path: Optional[str] = None):
        self.device_path = device_path
        self.cdm = None
        self.device = None
        self.legacy_mode = False
        self.PSSH = None
        self._init_cdm()

    def _find_device_file(self) -> Optional[Path]:
        search_paths = [
            Path.cwd() / "device.wvd",
            Path.cwd() / "cdm" / "device.wvd",
            Path.home() / ".wvd" / "device.wvd",
            Path.home() / ".videodownload" / "device.wvd",
            APP_ROOT / "device.wvd",
            APP_ROOT / "binaries" / "device.wvd",
        ]
        if self.device_path:
            p = Path(self.device_path)
            if p.exists():
                if p.is_file() and p.suffix == ".wvd":
                    return p
                elif p.is_dir():
                    wvd = list(p.glob("*.wvd"))
                    if wvd:
                        return wvd[0]
        for path in search_paths:
            if path.exists():
                return path
        return None

    def _init_cdm(self):
        try:
            from pywidevine.cdm import Cdm
            from pywidevine.device import Device
            from pywidevine.pssh import PSSH

            self.PSSH = PSSH
            device_file = self._find_device_file()
            if device_file:
                self.device = Device.load(device_file)
                self.cdm = Cdm.from_device(self.device)
                logger.info(f"Loaded CDM from: {device_file}")
            else:
                logger.warning("No .wvd device file found.")
        except ImportError:
            logger.warning("Modern pywidevine not found.")
            self._init_legacy_cdm()

    def _init_legacy_cdm(self):
        try:
            from pywidevine.decrypt.wvdecryptcustom import WvDecrypt  # noqa
            self.legacy_mode = True
            logger.info("Using legacy pywidevine CDM")
        except ImportError as e:
            raise RuntimeError(f"pywidevine not installed: {e}")

    def is_ready(self) -> bool:
        return self.cdm is not None or self.legacy_mode

    def get_keys(self, pssh_b64: str, license_url: str, headers: dict) -> List[str]:
        if self.legacy_mode:
            return self._get_keys_legacy(pssh_b64, license_url, headers)
        return self._get_keys_modern(pssh_b64, license_url, headers)

    def _unwrap_license(self, resp: requests.Response) -> bytes:
        """
        Handle different license response formats.
        Some servers return JSON with base64 license, others return raw protobuf.
        """
        try:
            j = resp.json()
            # DRMtoday format: {"status":"OK","license":"<base64>"}
            if j.get("status") == "OK" and "license" in j:
                return base64.b64decode(j["license"])
            # Other formats
            for field in ("license", "ckc", "message", "licenseData", "license_data", "widevine_license"):
                if field in j:
                    return base64.b64decode(j[field])
        except Exception:
            pass
        # Already raw protobuf
        return resp.content

    def _get_keys_modern(self, pssh_b64: str, license_url: str, headers: dict) -> List[str]:
        if not self.cdm:
            raise RuntimeError("CDM not initialized. Check device.wvd file.")
        pssh = self.PSSH(pssh_b64)
        session_id = self.cdm.open()
        try:
            challenge = self.cdm.get_license_challenge(session_id, pssh)
            resp = requests.post(license_url, data=challenge, headers=headers)
            resp.raise_for_status()

            logger.debug(f"License response: CT={resp.headers.get('Content-Type')} "
                         f"size={len(resp.content)}B "
                         f"first_bytes={resp.content[:8].hex()}")

            license_bytes = self._unwrap_license(resp)
            logger.debug(f"Unwrapped license: size={len(license_bytes)}B "
                         f"first_bytes={license_bytes[:8].hex()}")

            self.cdm.parse_license(session_id, license_bytes)
            keys = []
            for key in self.cdm.get_keys(session_id):
                if key.type == "CONTENT":
                    keys.append(f"{key.kid.hex}:{key.key.hex()}")
            return keys
        finally:
            self.cdm.close(session_id)

    def _get_keys_legacy(self, pssh_b64: str, license_url: str, headers: dict) -> List[str]:
        from pywidevine.decrypt.wvdecryptcustom import WvDecrypt
        for attempt in range(3):
            try:
                wvd = WvDecrypt(init_data_b64=pssh_b64.encode(), cert_data_b64=None)
                challenge = wvd.get_challenge()
                resp = requests.post(license_url, data=challenge, headers=headers)
                resp.raise_for_status()
                wvd.update_license(base64.b64encode(resp.content))
                success, keys = wvd.start_process()
                if success and keys:
                    return keys
            except Exception as e:
                logger.warning(f"Key attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(2)
        raise Exception("Failed to get decryption keys after 3 attempts")


# ---------------------------------------------------------------------------
# MPD Parsing / PSSH extraction
# ---------------------------------------------------------------------------

def extract_pssh_from_mpd(mpd_text: str) -> Optional[str]:
    """Extract the first Widevine PSSH from MPD XML."""
    try:
        mpd = xmltodict.parse(mpd_text)
        periods = mpd.get("MPD", {}).get("Period", [])
        if isinstance(periods, dict):
            periods = [periods]
        for period in periods:
            adapt_sets = period.get("AdaptationSet", [])
            if isinstance(adapt_sets, dict):
                adapt_sets = [adapt_sets]
            for adapt in adapt_sets:
                cp = adapt.get("ContentProtection", [])
                if isinstance(cp, dict):
                    cp = [cp]
                for prot in cp:
                    scheme = prot.get("@schemeIdUri", "")
                    if scheme.lower() == WIDEVINE_SYSTEM_ID.lower():
                        pssh_elem = prot.get("cenc:pssh") or prot.get("pssh")
                        if pssh_elem:
                            return pssh_elem if isinstance(pssh_elem, str) else pssh_elem.get("#text", "")
    except Exception as e:
        logger.warning(f"MPD PSSH parse error: {e}")

    # Fallback: regex
    m = re.search(r"<(?:cenc:)?pssh[^>]*>([A-Za-z0-9+/=]+)</(?:cenc:)?pssh>", mpd_text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def extract_license_url_from_mpd(mpd_text: str) -> Optional[str]:
    """Try to extract the Widevine license URL from MPD XML (ms:laurl or similar)."""
    try:
        mpd = xmltodict.parse(mpd_text)
        periods = mpd.get("MPD", {}).get("Period", [])
        if isinstance(periods, dict):
            periods = [periods]
        for period in periods:
            adapt_sets = period.get("AdaptationSet", [])
            if isinstance(adapt_sets, dict):
                adapt_sets = [adapt_sets]
            for adapt in adapt_sets:
                cp = adapt.get("ContentProtection", [])
                if isinstance(cp, dict):
                    cp = [cp]
                for prot in cp:
                    scheme = prot.get("@schemeIdUri", "")
                    if scheme.lower() == WIDEVINE_SYSTEM_ID.lower():
                        # Check for ms:laurl or similar license acquisition URL
                        laurl = prot.get("ms:laurl") or prot.get("clearkey:Laurl") or prot.get("dashif:Laurl")
                        if isinstance(laurl, dict):
                            return laurl.get("@licenseUrl") or laurl.get("@Url") or laurl.get("#text")
                        if isinstance(laurl, str):
                            return laurl
    except Exception:
        pass

    # Fallback: regex for laurl
    m = re.search(r'licenseUrl\s*=\s*["\']([^"\']+)["\']', mpd_text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def get_best_streams(mpd_text: str) -> Dict[str, Any]:
    """Parse MPD and return the best (highest bitrate) video and audio stream info."""
    try:
        mpd = xmltodict.parse(mpd_text)
        periods = mpd.get("MPD", {}).get("Period", [])
        if isinstance(periods, dict):
            periods = [periods]

        max_video_br = 0
        max_audio_br = 0

        for period in periods:
            adapt_sets = period.get("AdaptationSet", [])
            if isinstance(adapt_sets, dict):
                adapt_sets = [adapt_sets]
            for adapt in adapt_sets:
                mime = adapt.get("@mimeType", adapt.get("@contentType", ""))
                reps = adapt.get("Representation", [])
                if isinstance(reps, dict):
                    reps = [reps]
                for rep in reps:
                    br = int(rep.get("@bandwidth", 0))
                    if "video" in mime:
                        max_video_br = max(max_video_br, br)
                    elif "audio" in mime:
                        max_audio_br = max(max_audio_br, br)

        return {
            "video_bitrate": max_video_br,
            "audio_bitrate": max_audio_br,
        }
    except Exception as e:
        logger.debug(f"Stream parse error: {e}")
        return {}


def is_drm_protected(mpd_text: str) -> bool:
    """Check if MPD manifest contains DRM protection markers."""
    lower = mpd_text.lower()
    drm_markers = (
        "<contentprotection",
        "cenc:pssh",
        "edef8ba9-79d6-4ace-a3c8-27dcd51d21ed",
        "widevine",
    )
    return any(marker in lower for marker in drm_markers)


# ---------------------------------------------------------------------------
# Binary detection
# ---------------------------------------------------------------------------

def detect_binaries() -> Dict[str, str]:
    """Find required external binaries (mp4decrypt, mkvmerge, ffmpeg, aria2c)."""
    is_win = platform.system() == "Windows"
    ext = ".exe" if is_win else ""
    names = {
        "aria2c": f"aria2c{ext}",
        "mp4decrypt": f"mp4decrypt{ext}",
        "mkvmerge": f"mkvmerge{ext}",
        "ffmpeg": f"ffmpeg{ext}",
    }
    found = {}
    for key, binary in names.items():
        path = shutil.which(binary)
        if not path:
            # Check in binaries/ folder
            local = APP_ROOT / "binaries" / binary
            if local.exists():
                path = str(local)
        if not path:
            # Check in project root
            local = APP_ROOT / binary
            if local.exists():
                path = str(local)
        if not path:
            # Common Windows locations
            if key == "mkvmerge":
                for hint in [r"C:\Program Files\MKVToolNix\mkvmerge.exe",
                             r"C:\Program Files (x86)\MKVToolNix\mkvmerge.exe"]:
                    if Path(hint).exists():
                        path = hint
                        break
        if path:
            found[key] = path
        else:
            logger.warning(f"Binary not found in PATH: {binary}")
            found[key] = binary  # fall back to bare name
    return found


# ---------------------------------------------------------------------------
# Utility helpers (unchanged from original)
# ---------------------------------------------------------------------------

def is_url(value: str) -> bool:
    parsed = urlparse(value or "")
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_direct_media_url(value: str) -> bool:
    if not is_url(value):
        return False
    path = urlparse(value).path.lower()
    return any(path.endswith(ext) for ext in DIRECT_MEDIA_EXTENSIONS)


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", value or "eon")
    cleaned = re.sub(r"\s+", ".", cleaned).strip("._-")
    return cleaned[:120] or "eon"


def read_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def first_existing(paths: Iterable[Path]) -> Optional[Path]:
    for path in paths:
        if path.exists():
            return path
    return None


def normalize_channel_catalog(payload: Any) -> List[Dict[str, str]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("channels"), list):
            payload = payload["channels"]
        else:
            payload = [{"name": str(name), "url": str(url)} for name, url in payload.items()]

    channels = []
    if not isinstance(payload, list):
        return channels

    for item in payload:
        if isinstance(item, str):
            channels.append({"name": item, "url": ""})
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("title") or item.get("channel") or "").strip()
            url = str(item.get("url") or item.get("stream_url") or item.get("manifest") or "").strip()
            if name:
                channels.append({"name": name, "url": url})
    return channels


def as_list_payload(payload: Any) -> List[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "results", "videos", "content", "channels", "programs", "entries"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def normalize_media_items(payload: Any) -> List[Dict[str, str]]:
    items = []
    for item in as_list_payload(payload):
        if isinstance(item, str):
            items.append({"id": item, "title": item, "url": item if is_url(item) else ""})
        elif isinstance(item, dict):
            media_id = str(item.get("id") or item.get("ref_id") or item.get("asset_id") or item.get("slug") or "").strip()
            title = str(item.get("title") or item.get("name") or media_id or "Untitled").strip()
            url = str(
                item.get("url")
                or item.get("stream_url")
                or item.get("manifest")
                or item.get("media_url")
                or item.get("playback_url")
                or ""
            ).strip()
            items.append({"id": media_id, "title": title, "url": url})
    return items


def find_first_media_url(payload: Any) -> str:
    if isinstance(payload, str):
        return payload if is_direct_media_url(payload) else ""
    if isinstance(payload, dict):
        for key in ("url", "stream_url", "manifest", "media_url", "playback_url", "src", "href"):
            value = str(payload.get(key) or "").strip()
            if is_direct_media_url(value):
                return value
        for value in payload.values():
            found = find_first_media_url(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = find_first_media_url(item)
            if found:
                return found
    return ""


def find_license_url_in_payload(payload: Any) -> str:
    """Recursively search API response for license URL fields."""
    if isinstance(payload, str):
        return ""
    if isinstance(payload, dict):
        for key in ("license_url", "licenseUrl", "license_server", "licenseServer",
                     "drm_license_url", "widevine_license_url", "widevineLicenseUrl",
                     "la_url", "laUrl"):
            value = str(payload.get(key) or "").strip()
            if value and is_url(value):
                return value
        for value in payload.values():
            found = find_license_url_in_payload(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = find_license_url_in_payload(item)
            if found:
                return found
    return ""


def find_drm_headers_in_payload(payload: Any) -> Dict[str, str]:
    """Recursively search API response for DRM-specific headers."""
    if isinstance(payload, dict):
        for key in ("drm_headers", "drmHeaders", "license_headers", "licenseHeaders", "headers"):
            value = payload.get(key)
            if isinstance(value, dict):
                return {str(k): str(v) for k, v in value.items() if v}
        for value in payload.values():
            found = find_drm_headers_in_payload(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = find_drm_headers_in_payload(item)
            if found:
                return found
    return {}


# ---------------------------------------------------------------------------
# Catalog / API functions (unchanged)
# ---------------------------------------------------------------------------

def load_channels() -> List[Dict[str, str]]:
    try:
        return normalize_channel_catalog(api_request("channels", {}, require_auth=True))
    except Exception:
        path = first_existing(CHANNEL_CATALOG_FILES)
        if not path:
            return []
        return normalize_channel_catalog(read_json_file(path))


def find_channel(name: str) -> Optional[Dict[str, str]]:
    wanted = (name or "").strip().lower()
    for channel in load_channels():
        if channel["name"].strip().lower() == wanted:
            return channel
    return None


def load_series_catalog() -> Dict[str, List[Dict[str, str]]]:
    path = first_existing(SERIES_CATALOG_FILES)
    if not path:
        return {}
    payload = read_json_file(path)
    if isinstance(payload, dict) and isinstance(payload.get("series"), dict):
        payload = payload["series"]
    if not isinstance(payload, dict):
        return {}

    normalized: Dict[str, List[Dict[str, str]]] = {}
    for series_id, episodes in payload.items():
        if not isinstance(episodes, list):
            continue
        normalized_eps = []
        for index, episode in enumerate(episodes, start=1):
            if isinstance(episode, str):
                normalized_eps.append({"title": f"Episode {index}", "url": episode})
            elif isinstance(episode, dict):
                title = str(episode.get("title") or episode.get("name") or f"Episode {index}")
                url = str(episode.get("url") or episode.get("stream_url") or episode.get("manifest") or "")
                normalized_eps.append({"title": title, "url": url})
        normalized[str(series_id)] = normalized_eps
    return normalized


def normalize_episode_items(payload: Any) -> List[Dict[str, str]]:
    episodes = []
    for index, episode in enumerate(as_list_payload(payload), start=1):
        if isinstance(episode, str):
            episodes.append({"title": f"Episode {index}", "url": episode})
        elif isinstance(episode, dict):
            title = str(episode.get("title") or episode.get("name") or f"Episode {index}")
            url = str(
                episode.get("url")
                or episode.get("stream_url")
                or episode.get("manifest")
                or episode.get("media_url")
                or episode.get("playback_url")
                or ""
            )
            episode_id = str(episode.get("id") or episode.get("ref_id") or episode.get("asset_id") or "")
            episodes.append({"id": episode_id, "title": title, "url": url})
    return episodes


def load_series_episodes(series_id: str) -> List[Dict[str, str]]:
    series_id = (series_id or "").strip()
    try:
        payload = api_request("series", {"target": series_id, "series": series_id}, require_auth=True)
        episodes = normalize_episode_items(payload)
        if episodes:
            return episodes
    except Exception:
        pass
    return load_series_catalog().get(series_id, [])


def load_vod_catalog() -> List[Dict[str, str]]:
    path = first_existing(VOD_CATALOG_FILES)
    if not path:
        return []
    return normalize_media_items(read_json_file(path))


def search_vod(query: str) -> List[Dict[str, str]]:
    query = (query or "").strip()
    if not query:
        return []
    try:
        return normalize_media_items(api_request("search", {"query": query}, require_auth=True))
    except Exception:
        q = query.lower()
        return [item for item in load_vod_catalog() if q in item.get("title", "").lower() or q in item.get("id", "").lower()]


def get_vod_info(target: str) -> Dict[str, Any]:
    target = (target or "").strip()
    if is_url(target):
        return {"id": target, "title": target, "url": target}
    for item in load_vod_catalog():
        if target.lower() in {item.get("id", "").lower(), item.get("title", "").lower()}:
            return item
    try:
        payload = api_request("vod_detail", {"target": target}, require_auth=True)
        if isinstance(payload, dict):
            return payload
        return {"id": target, "payload": payload}
    except Exception as exc:
        return {"id": target, "title": target, "url": "", "found": False, "message": str(exc)}


def get_epg(channel: str) -> List[Dict[str, Any]]:
    channel = (channel or "").strip()
    try:
        return as_list_payload(api_request("epg", {"channel": channel}, require_auth=True))
    except Exception:
        path = first_existing(EPG_CATALOG_FILES)
        if not path:
            return []
        payload = read_json_file(path)
        if isinstance(payload, dict) and isinstance(payload.get("channels"), dict):
            return payload["channels"].get(channel, [])
        if isinstance(payload, dict):
            return payload.get(channel, [])
        return []


def resolve_media_url(target: str, kind: str) -> str:
    if is_direct_media_url(target):
        return target
    try:
        payload = api_request("resolve", {"target": target, "kind": kind}, require_auth=True)
        url = find_first_media_url(payload)
        if url:
            return url
    except Exception:
        pass
    if kind == "vod":
        info = get_vod_info(target)
        url = find_first_media_url(info)
        if url:
            return url
    raise EonSafeError(f"Could not resolve a media URL for {kind}: {target}")


def resolve_stream_info(target: str, kind: str) -> Dict[str, Any]:
    """Resolve target to stream info including mpd_url, license_url, drm_headers."""
    result = {"mpd_url": "", "license_url": "", "drm_headers": {}, "title": target}

    if is_direct_media_url(target):
        result["mpd_url"] = target
        return result

    try:
        payload = api_request("resolve", {"target": target, "kind": kind}, require_auth=True)
        url = find_first_media_url(payload)
        if url:
            result["mpd_url"] = url
        result["license_url"] = find_license_url_in_payload(payload)
        result["drm_headers"] = find_drm_headers_in_payload(payload)
        if isinstance(payload, dict):
            result["title"] = str(payload.get("title") or payload.get("name") or target)
        return result
    except Exception:
        pass

    if kind == "vod":
        info = get_vod_info(target)
        url = find_first_media_url(info)
        if url:
            result["mpd_url"] = url
        result["license_url"] = find_license_url_in_payload(info)
        result["drm_headers"] = find_drm_headers_in_payload(info)
        if isinstance(info, dict):
            result["title"] = str(info.get("title") or info.get("name") or target)

    return result


def parse_episode_selection(selection: str, total: int) -> List[int]:
    if not selection:
        return list(range(1, total + 1))
    selected = set()
    for part in selection.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            start = int(left) if left.strip() else 1
            end = int(right) if right.strip() else total
            for number in range(max(1, start), min(total, end) + 1):
                selected.add(number)
        else:
            number = int(part)
            if 1 <= number <= total:
                selected.add(number)
    return sorted(selected)


def fetch_text(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 EONDownloader/2.0"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text


def ensure_output_dir(path: str) -> Path:
    out = Path(path or "output")
    out.mkdir(parents=True, exist_ok=True)
    return out.resolve()


# ---------------------------------------------------------------------------
# DRM Download Pipeline
# ---------------------------------------------------------------------------

class EONDownloader:
    """Full download pipeline with Widevine DRM support."""

    def __init__(
        self,
        output_dir: str = "output",
        temp_dir: str = "temp",
        device_path: Optional[str] = None,
        workers: int = 16,
    ):
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        # Prefer centralized DRM manager (shared singleton with key caching)
        if _USE_CENTRAL_DRM and _drm_manager and _drm_manager.is_ready():
            self.cdm = _drm_manager
            logger.info("[EONDownloader] Using centralized DRM manager (key caching enabled)")
        else:
            self.cdm = WidevineCDM(device_path)
            logger.info("[EONDownloader] Using standalone WidevineCDM")
        self.bins = detect_binaries()
        self.workers = workers

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_decryption_keys(
        self,
        mpd_url: str,
        license_url: str,
        drm_headers: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """Fetch MPD, extract all PSSHs, get Widevine decryption keys via DRM Manager."""
        logger.info(f"Fetching MPD: {mpd_url}")
        mpd_text = fetch_text(mpd_url)

        # Log stream quality
        streams = get_best_streams(mpd_text)
        if streams:
            vbr = streams.get("video_bitrate", 0)
            abr = streams.get("audio_bitrate", 0)
            logger.info(f"Best streams — video: {vbr // 1000}kbps, audio: {abr // 1000}kbps")

        # If no license URL provided, try to extract from MPD
        if not license_url:
            license_url = extract_license_url_from_mpd(mpd_text) or ""
        if not license_url:
            raise EonSafeError(
                "No license URL available. Provide --license-url or configure the API to return it."
            )

        # License request headers
        lic_headers = {
            "Content-Type": "application/octet-stream",
            "User-Agent": "Mozilla/5.0 EONDownloader/2.0",
        }
        if drm_headers:
            lic_headers.update(drm_headers)

        # Use multi-PSSH via centralized DRM Manager (with key caching)
        if _USE_CENTRAL_DRM and _drm_manager and hasattr(_drm_manager, 'extract_all_pssh_from_mpd'):
            pssh_list = _drm_manager.extract_all_pssh_from_mpd(mpd_text)
            if not pssh_list:
                raise EonSafeError("Could not find Widevine PSSH in MPD manifest")
            logger.info(f"Found {len(pssh_list)} PSSH(s). Fetching keys from: {license_url}")
            keys = _drm_manager.get_keys_multi_pssh(pssh_list, license_url, lic_headers, "eon")
        else:
            pssh = extract_pssh_from_mpd(mpd_text)
            if not pssh:
                raise EonSafeError("Could not find Widevine PSSH in MPD manifest")
            logger.info(f"PSSH: {pssh[:40]}...")
            logger.info(f"Fetching decryption keys from: {license_url}")
            keys = self.cdm.get_keys(pssh, license_url, lic_headers)

        if not keys:
            raise EonSafeError("No CONTENT keys returned from license server")
        for k in keys:
            logger.info(f"  Key: {k}")
        return keys

    def download_fragments(self, mpd_url: str, output_name: str,
                           workers: int = 16) -> Tuple[Path, Path]:
        """
        Download encrypted audio and video fragments via yt-dlp.
        Uses concurrent fragment downloads for speed.
        Returns (video_path, audio_path).
        """
        from yt_dlp import YoutubeDL

        video_out = self.temp_dir / f"{output_name}_enc_video.mp4"
        audio_out = self.temp_dir / f"{output_name}_enc_audio.mp4"
        video_out.unlink(missing_ok=True)
        audio_out.unlink(missing_ok=True)

        aria2c = self.bins.get("aria2c")
        use_aria2c = aria2c and (shutil.which(aria2c) or Path(aria2c).exists())

        def _progress(d):
            raise_if_cancelled()
            if d.get("status") == "downloading":
                fname = d.get("filename", "")
                track = "Video" if "video" in fname.lower() else "Audio"
                done = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                speed = d.get("speed") or 0
                eta = d.get("eta") or 0
                fi = d.get("fragment_index")
                fc = d.get("fragment_count")
                spd_str = f"{speed / 1024 / 1024:.1f}MB/s" if speed else "??MB/s"
                eta_str = f"ETA {eta}s" if eta else ""
                if total:
                    pct = done / total * 100
                    filled = int(20 * done / total)
                    bar = "█" * filled + "░" * (20 - filled)
                    size = f"{total / 1024 / 1024:.1f}MB"
                    frag = f" frag {fi}/{fc}" if fi else ""
                    line = f"  {track} [{bar}] {pct:5.1f}% of {size}  {spd_str}  {eta_str}{frag}"
                elif fi:
                    line = f"  {track} frag {fi}/{fc or '?'}  {spd_str}  {eta_str}"
                else:
                    line = f"  {track} {done // 1024}KB  {spd_str}"
                print(f"\r{line:<70}", end="", flush=True)
            elif d.get("status") == "finished":
                fname = d.get("filename", "")
                track = "Video" if "video" in fname.lower() else "Audio"
                size = (d.get("total_bytes") or d.get("downloaded_bytes", 0)) / 1024 / 1024
                print(f"\r  {track} ✓  {size:.1f}MB" + " " * 40)

        ydl_opts = {
            "allow_unplayable_formats": True,
            "outtmpl": str(self.temp_dir / f"{output_name}_enc.%(ext)s"),
            "format": "bestvideo+bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "updatetime": False,
            "continuedl": False,
            "fixup": "never",
            "merge_output_format": None,
            "postprocessors": [],
            "progress_hooks": [_progress],
            "concurrent_fragment_downloads": workers,
        }

        if use_aria2c:
            ydl_opts["external_downloader"] = {"default": aria2c}
            ydl_opts["external_downloader_args"] = {
                "default": [
                    "--max-connection-per-server=16",
                    "--split=16",
                    "--min-split-size=1M",
                    "--console-log-level=warn",
                ]
            }
            logger.info(f"Using aria2c with {workers} concurrent fragments")
        else:
            logger.info(f"Using yt-dlp with {workers} concurrent fragments")

        logger.info(f"Downloading encrypted fragments from: {mpd_url}")
        download_started = time.time()
        with YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(mpd_url, download=True)

        def _fresh(paths: Iterable[Path]) -> List[Path]:
            return [p for p in paths if p.stat().st_mtime >= download_started - 1]

        # yt-dlp writes separate files for video and audio
        v_candidates = _fresh(
            list(self.temp_dir.glob(f"{output_name}_enc.f*.mp4")) +
            list(self.temp_dir.glob(f"{output_name}_enc.mp4"))
        )
        a_candidates = _fresh(
            list(self.temp_dir.glob(f"{output_name}_enc.f*.m4a")) +
            list(self.temp_dir.glob(f"{output_name}_enc.m4a")) +
            list(self.temp_dir.glob(f"{output_name}_enc.f*.mp4"))
        )

        # Filter duplicates
        v_candidates = [p for p in v_candidates if p != video_out]
        a_candidates = [p for p in a_candidates if p != audio_out and p != video_out]

        if not v_candidates and not a_candidates:
            merged = _fresh(list(self.temp_dir.glob(f"{output_name}_enc.*")))
            if merged:
                logger.warning("yt-dlp produced a single merged file. Will attempt decryption.")
                return merged[0], merged[0]
            raise FileNotFoundError("yt-dlp produced no output files")

        selected_video = None
        if v_candidates:
            v_candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
            selected_video = v_candidates[0]
            shutil.copy2(selected_video, video_out)
        if a_candidates:
            if selected_video:
                a_candidates = [p for p in a_candidates if p.resolve() != selected_video.resolve()]
            if not a_candidates:
                raise FileNotFoundError("yt-dlp produced no separate audio fragment")
            a_candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
            shutil.copy2(a_candidates[0], audio_out)
        if not video_out.exists():
            raise FileNotFoundError("yt-dlp produced no separate video fragment")
        if not audio_out.exists():
            raise FileNotFoundError("yt-dlp produced no separate audio fragment")

        logger.info(f"Video fragment: {video_out} ({video_out.stat().st_size // 1024}KB)")
        logger.info(f"Audio fragment: {audio_out} ({audio_out.stat().st_size // 1024}KB)")

        return video_out, audio_out

    def decrypt_file(self, encrypted: Path, keys: List[str]) -> Path:
        """Decrypt a single file with mp4decrypt."""
        decrypted = encrypted.with_name(encrypted.stem.replace("_enc", "_dec") + encrypted.suffix)
        cmd = [self.bins["mp4decrypt"]]
        for key in keys:
            cmd += ["--key", key]
        cmd += [str(encrypted), str(decrypted)]

        logger.info(f"Decrypting: {encrypted.name} -> {decrypted.name}")
        result = run_subprocess(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise EonSafeError(f"mp4decrypt failed: {result.stderr}")
        logger.info(f"Decrypted: {decrypted.name} ({decrypted.stat().st_size // 1024}KB)")
        return decrypted

    def fix_with_ffmpeg(self, input_path: Path) -> Path:
        """Re-mux a fragment through ffmpeg to fix timing / codec boxes."""
        fixed = input_path.with_name(input_path.stem + "_fixed.mp4")
        cmd = [
            self.bins["ffmpeg"], "-y",
            "-i", str(input_path),
            "-c", "copy",
            str(fixed),
        ]
        result = run_subprocess(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"ffmpeg fix failed (non-fatal): {result.stderr[-300:]}")
            return input_path
        return fixed

    def mux_output(self, video_path: Path, audio_path: Path, output_path: Path) -> Path:
        """Mux video and audio with mkvmerge, fallback to ffmpeg."""
        mkvmerge = self.bins.get("mkvmerge")
        ffmpeg = self.bins.get("ffmpeg")

        # Try mkvmerge first
        if mkvmerge and (shutil.which(mkvmerge) or Path(mkvmerge).exists()):
            temp_output = temporary_media_path(output_path)
            cmd = [
                mkvmerge,
                "-o", str(temp_output),
                str(video_path),
                str(audio_path),
            ]
            logger.info(f"Muxing with mkvmerge to: {output_path}")
            result = run_subprocess(cmd, capture_output=True, text=True)
            if result.returncode in (0, 1):
                promote_validated_media(temp_output, output_path, mkvmerge_path=mkvmerge)
                logger.info(f"Output: {output_path} ({output_path.stat().st_size // 1024 // 1024}MB)")
                return output_path
            temp_output.unlink(missing_ok=True)
            logger.warning(f"mkvmerge failed (code {result.returncode}), trying ffmpeg...")

        # Fallback to ffmpeg
        if ffmpeg and (shutil.which(ffmpeg) or Path(ffmpeg).exists()):
            output_mp4 = output_path.with_suffix(".mp4")
            temp_output = temporary_media_path(output_mp4)
            cmd = [
                ffmpeg, "-y",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-c", "copy",
                "-async", "1",
                "-vsync", "-1",
                "-fflags", "+genpts+igndts",
                "-movflags", "+faststart",
                str(temp_output),
            ]
            logger.info(f"Muxing with ffmpeg to: {output_mp4}")
            result = run_subprocess(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                promote_validated_media(temp_output, output_mp4)
                logger.info(f"Output: {output_mp4} ({output_mp4.stat().st_size // 1024 // 1024}MB)")
                return output_mp4
            temp_output.unlink(missing_ok=True)
            raise EonSafeError(f"ffmpeg mux failed: {result.stderr[-500:]}")

        raise EonSafeError("Neither mkvmerge nor ffmpeg found for muxing")

    def cleanup(self, name: str):
        """Remove temp files for a given download name."""
        for pattern in [f"{name}_enc*", f"{name}_dec*", f"{name}_fixed*"]:
            for f in self.temp_dir.glob(pattern):
                try:
                    f.unlink()
                except Exception:
                    pass

    def download(
        self,
        mpd_url: str,
        license_url: str = "",
        drm_headers: Optional[Dict[str, str]] = None,
        title: str = "EON.Video",
        workers: int = 16,
    ) -> Path:
        """
        Full DRM download pipeline:
        1. Fetch MPD, extract PSSH
        2. License exchange to get content keys
        3. Download encrypted fragments via yt-dlp
        4. Decrypt with mp4decrypt
        5. Fix with ffmpeg if needed
        6. Mux with mkvmerge/ffmpeg
        """
        safe_name = safe_filename(title)
        logger.info(f"=== EON DRM Download: {title} ===")
        logger.info(f"MPD: {mpd_url}")
        print(f"\n[EON] Starting download: {title}")
        print(f"[EON] MPD: {mpd_url}")

        # Step 1: Check if DRM is present
        mpd_text = fetch_text(mpd_url)
        drm_present = is_drm_protected(mpd_text)

        if not drm_present:
            # Non-DRM stream: just download with yt-dlp directly
            print("[EON] Stream is not DRM-protected, downloading directly...")
            return self._download_direct(mpd_url, safe_name, workers)

        print("[EON] Widevine DRM detected, starting decryption pipeline...")

        # Step 2: Extract PSSH and get keys
        keys = self.get_decryption_keys(mpd_url, license_url, drm_headers)
        print(f"[EON] Got {len(keys)} decryption key(s)")

        # Step 3: Download encrypted fragments
        print("[EON] Downloading encrypted fragments...")
        enc_video, enc_audio = self.download_fragments(mpd_url, safe_name, workers)

        # Step 4: Decrypt
        print("[EON] Decrypting video...")
        dec_video = self.decrypt_file(enc_video, keys)
        dec_audio = dec_video  # default if same file
        if enc_audio != enc_video and enc_audio.exists():
            print("[EON] Decrypting audio...")
            dec_audio = self.decrypt_file(enc_audio, keys)

        # Step 5: Fix with ffmpeg if needed
        dec_video = self.fix_with_ffmpeg(dec_video)
        if dec_audio != dec_video:
            dec_audio = self.fix_with_ffmpeg(dec_audio)

        # Step 6: Mux
        output_path = self.output_dir / f"{safe_name}.mkv"
        print("[EON] Muxing final output...")
        result = self.mux_output(dec_video, dec_audio, output_path)

        # Step 7: Cleanup
        self.cleanup(safe_name)

        print(f"\n[EON] ✓ Download complete: {result}")
        print(f"[EON] ✓ Size: {result.stat().st_size / 1024 / 1024:.1f} MB")
        return result

    def _download_direct(self, url: str, safe_name: str, workers: int) -> Path:
        """Download a non-DRM stream directly with yt-dlp."""
        from yt_dlp import YoutubeDL

        temp_prefix = f"{safe_name}.{uuid.uuid4().hex}.tmp"
        output_template = str(self.output_dir / f"{temp_prefix}.%(ext)s")
        def _progress(_data):
            raise_if_cancelled()

        ydl_opts = {
            "outtmpl": output_template,
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mkv",
            "concurrent_fragment_downloads": workers,
            "retries": 10,
            "fragment_retries": 10,
            "updatetime": False,
            "progress_hooks": [_progress],
        }
        download_started = time.time()
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find output file
        for ext in ("mkv", "mp4", "webm", "ts"):
            temp_out = self.output_dir / f"{temp_prefix}.{ext}"
            if temp_out.exists() and temp_out.stat().st_mtime >= download_started - 1:
                out = self.output_dir / f"{safe_name}.{ext}"
                promote_validated_media(temp_out, out, probe=ext != "ts")
                return out
        raise FileNotFoundError("yt-dlp produced no direct output file")

    def download_live(
        self,
        mpd_url: str,
        license_url: str = "",
        drm_headers: Optional[Dict[str, str]] = None,
        title: str = "EON.Live",
        duration: int = 60,
        player: str = "",
        play: bool = False,
    ) -> Path:
        """Download/record a live stream with optional DRM decryption."""
        safe_name = safe_filename(title)
        logger.info(f"=== EON Live Capture: {title} ===")
        print(f"\n[EON] Starting live capture: {title}")
        print(f"[EON] Duration: {duration}s")

        if play and player:
            subprocess.Popen([player, mpd_url])
        elif play:
            print(f"[EON] Stream URL for playback: {mpd_url}")

        # Check if DRM
        mpd_text = fetch_text(mpd_url)
        drm_present = is_drm_protected(mpd_text)

        if not drm_present:
            # Non-DRM: use ffmpeg directly
            ffmpeg = self.bins.get("ffmpeg")
            if not ffmpeg:
                raise EonSafeError("ffmpeg is required for live capture")
            output_file = self.output_dir / f"{safe_name}.ts"
            temp_output = temporary_media_path(output_file)
            cmd = [ffmpeg, "-hide_banner", "-loglevel", "info", "-y",
                   "-reconnect", "1", "-reconnect_streamed", "1"]
            if duration > 0:
                cmd += ["-t", str(duration)]
            cmd += ["-i", mpd_url, "-c", "copy", "-async", "1", "-vsync", "-1", "-fflags", "+genpts+igndts", str(temp_output)]
            print("[EON] Recording non-DRM live stream with ffmpeg...")
            result = run_subprocess(cmd)
            if result.returncode != 0:
                temp_output.unlink(missing_ok=True)
                raise EonSafeError("ffmpeg live capture failed")
            promote_validated_media(temp_output, output_file, min_bytes=1024, probe=False)
            print(f"[EON] ✓ Live capture saved: {output_file}")
            return output_file

        # DRM live: get keys, download, decrypt, mux
        print("[EON] Widevine DRM detected on live stream...")
        keys = self.get_decryption_keys(mpd_url, license_url, drm_headers)
        print(f"[EON] Got {len(keys)} decryption key(s)")

        # For live, use ffmpeg to capture limited duration of encrypted stream
        enc_output = self.temp_dir / f"{safe_name}_enc_live.mp4"
        ffmpeg = self.bins.get("ffmpeg")
        if not ffmpeg:
            raise EonSafeError("ffmpeg is required for DRM live capture")

        cmd = [ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
               "-reconnect", "1", "-reconnect_streamed", "1"]
        if duration > 0:
            cmd += ["-t", str(duration)]
        cmd += ["-i", mpd_url, "-c", "copy", "-async", "1", "-vsync", "-1", "-fflags", "+genpts+igndts", str(enc_output)]
        try:
            print(f"[EON] Capturing encrypted live stream ({duration}s)...")
            run_subprocess(cmd)
        except KeyboardInterrupt:
            print("\n[EON] Snimanje prekinuto od strane korisnika. Pokušavam dešifrovati do sada snimljeni deo...")

        if not enc_output.exists() or enc_output.stat().st_size < 1024:
            raise EonSafeError("Nema snimljenog materijala ili je snimak premali.")

        # Decrypt
        print("[EON] Decrypting captured stream...")
        dec_output = self.decrypt_file(enc_output, keys)

        # Fix and rename
        fixed = self.fix_with_ffmpeg(dec_output)
        final = self.output_dir / f"{safe_name}.mp4"
        promote_validated_media(fixed, final, min_bytes=1024, probe=False)

        self.cleanup(safe_name)
        print(f"[EON] ✓ Live capture complete: {final}")
        return final


# ---------------------------------------------------------------------------
# Non-DRM fallback download (for when no keys are needed)
# ---------------------------------------------------------------------------

def run_yt_dlp(
    url: str,
    output_dir: Path,
    title: str,
    verbose: bool = False,
    quality: str = "best",
    subs: str = "",
) -> int:
    """Download a direct media URL using yt-dlp (non-DRM path)."""
    output_template = str(output_dir / f"{safe_filename(title)}.%(ext)s")
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--continue",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--restrict-filenames",
        "-f",
        quality or "best",
        "-o",
        output_template,
        url,
    ]
    if subs:
        cmd[3:3] = ["--write-subs", "--write-auto-subs", "--sub-langs", subs]
    if verbose:
        cmd.insert(-1, "--verbose")
    print("[EON] Downloading with yt-dlp")
    return run_subprocess(cmd).returncode


def run_live_capture(url: str, output_dir: Path, title: str, duration: int, player: str = "", play: bool = False) -> int:
    """Capture a direct non-DRM live stream with ffmpeg."""
    if play:
        if player:
            subprocess.Popen([player, url])
        else:
            print("[EON] --play requested without --player; stream URL:")
            print(url)

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise EonSafeError("ffmpeg is required for live capture.")

    output_file = output_dir / f"{safe_filename(title)}.ts"
    temp_output = temporary_media_path(output_file)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "info", "-y", "-reconnect", "1", "-reconnect_streamed", "1"]
    if duration > 0:
        cmd += ["-t", str(duration)]
    cmd += ["-i", url, "-c", "copy", str(temp_output)]
    try:
        print("[EON] Capturing live stream with ffmpeg")
        result = run_subprocess(cmd)
        if result.returncode == 0:
            promote_validated_media(temp_output, output_file, min_bytes=1024, probe=False)
        else:
            temp_output.unlink(missing_ok=True)
        return result.returncode
    except KeyboardInterrupt:
        print("\n[EON] Snimanje uživo prekinuto od strane korisnika.")
        if temp_output.exists() and temp_output.stat().st_size >= 1024:
            promote_validated_media(temp_output, output_file, min_bytes=1024, probe=False)
            return 0
        temp_output.unlink(missing_ok=True)
        return 1


# ---------------------------------------------------------------------------
# Health / Status
# ---------------------------------------------------------------------------

def build_health() -> Dict[str, Any]:
    channels = load_channels()
    series_catalog = load_series_catalog()
    vod_catalog = load_vod_catalog()

    # Check CDM availability
    cdm_ready = False
    try:
        cdm = WidevineCDM()
        cdm_ready = cdm.is_ready()
    except Exception:
        pass

    # Check binaries
    bins = detect_binaries()
    bins_status = {}
    for name, path in bins.items():
        found = bool(shutil.which(path) or Path(path).exists())
        bins_status[name] = {"found": found, "path": path}

    return {
        "name": "EON DRM Downloader Engine",
        "download_supported": True,
        "message": SAFE_MESSAGE,
        "device": device_profile_status(),
        "token": token_status(),
        "api": api_status(),
        "cdm_ready": cdm_ready,
        "binaries": bins_status,
        "catalog": {
            "channels": len(channels),
            "series": len(series_catalog),
            "vod": len(vod_catalog),
            "channel_files": [str(path) for path in CHANNEL_CATALOG_FILES],
            "series_files": [str(path) for path in SERIES_CATALOG_FILES],
            "vod_files": [str(path) for path in VOD_CATALOG_FILES],
            "epg_files": [str(path) for path in EPG_CATALOG_FILES],
        },
        "capabilities": {
            "save_device": True,
            "api_login": True,
            "api_refresh": True,
            "api_status": True,
            "list_channels": True,
            "epg": True,
            "search": True,
            "vod_info": True,
            "live": True,
            "vod": True,
            "series": True,
            "drm_decryption": cdm_ready,
            "direct_non_drm": True,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="EON TV Video Downloader with Widevine DRM support.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Save device credentials
  python eon_downloader.py -u user@email.com -p Password --device-serial SERIAL --device-number NUMBER --save-device

  # Health check
  python eon_downloader.py --health

  # Download DRM-protected VOD
  python eon_downloader.py --vod "https://example.com/manifest.mpd" --license-url "https://lic.example.com/wv"

  # Download VOD from catalog/API
  python eon_downloader.py --vod "12345" -v

  # Live stream capture (DRM or non-DRM)
  python eon_downloader.py --live -c "RTS 1" --duration 120

  # Series download
  python eon_downloader.py --series "12345" --episodes "1-5"

  # List channels
  python eon_downloader.py --list-channels

  # Search
  python eon_downloader.py --search "movie name" --json
""",
    )
    # Account / device
    parser.add_argument("-u", "--username", help="EON username / email")
    parser.add_argument("-p", "--password", help="EON password")
    parser.add_argument("--device-serial", help="EON device serial")
    parser.add_argument("--device-number", help="EON device number")
    parser.add_argument("--save-device", action="store_true", help="Save local EON device metadata")

    # Info / status
    parser.add_argument("--health", action="store_true", help="Print JSON health/capability status")
    parser.add_argument("--api-status", action="store_true", help="Print configured EON API endpoint/token status")
    parser.add_argument("--login-api", action="store_true", help="Run configured API login endpoint")
    parser.add_argument("--refresh-token", action="store_true", help="Run configured refresh endpoint")
    parser.add_argument("--list-channels", action="store_true", help="List channels")
    parser.add_argument("--epg", help="Print EPG entries for a channel")
    parser.add_argument("--search", help="Search VOD catalog/API")
    parser.add_argument("--vod-info", help="Print VOD metadata")
    parser.add_argument("--resolve-stream", help="Resolve EON stream (channel name or VOD ID) and output JSON")
    parser.add_argument("--kind", default="live", help="Kind of target to resolve: live or vod")

    # Download modes
    parser.add_argument("--live", action="store_true", help="Live stream capture")
    parser.add_argument("-c", "--channel", help="Live channel name or direct URL")
    parser.add_argument("--duration", type=int, default=60, help="Live recording duration in seconds (0=until stopped)")
    parser.add_argument("--play", action="store_true", help="Open stream in player while recording")
    parser.add_argument("--player", help="Player executable path")
    parser.add_argument("--vod", help="VOD target (URL, ID, or MPD link)")
    parser.add_argument("--series", help="Series ID")
    parser.add_argument("--list-episodes", action="store_true", help="List series episodes")
    parser.add_argument("--episodes", help="Episode range, e.g. 1-3, 2-, -5, 4")

    # DRM options
    parser.add_argument("--license-url", help="Widevine DRM license server URL")
    parser.add_argument("--device-wvd", help="Path to .wvd CDM device file")

    # Output options
    parser.add_argument("--quality", default="best", help="yt-dlp format selector")
    parser.add_argument("--subs", default="", help="Subtitle languages, e.g. sr,hr,en or all")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("-o", "--output", default="output", help="Output directory")
    parser.add_argument("-t", "--title", help="Override output filename")
    parser.add_argument("-w", "--workers", type=int, default=16, help="Concurrent fragment downloads")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def extract_id_from_url(target: str) -> str:
    if not target:
        return ""
    target = target.strip()
    # Matches /ondemand/detail/12345 or /series/detail/162073-s1 or similar
    match = re.search(r"/(?:ondemand|series)/detail/([^/?#]+)", target)
    if match:
        return match.group(1)
    return target


def handle_save_device(args: argparse.Namespace) -> int:
    try:
        profile = save_device_profile(
            username=args.username or "",
            serial=args.device_serial or "",
            number=args.device_number or "",
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"EON device metadata saved for {profile['username']}.")

    # Automatically trigger API login if password is provided
    if args.password:
        print("Performing API login with provided credentials...")
        try:
            res = login_api(
                username=args.username or "",
                password=args.password,
                serial=args.device_serial or "",
                number=args.device_number or "",
            )
            if res.get("tokens_saved"):
                print("API login successful, tokens saved.")
            else:
                print("API login executed, but no tokens were extracted.", file=sys.stderr)
        except Exception as exc:
            print(f"API login failed: {exc}", file=sys.stderr)
            return 1
    return 0



def handle_list_channels(as_json: bool = False) -> int:
    channels = load_channels()
    if as_json:
        print(json.dumps(channels, indent=2, ensure_ascii=False))
        return 0
    if not channels:
        print("No channels found.")
        return 0
    for channel in channels:
        print(channel["name"])
    return 0


def print_payload(payload: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                label = item.get("title") or item.get("name") or item.get("id") or json.dumps(item, ensure_ascii=False)
                extra = item.get("id") or item.get("start") or item.get("url") or ""
                print(f"{label}" + (f" [{extra}]" if extra else ""))
            else:
                print(item)
    elif isinstance(payload, dict):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload)


def resolve_live_url(channel_or_url: str) -> str:
    if is_url(channel_or_url):
        return channel_or_url
    channel = find_channel(channel_or_url)
    if channel and channel.get("url"):
        return channel["url"]
    resolved = resolve_media_url(channel_or_url, "live")
    if resolved:
        return resolved
    if not channel:
        raise EonSafeError(f"Channel not found in local catalog: {channel_or_url}")
    raise EonSafeError(f"Channel has no URL in local catalog: {channel_or_url}")


def handle_vod_download(args: argparse.Namespace) -> int:
    """Handle VOD download with full DRM support."""
    target = extract_id_from_url(args.vod)
    output_dir = ensure_output_dir(args.output)

    # Try to resolve stream info from API
    stream_info = resolve_stream_info(target, "vod")
    mpd_url = stream_info.get("mpd_url") or target
    license_url = args.license_url or stream_info.get("license_url", "")
    drm_headers = stream_info.get("drm_headers", {})
    title = args.title or stream_info.get("title") or target

    if not is_url(mpd_url):
        raise EonSafeError(f"Could not resolve media URL for: {target}")

    # Check if the URL is an MPD with DRM
    try:
        mpd_text = fetch_text(mpd_url)
        has_drm = is_drm_protected(mpd_text)
    except Exception:
        has_drm = False

    if has_drm and license_url:
        # Full DRM pipeline
        downloader = EONDownloader(
            output_dir=str(output_dir),
            temp_dir=str(output_dir / "temp"),
            device_path=args.device_wvd,
            workers=args.workers,
        )
        downloader.download(
            mpd_url=mpd_url,
            license_url=license_url,
            drm_headers=drm_headers,
            title=title,
            workers=args.workers,
        )
        return 0
    elif has_drm and not license_url:
        # DRM detected but no license URL - try to extract from MPD
        extracted_lic = extract_license_url_from_mpd(mpd_text)
        if extracted_lic:
            downloader = EONDownloader(
                output_dir=str(output_dir),
                temp_dir=str(output_dir / "temp"),
                device_path=args.device_wvd,
                workers=args.workers,
            )
            downloader.download(
                mpd_url=mpd_url,
                license_url=extracted_lic,
                drm_headers=drm_headers,
                title=title,
                workers=args.workers,
            )
            return 0
        else:
            print("[EON] DRM detected but no license URL found.", file=sys.stderr)
            print("[EON] Use --license-url to provide the Widevine license server URL.", file=sys.stderr)
            return 2
    else:
        # Non-DRM: simple download
        return run_yt_dlp(mpd_url, output_dir, title, args.verbose, args.quality, args.subs)


def handle_live_download(args: argparse.Namespace) -> int:
    """Handle live stream capture with DRM support."""
    if not args.channel:
        raise EonSafeError("--live requires -c/--channel")

    output_dir = ensure_output_dir(args.output)
    live_url = resolve_live_url(args.channel)
    title = args.title or args.channel
    license_url = args.license_url or ""

    # Check if DRM
    try:
        mpd_text = fetch_text(live_url)
        has_drm = is_drm_protected(mpd_text)
    except Exception:
        has_drm = False

    if has_drm:
        # Try to get license URL from API or MPD
        if not license_url:
            stream_info = resolve_stream_info(args.channel, "live")
            license_url = stream_info.get("license_url", "")
        if not license_url:
            license_url = extract_license_url_from_mpd(mpd_text) or ""

        if license_url:
            downloader = EONDownloader(
                output_dir=str(output_dir),
                temp_dir=str(output_dir / "temp"),
                device_path=args.device_wvd,
                workers=args.workers,
            )
            downloader.download_live(
                mpd_url=live_url,
                license_url=license_url,
                title=title,
                duration=args.duration,
                player=args.player or "",
                play=args.play,
            )
            return 0
        else:
            print("[EON] DRM detected but no license URL found.", file=sys.stderr)
            print("[EON] Use --license-url to provide the Widevine license server URL.", file=sys.stderr)
            return 2
    else:
        return run_live_capture(live_url, output_dir, title, args.duration, args.player or "", args.play)


def handle_series(args: argparse.Namespace) -> int:
    """Handle series download with DRM support."""
    series_id = extract_id_from_url(args.series or "")
    episodes = load_series_episodes(series_id)
    if not episodes:
        print(f"Series not found in configured API/local catalog: {args.series}", file=sys.stderr)
        return 1

    if args.list_episodes:
        if args.json:
            print(json.dumps(episodes, indent=2, ensure_ascii=False))
            return 0
        for index, episode in enumerate(episodes, start=1):
            print(f"{index}. {episode['title']}")
        return 0

    output_dir = ensure_output_dir(args.output)
    selected = parse_episode_selection(args.episodes or "", len(episodes))
    if not selected:
        print("No episodes selected.", file=sys.stderr)
        return 1

    license_url = args.license_url or ""
    final_code = 0

    for number in selected:
        episode = episodes[number - 1]
        title = args.title or f"{args.series}.E{number:02d}.{episode['title']}"
        ep_url = episode.get("url", "")

        if not ep_url:
            print(f"[EON] Episode {number} has no URL, skipping", file=sys.stderr)
            final_code = 1
            continue

        # Check DRM
        try:
            mpd_text = fetch_text(ep_url)
            has_drm = is_drm_protected(mpd_text)
        except Exception:
            has_drm = False

        if has_drm:
            ep_license = license_url
            if not ep_license:
                ep_license = extract_license_url_from_mpd(mpd_text) or ""
            if not ep_license:
                stream_info = resolve_stream_info(episode.get("id", ""), "vod")
                ep_license = stream_info.get("license_url", "")

            if ep_license:
                try:
                    downloader = EONDownloader(
                        output_dir=str(output_dir),
                        temp_dir=str(output_dir / "temp"),
                        device_path=args.device_wvd,
                        workers=args.workers,
                    )
                    downloader.download(
                        mpd_url=ep_url,
                        license_url=ep_license,
                        title=title,
                        workers=args.workers,
                    )
                except Exception as exc:
                    print(f"[EON] Episode {number} failed: {exc}", file=sys.stderr)
                    final_code = 1
            else:
                print(f"[EON] Episode {number} is DRM-protected but no license URL found.", file=sys.stderr)
                final_code = 2
        else:
            code = run_yt_dlp(ep_url, output_dir, title, args.verbose, args.quality, args.subs)
            if code != 0:
                final_code = code

    return final_code


def main() -> int:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        if args.health:
            print(json.dumps(build_health(), indent=2, ensure_ascii=False))
            return 0

        if args.api_status:
            print(json.dumps(api_status(), indent=2, ensure_ascii=False))
            return 0

        if args.save_device:
            return handle_save_device(args)

        if args.login_api:
            if not args.username or not args.password or not args.device_serial or not args.device_number:
                raise EonSafeError("--login-api requires -u, -p, --device-serial and --device-number")
            print(json.dumps(login_api(args.username, args.password, args.device_serial, args.device_number), indent=2, ensure_ascii=False))
            return 0

        if args.refresh_token:
            print(json.dumps(refresh_api_token(), indent=2, ensure_ascii=False))
            return 0

        if args.list_channels:
            return handle_list_channels(args.json)

        if args.search:
            print_payload(search_vod(args.search), args.json)
            return 0

        if args.epg:
            print_payload(get_epg(args.epg), args.json)
            return 0

        if args.vod_info:
            print_payload(get_vod_info(args.vod_info), True)
            return 0

        if args.resolve_stream:
            print(json.dumps(resolve_stream_info(args.resolve_stream, args.kind), indent=2, ensure_ascii=False))
            return 0

        if args.series:
            return handle_series(args)

        if args.live:
            return handle_live_download(args)

        if args.vod:
            return handle_vod_download(args)

        print(json.dumps(build_health(), indent=2, ensure_ascii=False))
        return 0

    except EonSafeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except requests.RequestException as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 2
    except EonAuthError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        logger.exception("Unexpected error")
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
