#!/usr/bin/env python3
"""
HBO Max (Max) Video Downloader
Handles DRM-protected content via Widevine CDM (L3).

Requirements:
    pip install requests pycryptodome yt-dlp xmltodict pywidevine curl_cffi

Usage:
    # Login first (once):
    python hbomax_downloader.py --login --market emea

    # Download by video ID (last UUID in the watch URL):
    python hbomax_downloader.py -i de4c9160-1b67-4c1e-8cad-e7b0e42c5fdf

    # With subtitle options:
    python hbomax_downloader.py -i <id> --subs all
    python hbomax_downloader.py -i <id> --subs sr,hr,en
    python hbomax_downloader.py -i <id> --subs none
    python hbomax_downloader.py -i <id> --audio all

    # URL directly accepted too:
    python hbomax_downloader.py -i https://play.hbomax.com/video/watch/.../de4c9160-...

Notes:
    - L3 CDM (software): max 720p (height ≤ 720, capped at 580 for safe L3)
    - L1 CDM (hardware): up to 4K (change L3_MAX_HEIGHT to 2160)
    - Token stored at ~/.hbomax/token.json
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
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
import xmltodict

from backend.utils.cancellable_subprocess import (
    current_cancel_event,
    raise_if_cancelled,
    run as run_subprocess,
)
from backend.utils.media_validation import promote_validated_media, temporary_media_path

from .hbomax_auth import HBOMaxAuth, load_token, save_token

try:
    from backend.services.drm_manager import drm_manager as _drm_manager
    _USE_CENTRAL_DRM = True
except ImportError:
    _USE_CENTRAL_DRM = False
    _drm_manager = None

try:
    from curl_cffi import requests as cffi_requests
    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

# For L3 (software) CDM cap height at 720 (some servers enforce 580 for browser L3)
L3_MAX_HEIGHT = 720

API_BASE     = "https://default.any-any.prd.api.max.com/ara"
LICENSE_URL  = "https://widevine.any-any.prd.max.com/widevine/v1/license"

# SlyGuy-compatible app/client details
APP_VERSION  = "3.0.0"
PLATFORM_TAG = "browser"

_DEFAULT_SUBS = "all"
_DEFAULT_AUDIO = "all"
_OUTPUT_DIR   = Path("output")

# ── Widevine CDM wrapper ───────────────────────────────────────────────────────

class WidevineCDM:
    """Thin wrapper around pywidevine for PSSH → decryption key extraction."""

    def __init__(self, device_path: Optional[str] = None):
        self.device_path = device_path
        self.cdm = None
        self.device = None

    def _find_wvd(self) -> Optional[Path]:
        """Auto-discover a .wvd file in common locations."""
        candidates = [
            Path(self.device_path) if self.device_path else None,
            Path.home() / ".wvd" / "device.wvd",
            Path.home() / "device.wvd",
            Path(__file__).parent / "device.wvd",
            Path(__file__).parent / "binaries" / "device.wvd",
        ]
        for p in candidates:
            if p and p.exists():
                return p
        # Search current dir
        for p in Path(".").glob("*.wvd"):
            return p
        return None

    def open(self) -> None:
        from pywidevine.cdm import Cdm
        from pywidevine.device import Device

        wvd_path = self._find_wvd()
        if not wvd_path:
            raise FileNotFoundError(
                "Nije pronađen .wvd CDM fajl.\n"
                "Kopirajte device.wvd u isti folder kao hbomax_downloader.py ili u ~/.wvd/device.wvd"
            )
        logger.info(f"Koristim CDM: {wvd_path}")
        self.device = Device.load(str(wvd_path))
        self.cdm = Cdm.from_device(self.device)

    def get_keys(self, pssh_b64: str, license_url: str, headers: Dict[str, str]) -> List[Dict[str, str]]:
        """Given a PSSH (base64) and a license URL, return decryption keys."""
        from pywidevine.cdm import Cdm
        from pywidevine.pssh import PSSH

        if self.cdm is None:
            self.open()

        pssh = PSSH(pssh_b64)
        session_id = self.cdm.open()
        try:
            challenge = self.cdm.get_license_challenge(session_id, pssh)
            # Send challenge to license server
            resp = requests.post(license_url, data=challenge, headers=headers, timeout=15)
            resp.raise_for_status()
            self.cdm.parse_license(session_id, resp.content)
            keys = []
            for key in self.cdm.get_keys(session_id):
                if key.type == "CONTENT":
                    keys.append({
                        "kid": key.kid.hex,
                        "key": key.key.hex(),
                    })
            return keys
        finally:
            self.cdm.close(session_id)

    def close(self) -> None:
        pass  # Cdm is stateless per session


def _pairs_to_hbo_keys(pairs: List[str]) -> List[Dict[str, str]]:
    keys: List[Dict[str, str]] = []
    for pair in pairs:
        if ":" in pair:
            kid, key = pair.split(":", 1)
            keys.append({"kid": kid, "key": key})
    return keys


class HBOCDMBridge:
    """Delegates to central DRMManager; HBO code expects kid/key dicts."""

    def get_keys(
        self, pssh_b64: str, license_url: str, headers: Dict[str, str]
    ) -> List[Dict[str, str]]:
        if not (_USE_CENTRAL_DRM and _drm_manager and _drm_manager.is_ready()):
            raise RuntimeError("Central CDM not ready")
        pairs = _drm_manager.get_keys(pssh_b64, license_url, headers, "hbomax")
        return _pairs_to_hbo_keys(pairs)

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass


# ── Binary discovery ───────────────────────────────────────────────────────────

def _find_binary(name: str, custom_path: Optional[str] = None) -> Optional[str]:
    """Find an executable in PATH or a local binaries/ subfolder."""
    if custom_path and Path(custom_path).exists():
        return str(Path(custom_path).resolve())
    # Local binaries folder
    local = Path(__file__).parent / "binaries" / (name + (".exe" if platform.system() == "Windows" else ""))
    if local.exists():
        return str(local)
    return shutil.which(name)


def _require_binaries(mp4decrypt_path: Optional[str] = None, mkvmerge_path: Optional[str] = None) -> Dict[str, str]:
    needed = {
        "mp4decrypt": _find_binary("mp4decrypt", mp4decrypt_path),
        "mkvmerge":   _find_binary("mkvmerge", mkvmerge_path),
    }
    missing = [k for k, v in needed.items() if not v]
    if missing:
        raise EnvironmentError(
            f"Nedostaju alati: {', '.join(missing)}\n"
            "Instalirajte Bento4 (mp4decrypt) i MKVToolNix (mkvmerge) i dodajte ih u PATH, "
            "ili kopirajte u binaries/ folder."
        )
    return {k: v for k, v in needed.items()}


# ── Max API client ─────────────────────────────────────────────────────────────

class MaxAPI:
    """HTTP client for the Max/HBO Max API."""

    def __init__(self, auth: HBOMaxAuth):
        self.auth = auth
        if _HAS_CURL_CFFI:
            self._session = cffi_requests.Session(impersonate="chrome124")
        else:
            self._session = requests.Session()
            logger.warning("curl_cffi nije instaliran; neke Max CDN rute mogu biti blokirane.")

    def _headers(self, extra: Optional[Dict] = None) -> Dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.auth.get_access_token()}",
            "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept":        "application/json",
            "Origin":        "https://www.max.com",
            "Referer":       "https://www.max.com/",
        }
        if extra:
            h.update(extra)
        return h

    def get_content(self, video_id: str) -> Dict[str, Any]:
        """Fetch content metadata for a video UUID."""
        url = f"{API_BASE}/v1/content/videos/{video_id}"
        resp = self._session.get(url, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_playback(self, edit_id: str) -> Dict[str, Any]:
        """
        Request playback info (MPD URL + DRM headers) for a given edit/asset ID.
        Uses the Widevine playback endpoint.
        """
        url = f"{API_BASE}/v1/playback/vodAssets/{edit_id}"
        payload = {
            "applicationRuntime": "chrome",
            "deviceInfo": {
                "adSupportedDevice": False,
                "drmSupported": True,
                "hardwareDecodingSupported": False,  # L3 (software)
                "model": "desktop",
                "os": "windows",
                "osVersion": "10",
                "type": "DESKTOP",
                "version": "1.0",
            },
            "drm": {
                "scheme": "WIDEVINE",
                "version": "MODULAR",
            },
            "streamType": "DASH",
        }
        resp = self._session.post(url, json=payload, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_manifest(self, mpd_url: str) -> str:
        """Fetch the MPD manifest text."""
        resp = self._session.get(
            mpd_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Origin":  "https://www.max.com",
                "Referer": "https://www.max.com/",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.text

    def get_license_headers(self, playback_data: Dict[str, Any]) -> Dict[str, str]:
        """Extract/build DRM license request headers from playback data."""
        drm_info = playback_data.get("drm") or playback_data.get("protection") or {}
        custom_data = drm_info.get("customData") or drm_info.get("widevineCustomData") or ""
        headers = {
            "Authorization": f"Bearer {self.auth.get_access_token()}",
            "Content-Type":  "application/octet-stream",
        }
        if custom_data:
            headers["x-dt-custom-data"] = custom_data
        return headers


# ── Language / track helpers ───────────────────────────────────────────────────

_LANG_ISO_MAP = {
    "sr": "srp", "sr-latn": "srp", "sr-cyrl": "srp",
    "hr": "hrv", "mk": "mkd", "bs": "bos",
    "sl": "slv", "en": "eng", "und": "und",
    "de": "deu", "fr": "fra", "es": "spa", "it": "ita",
    "pt": "por", "nl": "nld", "pl": "pol", "cs": "ces",
    "sk": "slk", "hu": "hun", "ro": "ron", "bg": "bul",
    "el": "ell", "tr": "tur", "ru": "rus", "uk": "ukr",
    "ja": "jpn", "ko": "kor", "zh": "zho", "ar": "ara",
}


def _lang_base(lang: str) -> str:
    return (lang or "und").lower().split("-")[0]


def _lang_to_iso639_2(lang: str) -> str:
    low = (lang or "und").lower()
    if low in _LANG_ISO_MAP:
        return _LANG_ISO_MAP[low]
    base = _lang_base(low)
    return _LANG_ISO_MAP.get(base, base[:3] if len(base) >= 3 else "und")


def _adaptation_role(adapt: Dict[str, Any]) -> str:
    roles = adapt.get("Role", [])
    if isinstance(roles, dict):
        roles = [roles]
    for role in roles or []:
        val = (role.get("@value") or "").strip().lower()
        if val:
            return val
    return ""


def _safe_filename_part(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*\s]+', "_", (value or "track").strip())[:80]


_AUDIO_ROLE_PRIORITY = ("", "main", "dub", "subtitle", "description", "alternate", "commentary", "caption")


def _audio_role_rank(role: str) -> int:
    r = (role or "").lower()
    try:
        return _AUDIO_ROLE_PRIORITY.index(r)
    except ValueError:
        return len(_AUDIO_ROLE_PRIORITY)


def _track_identity(track: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        str(track.get("lang") or "und"),
        str(track.get("role") or ""),
        str(track.get("id") or ""),
    )


def _pick_default_audio_track(audio_tracks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not audio_tracks:
        return None

    def _score(track: Dict[str, Any]) -> Tuple[int, int, str]:
        lang = _lang_base(track.get("lang", ""))
        if lang == "und":
            lang_score = 0
        elif lang == "en":
            lang_score = 1
        else:
            lang_score = 2
        return (lang_score, _audio_role_rank(track.get("role", "")), str(track.get("lang") or ""))

    return min(audio_tracks, key=_score)


def _primary_audio_track_from_list(audio_tracks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return _pick_default_audio_track(audio_tracks)


def _upsert_audio_track(
    tracks: List[Dict[str, Any]],
    lang: str,
    role: str,
    rep_id: str,
    merged: Dict[str, Any],
) -> None:
    bw = int(merged.get("@bandwidth") or 0)
    for track in tracks:
        if (
            track.get("lang") == lang
            and track.get("role", "") == role
            and track.get("id", "") == rep_id
        ):
            if bw > int(track.get("@bandwidth") or 0):
                track.clear()
                track.update({**merged, "lang": lang, "role": role, "id": rep_id})
            return
    tracks.append({**merged, "lang": lang, "role": role, "id": rep_id})


def _normalize_audio_tracks(parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = parsed.get("audio_tracks")
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        out: List[Dict[str, Any]] = []
        for lang, merged in raw.items():
            out.append({
                **merged,
                "lang": lang,
                "role": merged.get("role", ""),
                "id": merged.get("@id", merged.get("id", "")),
            })
        return out
    if parsed.get("audio"):
        merged = parsed["audio"]
        return [{
            **merged,
            "lang": merged.get("@lang", merged.get("lang", "und")),
            "role": merged.get("role", ""),
            "id": merged.get("@id", merged.get("id", "")),
        }]
    return []


def _audio_display_name(lang: str, role: str) -> str:
    label = (lang or "und").upper()
    if role in ("description", "alternate"):
        return f"{label} (AD)"
    if role == "commentary":
        return f"{label} (komentar)"
    if role == "dub":
        return f"{label} (dub)"
    if role in ("main", "subtitle", ""):
        return label
    return f"{label} ({role})"


def _subtitle_extension(mime: str) -> str:
    m = (mime or "").lower()
    if "ttml" in m:
        return "ttml"
    if "srt" in m:
        return "srt"
    if "vtt" in m or "webvtt" in m:
        return "vtt"
    return "vtt"


def _pick_default_audio_lang(langs: List[str]) -> str:
    for pref in ("und", "en"):
        for lang in langs:
            if _lang_base(lang) == pref:
                return lang
    return langs[0] if langs else "und"


def _subtitle_track_wanted(wanted_langs: List[str], track_lang: str) -> bool:
    if not wanted_langs or wanted_langs == ["none"]:
        return False
    normalized = [w.lower() for w in wanted_langs]
    if "all" in normalized:
        return True
    tl = (track_lang or "und").lower()
    base = _lang_base(tl)
    for wanted in normalized:
        if tl == wanted or tl.startswith(f"{wanted}-") or base == wanted:
            return True
    return False


def _subtitle_display_name(lang: str, role: str) -> str:
    label = (lang or "und").upper()
    if role == "caption":
        return f"{label} (CC)"
    if role in ("subtitle", "main", ""):
        return label
    return f"{label} ({role})"


# ── MPD parsing ───────────────────────────────────────────────────────────────

def _parse_mpd(mpd_text: str, max_height: int = L3_MAX_HEIGHT) -> Dict[str, Any]:
    """
    Parse MPEG-DASH manifest, selecting best video/audio representations
    within the height cap, plus any subtitle tracks.
    Returns dict with keys: video, audio, subtitles, pssh
    """
    mpd = xmltodict.parse(mpd_text)
    root = mpd.get("MPD", mpd)
    mpd_duration = root.get("@mediaPresentationDuration", "")

    periods = root.get("Period", [])
    if isinstance(periods, dict):
        periods = [periods]

    best_video: Optional[Dict] = None
    audio_tracks_list: List[Dict[str, Any]] = []
    subtitle_tracks: List[Dict] = []
    pssh_b64: Optional[str] = None

    for period in periods:
        adapt_sets = period.get("AdaptationSet", [])
        if isinstance(adapt_sets, dict):
            adapt_sets = [adapt_sets]

        for adapt in adapt_sets:
            mime = (adapt.get("@mimeType") or "").lower()
            content_type = (adapt.get("@contentType") or "").lower()
            lang = adapt.get("@lang", "und")

            # ── PSSH (Widevine) ──────────────────────────────────────────────
            content_protections = adapt.get("ContentProtection", [])
            if isinstance(content_protections, dict):
                content_protections = [content_protections]
            for cp in content_protections:
                scheme_id = cp.get("@schemeIdUri", "").lower()
                if "edef8ba9-79d6-4ace-a3c8-27dcd51d21ed" in scheme_id or "widevine" in scheme_id:
                    pssh_node = cp.get("cenc:pssh") or cp.get("pssh")
                    if pssh_node and not pssh_b64:
                        pssh_b64 = pssh_node if isinstance(pssh_node, str) else pssh_node.get("#text", "")

            # ── Video ────────────────────────────────────────────────────────
            if "video" in mime or "video" in content_type:
                reps = adapt.get("Representation", [])
                if isinstance(reps, dict):
                    reps = [reps]
                for rep in reps:
                    h = int(rep.get("@height") or 0)
                    bw = int(rep.get("@bandwidth") or 0)
                    if h <= max_height:
                        if best_video is None or bw > int(best_video.get("@bandwidth", 0)):
                            best_video = {**adapt, **rep}

            # ── Audio ────────────────────────────────────────────────────────
            elif "audio" in mime or "audio" in content_type:
                role = _adaptation_role(adapt)
                reps = adapt.get("Representation", [])
                if isinstance(reps, dict):
                    reps = [reps]
                for rep in reps:
                    rep_id = str(rep.get("@id") or "")
                    _upsert_audio_track(
                        audio_tracks_list,
                        lang,
                        role,
                        rep_id,
                        {**adapt, **rep},
                    )

            # ── Subtitles ────────────────────────────────────────────────────
            elif (
                "text" in mime or "text" in content_type or "subtitle" in mime
            ) and "image" not in mime:
                reps = adapt.get("Representation", [])
                if isinstance(reps, dict):
                    reps = [reps]
                for rep in reps:
                    base_url = rep.get("BaseURL") or adapt.get("BaseURL")
                    if not base_url:
                        # Try SegmentTemplate
                        tmpl = rep.get("SegmentTemplate") or adapt.get("SegmentTemplate")
                        if tmpl:
                            base_url = tmpl.get("@media") or tmpl.get("@initialization")
                    subtitle_tracks.append({
                        "lang": lang,
                        "role": _adaptation_role(adapt),
                        "id": rep.get("@id", ""),
                        "mime": mime,
                        "base_url": base_url,
                        "adapt": adapt,
                        "rep": rep,
                    })

    best_audio = _primary_audio_track_from_list(audio_tracks_list)

    if best_video and mpd_duration:
        best_video["_mpd_duration"] = mpd_duration
    if best_audio and mpd_duration:
        best_audio["_mpd_duration"] = mpd_duration
    for track in audio_tracks_list:
        if mpd_duration:
            track["_mpd_duration"] = mpd_duration

    return {
        "video":        best_video,
        "audio":        best_audio,
        "audio_tracks": audio_tracks_list,
        "subtitles":    subtitle_tracks,
        "pssh":         pssh_b64,
    }


def _parse_mpd_duration(adapt_rep: Dict) -> Optional[float]:
    """Try to parse ISO 8601 duration (PT...S) stored in _mpd_duration key."""
    dur_str = adapt_rep.get("_mpd_duration", "")
    if not dur_str:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?", dur_str)
    if not m:
        return None
    h = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    secs = float(m.group(3) or 0)
    return h * 3600 + mins * 60 + secs


def _extract_segment_urls(adapt_rep: Dict, mpd_base_url: str) -> List[str]:
    """
    Extract all segment URLs from a Representation dict.
    Handles SegmentTemplate with SegmentTimeline, SegmentList, and BaseURL.
    """
    urls = []

    base_url = adapt_rep.get("BaseURL")
    if base_url:
        full = base_url if base_url.startswith("http") else mpd_base_url.rsplit("/", 1)[0] + "/" + base_url
        urls.append(full)
        return urls

    seg_tmpl = adapt_rep.get("SegmentTemplate")
    if seg_tmpl:
        init = seg_tmpl.get("@initialization")
        media = seg_tmpl.get("@media")
        rep_id = adapt_rep.get("@id", "")
        bandwidth = adapt_rep.get("@bandwidth", "")

        base = mpd_base_url.rsplit("/", 1)[0] + "/"

        def _fill(tmpl: str) -> str:
            return (tmpl or "")                .replace("$RepresentationID$", str(rep_id))                .replace("$Bandwidth$", str(bandwidth))

        if init:
            urls.append(base + _fill(init))

        timeline = seg_tmpl.get("SegmentTimeline")
        if timeline:
            segments = timeline.get("S", [])
            if isinstance(segments, dict):
                segments = [segments]
            t = 0
            for seg in segments:
                t_attr = seg.get("@t")
                if t_attr is not None:
                    t = int(t_attr)
                d = int(seg.get("@d", 0))
                r = int(seg.get("@r", 0)) + 1
                for _ in range(r):
                    seg_url = base + _fill(media).replace("$Time$", str(t))
                    urls.append(seg_url)
                    t += d
        else:
            start = int(seg_tmpl.get("@startNumber", 1))
            timescale = int(seg_tmpl.get("@timescale", 1))
            duration_attr = seg_tmpl.get("@duration")
            if duration_attr:
                seg_duration = int(duration_attr) / timescale
                # Derive total duration from MPD @mediaPresentationDuration if available
                total_secs = _parse_mpd_duration(adapt_rep) or 14400
                count = int(total_secs / seg_duration) + 5
                for i in range(start, start + count):
                    seg_url = base + _fill(media).replace("$Number$", str(i))
                    urls.append(seg_url)

    seg_list = adapt_rep.get("SegmentList")
    if seg_list:
        init_seg = seg_list.get("Initialization", {})
        src = init_seg.get("@sourceURL", "")
        if src:
            urls.append(mpd_base_url.rsplit("/", 1)[0] + "/" + src)
        for seg in seg_list.get("SegmentURL", []):
            media_url = seg.get("@media", "")
            if media_url:
                urls.append(mpd_base_url.rsplit("/", 1)[0] + "/" + media_url)

    return urls


# ── Download helpers ───────────────────────────────────────────────────────────

_seg_session: Optional[requests.Session] = None

def _get_seg_session() -> requests.Session:
    global _seg_session
    if _seg_session is None:
        _seg_session = requests.Session()
        _seg_session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        })
    return _seg_session


def _download_segments(
    urls: List[str],
    out_path: Path,
    label: str,
    workers: int = 16,
) -> None:
    """Download a list of segment URLs and concatenate into out_path."""
    total = len(urls)
    data_map: Dict[int, bytes] = {}
    sess = _get_seg_session()
    cancel_event = current_cancel_event()

    def _fetch(idx: int, url: str) -> Tuple[int, bytes]:
        for attempt in range(3):
            raise_if_cancelled(cancel_event)
            try:
                r = sess.get(url, timeout=30)
                r.raise_for_status()
                return idx, r.content
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1.5 ** attempt)
        raise_if_cancelled(cancel_event)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_fetch, i, url): i for i, url in enumerate(urls)}
        done = 0
        for fut in as_completed(futures):
            raise_if_cancelled(cancel_event)
            idx, data = fut.result()
            data_map[idx] = data
            done += 1
            pct = done * 100 // total
            logger.info(f"  {label}: {pct:3d}% ({done}/{total} segmenata)")

    with out_path.open("wb") as f:
        for i in sorted(data_map):
            raise_if_cancelled(cancel_event)
            f.write(data_map[i])


def _download_with_ytdlp(url: str, out_path: Path, headers: Dict[str, str]) -> None:
    """Download a single stream using yt-dlp (for BaseURL style streams)."""
    from yt_dlp import YoutubeDL
    def _progress(_data):
        raise_if_cancelled()

    ydl_opts = {
        "outtmpl":  str(out_path),
        "http_headers": headers,
        "quiet":    True,
        "noprogress": False,
        "progress_hooks": [_progress],
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


# ── Subtitle download ──────────────────────────────────────────────────────────

def _download_subtitles(
    subtitle_tracks: List[Dict],
    wanted_langs: List[str],
    out_dir: Path,
    mpd_base_url: str,
    sess: Any,
) -> List[Dict[str, str]]:
    """Download subtitle tracks. Returns list of {lang, path, name}."""
    result: List[Dict[str, str]] = []
    if not wanted_langs or wanted_langs == ["none"]:
        return result

    used_names: Dict[str, int] = {}

    for idx, track in enumerate(subtitle_tracks):
        lang = (track.get("lang") or "und").lower()
        role = (track.get("role") or "").lower()
        if not _subtitle_track_wanted(wanted_langs, lang):
            continue

        base_url = track.get("base_url")
        if not base_url:
            seg_urls = _extract_segment_urls(
                {**track.get("adapt", {}), **track.get("rep", {})},
                mpd_base_url,
            )
            if not seg_urls:
                logger.warning("Ne mogu naći subtitle URL za %s (%s)", lang, role or "main")
                continue
        else:
            seg_urls = [
                base_url if base_url.startswith("http")
                else mpd_base_url.rsplit("/", 1)[0] + "/" + base_url
            ]

        rep_id = _safe_filename_part(str(track.get("id") or f"{lang}_{role}_{idx}"))
        name_key = f"{lang}|{role}|{rep_id}"
        used_names[name_key] = used_names.get(name_key, 0) + 1
        suffix = f"_{role}" if role else ""
        if used_names[name_key] > 1:
            suffix += f"_{used_names[name_key]}"
        ext = _subtitle_extension(track.get("mime", ""))
        out_path = out_dir / f"sub_{_safe_filename_part(lang)}{suffix}_{rep_id}.{ext}"

        try:
            content_parts: List[str] = []
            header_written = False
            for url in seg_urls:
                r = sess.get(url, timeout=15)
                r.raise_for_status()
                text = r.text
                if not header_written:
                    content_parts.append(text)
                    header_written = True
                else:
                    lines = text.split("\n")
                    skip = 0
                    for i, line in enumerate(lines):
                        if line.strip() in ("WEBVTT", "") and i < 3:
                            skip = i + 1
                        else:
                            break
                    content_parts.append("\n".join(lines[skip:]))

            out_path.write_text("\n".join(content_parts), encoding="utf-8")
            display = _subtitle_display_name(lang, role)
            logger.info("  ✓ Titlovi %s: %s", display, out_path.name)
            result.append({"lang": lang, "path": str(out_path), "name": display})
        except Exception as e:
            logger.warning("  ✗ Titlovi %s (%s): %s", lang, role or "main", e)

    return result


# ── mp4decrypt ────────────────────────────────────────────────────────────────

def _decrypt_file(
    enc_path: Path,
    dec_path: Path,
    keys: List[Dict[str, str]],
    mp4decrypt_bin: str,
) -> None:
    """Run mp4decrypt to decrypt an encrypted MP4/CMAF file."""
    cmd = [mp4decrypt_bin]
    for k in keys:
        cmd += ["--key", f"{k['kid']}:{k['key']}"]
    cmd += [str(enc_path), str(dec_path)]
    result = run_subprocess(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"mp4decrypt greška:\n{result.stderr}")


# ── mkvmerge ──────────────────────────────────────────────────────────────────

def _download_decrypt_audio_tracks(
    audio_tracks: List[Dict[str, Any]],
    mpd_url: str,
    tmp: Path,
    keys: List[Dict],
    mp4decrypt_bin: str,
    workers: int,
    audio_mode: str = "all",
) -> List[Dict[str, Any]]:
    """Download and decrypt all (or primary) audio tracks from the manifest."""
    if not audio_tracks:
        raise RuntimeError("Nije pronađena audio reprezentacija u MPD.")

    if audio_mode == "first":
        primary = _pick_default_audio_track(audio_tracks)
        selected = [primary] if primary else []
    else:
        selected = list(audio_tracks)

    default_track = _pick_default_audio_track(selected) or (selected[0] if selected else None)
    default_key = _track_identity(default_track) if default_track else ("", "", "")
    decrypted: List[Dict[str, Any]] = []

    for track in sorted(selected, key=_track_identity):
        lang = str(track.get("lang") or "und")
        role = str(track.get("role") or "")
        rep_id = str(track.get("id") or "")
        safe_name = _safe_filename_part(f"{lang}_{role}_{rep_id}")
        enc_audio = tmp / f"audio_{safe_name}.mp4"
        dec_audio = tmp / f"audio_{safe_name}_dec.mp4"

        label = _audio_display_name(lang, role)
        logger.info("Preuzimam audio segmente (%s) …", label)
        aud_urls = _extract_segment_urls(track, mpd_url)
        if not aud_urls:
            logger.warning("Preskačem audio %s — nema segmenata.", label)
            continue
        _download_segments(aud_urls, enc_audio, f"Audio {label}", workers)

        if keys:
            _decrypt_file(enc_audio, dec_audio, keys, mp4decrypt_bin)
        else:
            enc_audio.rename(dec_audio)

        decrypted.append({
            "lang": lang,
            "role": role,
            "name": label,
            "path": dec_audio,
            "default": _track_identity(track) == default_key,
        })

    if not decrypted:
        raise RuntimeError("Nijedan audio zapis nije uspešno preuzet.")
    return decrypted


def _mux_mkv(
    video: Path,
    audio_tracks: List[Dict[str, Any]],
    out: Path,
    subtitles: Optional[List[Dict]],
    mkvmerge_bin: str,
) -> None:
    """Mux video, multiple audio tracks and optional subtitles into MKV."""
    temp_out = temporary_media_path(out)
    cmd = [
        mkvmerge_bin, "--ui-language", "en",
        "--output", str(temp_out),
        "--language", "0:und", "--default-track", "0:yes", str(video),
    ]

    default_set = False
    for track in audio_tracks:
        lang = str(track.get("lang") or "und")
        iso = _lang_to_iso639_2(lang)
        is_default = bool(track.get("default")) and not default_set
        if is_default:
            default_set = True
        cmd += ["--language", f"0:{iso}", "--default-track", f"0:{'yes' if is_default else 'no'}"]
        name = track.get("name")
        if name:
            cmd += ["--track-name", f"0:{name}"]
        cmd.append(str(track["path"]))

    if subtitles:
        for sub in subtitles:
            lang_bcp = (sub.get("lang") or "und").lower()
            iso = _lang_to_iso639_2(lang_bcp)
            cmd += ["--language", f"0:{iso}", "--default-track", "0:no"]
            name = sub.get("name")
            if name:
                cmd += ["--track-name", f"0:{name}"]
            cmd.append(sub["path"])

    cmd.append("--no-global-tags")

    result = run_subprocess(cmd, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        temp_out.unlink(missing_ok=True)
        raise RuntimeError(f"mkvmerge greška:\n{result.stderr}")
    promote_validated_media(temp_out, out, mkvmerge_path=mkvmerge_bin)


# ── Main Downloader ────────────────────────────────────────────────────────────

class HBOMaxDownloader:
    """End-to-end HBO Max / Max video downloader."""

    def __init__(
        self,
        market:     str = "emea",
        output_dir: str = "output",
        device_path: Optional[str] = None,
        workers:    int = 16,
    ):
        self.market      = market
        self.output_dir  = Path(output_dir)
        self.workers     = workers
        self.auth        = HBOMaxAuth(market=market)
        self.api         = MaxAPI(self.auth)
        if _USE_CENTRAL_DRM and _drm_manager and _drm_manager.is_ready():
            self.cdm = HBOCDMBridge()
            logger.info("HBO Max: using centralized DRM Manager")
        else:
            self.cdm = WidevineCDM(device_path=device_path)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.mp4decrypt_path = None
        self.mkvmerge_path = None

        if _HAS_CURL_CFFI:
            from curl_cffi import requests as cffi_requests
            self._sess = cffi_requests.Session(impersonate="chrome124")
        else:
            self._sess = requests.Session()

    # ── Video ID extraction ───────────────────────────────────────────────────

    @staticmethod
    def extract_video_id(target: str) -> str:
        """
        Accept full URL or bare UUID and return the video ID.
        URL format: https://play.hbomax.com/video/watch/<ep_id>/<video_id>
                    https://www.max.com/video/watch/<ep_id>/<video_id>
        """
        target = target.strip()
        # If it looks like a UUID already
        uuid_re = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        if re.fullmatch(uuid_re, target, re.I):
            return target
        # Extract last UUID from URL
        matches = re.findall(uuid_re, target, re.I)
        if matches:
            return matches[-1]
        raise ValueError(f"Ne mogu da prepoznam video ID iz: {target!r}")

    # ── Download pipeline ─────────────────────────────────────────────────────

    def _finalize_from_parsed(
        self,
        parsed: Dict[str, Any],
        mpd_url: str,
        safe_title: str,
        wanted_subs: List[str],
        keys: List[Dict],
        audio_mode: str = "all",
    ) -> None:
        """Download segments, decrypt, subtitles and mux from parsed MPD."""
        audio_tracks = _normalize_audio_tracks(parsed)
        if not parsed.get("video"):
            raise RuntimeError(f"Nije pronađena video reprezentacija ≤{L3_MAX_HEIGHT}p u MPD.")
        if not audio_tracks:
            raise RuntimeError("Nije pronađena audio reprezentacija u MPD.")

        vh = parsed["video"].get("@height", "?")
        vbw = int(parsed["video"].get("@bandwidth", 0)) // 1000
        logger.info(f"Video: {vh}p @ {vbw} kbps")
        audio_labels = [
            _audio_display_name(t.get("lang", "und"), t.get("role", ""))
            for t in audio_tracks
        ]
        logger.info(
            "Audio u manifestu (%s): %s",
            len(audio_labels),
            ", ".join(audio_labels) if audio_labels else "—",
        )
        logger.info(
            "Subtitlovi u manifestu: %s",
            [f"{t.get('lang', 'und')}{'/' + t['role'] if t.get('role') else ''}" for t in parsed["subtitles"]],
        )

        tmp = Path(tempfile.mkdtemp(prefix="hbomax_"))
        try:
            enc_video = tmp / "video.mp4"
            dec_video = tmp / "video_dec.mp4"

            logger.info("Preuzimam video segmente …")
            vid_urls = _extract_segment_urls(parsed["video"], mpd_url)
            if not vid_urls:
                raise RuntimeError("Nije pronađen nijedan video segment URL.")
            _download_segments(vid_urls, enc_video, "Video", self.workers)

            bins = _require_binaries(self.mp4decrypt_path, self.mkvmerge_path)

            if keys:
                logger.info("Dekripcija videa …")
                _decrypt_file(enc_video, dec_video, keys, bins["mp4decrypt"])
            else:
                enc_video.rename(dec_video)

            decrypted_audio = _download_decrypt_audio_tracks(
                audio_tracks,
                mpd_url,
                tmp,
                keys,
                bins["mp4decrypt"],
                self.workers,
                audio_mode=audio_mode,
            )

            subs: List[Dict] = []
            if wanted_subs and wanted_subs != ["none"]:
                logger.info("Preuzimam titlove: %s …", ", ".join(wanted_subs))
                subs = _download_subtitles(
                    parsed["subtitles"],
                    wanted_subs,
                    tmp,
                    mpd_url,
                    self._sess,
                )

            out_path = self.output_dir / f"{safe_title}.mkv"
            logger.info(f"Muxing → {out_path} …")
            _mux_mkv(dec_video, decrypted_audio, out_path, subs or None, bins["mkvmerge"])
            logger.info(f"✓ Završeno: {out_path} ({len(decrypted_audio)} audio, {len(subs)} titlova)")
        finally:
            import shutil as _shutil
            _shutil.rmtree(tmp, ignore_errors=True)

    def download(
        self,
        video_id: str,
        wanted_subs: List[str],
        audio_mode: str = "all",
    ) -> None:
        """Full download pipeline for one video."""
        video_id = self.extract_video_id(video_id)
        logger.info(f"Preuzimam video ID: {video_id}")

        # ── 1. Metadata ───────────────────────────────────────────────────────
        logger.info("Dohvatam metapodatke …")
        try:
            content = self.api.get_content(video_id)
        except Exception as e:
            logger.warning(f"Ne mogu dohvatiti metapodatke: {e}. Nastavlja se bez naslova.")
            content = {}

        title = self._extract_title(content, video_id)
        safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)
        logger.info(f"Naslov: {title}")

        # ── 2. Playback URL + DRM headers ─────────────────────────────────────
        logger.info("Tražim stream URL …")
        # Try to find the edit/asset ID
        edit_id = self._find_edit_id(content, video_id)
        try:
            playback = self.api.get_playback(edit_id)
        except Exception as e:
            raise RuntimeError(f"Ne mogu dobiti playback info: {e}")

        mpd_url = self._extract_mpd_url(playback)
        if not mpd_url:
            raise RuntimeError("MPD URL nije pronađen u playback odgovoru.")
        logger.info(f"MPD: {mpd_url[:80]}…")

        # ── 3. Parse manifest ─────────────────────────────────────────────────
        logger.info("Parsiranje MPD manifesta …")
        mpd_text = self.api.get_manifest(mpd_url)
        parsed   = _parse_mpd(mpd_text, max_height=L3_MAX_HEIGHT)

        # ── 4. Widevine keys ──────────────────────────────────────────────────
        pssh = parsed.get("pssh")
        keys: List[Dict] = []
        if pssh:
            logger.info("Dobavljam Widevine ključeve …")
            lic_headers = self.api.get_license_headers(playback)
            try:
                keys = self.cdm.get_keys(pssh, LICENSE_URL, lic_headers)
                logger.info(f"Dobijeno {len(keys)} ključ(eva)")
                for k in keys:
                    logger.debug(f"  KID={k['kid']} KEY={k['key']}")
            except Exception as e:
                raise RuntimeError(f"Widevine licenca nije uspela: {e}")
        else:
            logger.warning("PSSH nije pronađen — sadržaj možda nije zaštićen ili je manifest nestandardan.")

        self._finalize_from_parsed(parsed, mpd_url, safe_title, wanted_subs, keys, audio_mode)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def download_direct(
        self,
        manifest_url: str,
        license_url: str,
        title: str,
        wanted_subs: List[str],
        audio_mode: str = "all",
    ) -> None:
        """Full download pipeline using direct manifest URL and license URL (Bypass Mode)."""
        logger.info("Započinjem direktno preuzimanje preko manifesta i licence...")
        if not title or not title.strip():
            title = f"Max_Direct_{int(time.time())}"
        safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)
        logger.info(f"Naslov: {title}")

        # ── 1. Parse manifest ─────────────────────────────────────────────────
        logger.info("Parsiranje MPD manifesta …")
        mpd_text = self.api.get_manifest(manifest_url)
        parsed   = _parse_mpd(mpd_text, max_height=L3_MAX_HEIGHT)

        # ── 2. Widevine keys ──────────────────────────────────────────────────
        pssh = parsed.get("pssh")
        keys: List[Dict] = []
        if pssh:
            logger.info("Dobavljam Widevine ključeve …")
            lic_headers = {
                "Content-Type": "application/octet-stream",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Origin": "https://www.max.com",
                "Referer": "https://www.max.com/",
            }
            try:
                token = self.auth.get_access_token()
                if token:
                    lic_headers["Authorization"] = f"Bearer {token}"
            except Exception:
                pass
            try:
                keys = self.cdm.get_keys(pssh, license_url, lic_headers)
                logger.info(f"Dobijeno {len(keys)} ključ(eva)")
                for k in keys:
                    logger.debug(f"  KID={k['kid']} KEY={k['key']}")
            except Exception as e:
                raise RuntimeError(f"Widevine licenca nije uspela: {e}")
        else:
            logger.warning("PSSH nije pronađen — sadržaj možda nije zaštićen ili je manifest nestandardan.")

        self._finalize_from_parsed(
            parsed, manifest_url, safe_title, wanted_subs, keys, audio_mode
        )

    @staticmethod
    def _extract_title(content: Dict, video_id: str) -> str:
        """Best-effort title extraction from the content API response."""
        body = content.get("body") or content
        if isinstance(body, list) and body:
            body = body[0]
        if isinstance(body, dict):
            # Try common title fields
            for field in ("title", "name", "seriesName", "showName"):
                v = body.get(field)
                if v and isinstance(v, str):
                    return v
            # Nested items
            items = body.get("items", [])
            if items and isinstance(items, list):
                item = items[0]
                for field in ("title", "name"):
                    v = item.get(field)
                    if v:
                        return str(v)
        return f"HBO_Max_{video_id[:8]}"

    @staticmethod
    def _find_edit_id(content: Dict, video_id: str) -> str:
        """
        Try to find the edit/asset ID from content metadata.
        Fall back to using video_id directly as the asset ID.
        """
        body = content.get("body") or content
        if isinstance(body, list) and body:
            body = body[0]
        if isinstance(body, dict):
            # SlyGuy API pattern
            for field in ("editId", "edit_id", "assetId", "asset_id", "id"):
                v = body.get(field)
                if v and isinstance(v, str):
                    return v
            # Inside items
            items = body.get("items", [])
            if items and isinstance(items, list):
                for item in items:
                    for field in ("editId", "edit_id", "assetId", "id"):
                        v = item.get(field)
                        if v:
                            return str(v)
        # Fallback
        return video_id

    @staticmethod
    def _extract_mpd_url(playback: Dict) -> Optional[str]:
        """Extract the MPD/DASH URL from a playback response."""
        # Direct URL
        for field in ("url", "manifestUrl", "manifest_url", "dashUrl", "dash_url"):
            v = playback.get(field)
            if v and isinstance(v, str) and ("mpd" in v or "dash" in v or v.endswith(".mpd")):
                return v
        # Nested under 'sources' or 'stream'
        for key in ("sources", "streams", "source", "stream"):
            sources = playback.get(key)
            if isinstance(sources, list):
                for src in sources:
                    if isinstance(src, dict):
                        for field in ("src", "url", "manifestUrl", "dash"):
                            v = src.get(field)
                            if v and isinstance(v, str):
                                return v
            elif isinstance(sources, dict):
                for field in ("src", "url", "manifestUrl", "dash"):
                    v = sources.get(field)
                    if v and isinstance(v, str):
                        return v
        # Deep search for any .mpd URL
        raw = json.dumps(playback)
        matches = re.findall(r'https?://[^\s"\'<>]+\.mpd[^\s"\'<>]*', raw)
        if matches:
            return matches[0]
        # Any DASH-like URL
        matches = re.findall(r'https?://[^\s"\'<>]*/dash/[^\s"\'<>]+', raw)
        if matches:
            return matches[0]
        return None


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="HBO Max / Max Video Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Primeri:
  # Login (jednom):
  python hbomax_downloader.py --login --market emea

  # Download po video ID:
  python hbomax_downloader.py -i de4c9160-1b67-4c1e-8cad-e7b0e42c5fdf

  # Download po URL:
  python hbomax_downloader.py -i "https://play.hbomax.com/video/watch/.../de4c9160-..."

  # Sa titlovima / audio:
  python hbomax_downloader.py -i <id> --subs all
  python hbomax_downloader.py -i <id> --subs sr,hr,en
  python hbomax_downloader.py -i <id> --subs none --audio first
""",
    )

    # Auth
    parser.add_argument("--login",  action="store_true", help="Pokrenuti device-code login")
    parser.add_argument("--market", default="emea",      help="Market: emea / latam / us (default: emea)")

    # Download
    parser.add_argument("-i", "--id",   dest="video_id", help="Video ID (UUID) ili puni URL")
    parser.add_argument("--subs",       default=_DEFAULT_SUBS,
                        help=f"Titlovi: 'all', lista jezika ili 'none' (default: {_DEFAULT_SUBS})")
    parser.add_argument("--audio",      default=_DEFAULT_AUDIO,
                        help=f"Audio: 'all' (svi jezici) ili 'first' (jedan, default: {_DEFAULT_AUDIO})")

    # Direct Download (Bypass Mode)
    parser.add_argument("--manifest",      default=None,       help="Direktni DASH (.mpd) manifest URL")
    parser.add_argument("--license",       default=None,       help="Direktni Widevine licencni URL")
    parser.add_argument("--title",         default=None,       help="Naslov za direktno preuzimanje")

    # Custom binary paths
    parser.add_argument("--mp4decrypt",    default=None,       help="Putanja do mp4decrypt izvršnog fajla")
    parser.add_argument("--mkvmerge",      default=None,       help="Putanja do mkvmerge izvršnog fajla")

    # Output / tuning
    parser.add_argument("-o", "--output",  default="output",  help="Izlazni folder (default: output)")
    parser.add_argument("-d", "--device",  default=None,       help="Putanja do .wvd CDM fajla")
    parser.add_argument("-w", "--workers", type=int, default=16, help="Broj paralelnih download niti (default: 16)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Detaljan ispis (debug)")

    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    # ── Login mode ────────────────────────────────────────────────────────────
    if args.login:
        auth = HBOMaxAuth(market=args.market)
        auth.login()
        return 0

    # ── Download mode ─────────────────────────────────────────────────────────
    if not args.video_id and not (args.manifest and args.license):
        print("Greška: navedite -i <video_id> ili --manifest i --license, ili --login")
        return 1

    subs_raw = (args.subs or "").strip().lower()
    if subs_raw in ("none", "no", ""):
        wanted_subs = ["none"]
    elif subs_raw == "all":
        wanted_subs = ["all"]
    else:
        wanted_subs = [s.strip() for s in subs_raw.split(",") if s.strip()]

    audio_mode = (args.audio or _DEFAULT_AUDIO).strip().lower()
    if audio_mode not in ("all", "first"):
        audio_mode = "all"

    # Ensure authenticated
    auth = HBOMaxAuth(market=args.market)
    if not auth.is_authenticated():
        print("Niste prijavljeni. Pokrenite:\n  python hbomax_downloader.py --login --market emea")
        return 1

    # Run download
    dl = HBOMaxDownloader(
        market=args.market,
        output_dir=args.output,
        device_path=args.device,
        workers=args.workers,
    )
    dl.mp4decrypt_path = args.mp4decrypt
    dl.mkvmerge_path = args.mkvmerge
    try:
        if args.manifest and args.license:
            dl.download_direct(args.manifest, args.license, args.title, wanted_subs, audio_mode)
        else:
            dl.download(args.video_id, wanted_subs, audio_mode)
        return 0
    except KeyboardInterrupt:
        print("\nPrekid od strane korisnika.")
        return 130
    except Exception as e:
        logger.error(f"Greška: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
