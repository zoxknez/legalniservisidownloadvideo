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
    python hbomax_downloader.py -i <id> --subs sr,hr,mk,bs,sl
    python hbomax_downloader.py -i <id> --subs none

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

from hbomax_auth import HBOMaxAuth, load_token, save_token

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

_DEFAULT_SUBS = "sr,hr,mk,bs,sl"
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


# ── Binary discovery ───────────────────────────────────────────────────────────

def _find_binary(name: str) -> Optional[str]:
    """Find an executable in PATH or a local binaries/ subfolder."""
    # Local binaries folder
    local = Path(__file__).parent / "binaries" / (name + (".exe" if platform.system() == "Windows" else ""))
    if local.exists():
        return str(local)
    return shutil.which(name)


def _require_binaries() -> Dict[str, str]:
    needed = {
        "mp4decrypt": _find_binary("mp4decrypt"),
        "mkvmerge":   _find_binary("mkvmerge"),
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


# ── MPD parsing ───────────────────────────────────────────────────────────────

def _parse_mpd(mpd_text: str, max_height: int = L3_MAX_HEIGHT) -> Dict[str, Any]:
    """
    Parse MPEG-DASH manifest, selecting best video/audio representations
    within the height cap, plus any subtitle tracks.
    Returns dict with keys: video, audio, subtitles, pssh
    """
    mpd = xmltodict.parse(mpd_text)
    root = mpd.get("MPD", mpd)

    periods = root.get("Period", [])
    if isinstance(periods, dict):
        periods = [periods]

    best_video: Optional[Dict] = None
    best_audio_by_lang: Dict[str, Dict] = {}
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
                reps = adapt.get("Representation", [])
                if isinstance(reps, dict):
                    reps = [reps]
                for rep in reps:
                    bw = int(rep.get("@bandwidth") or 0)
                    existing = best_audio_by_lang.get(lang)
                    if not existing or bw > int(existing.get("@bandwidth", 0)):
                        best_audio_by_lang[lang] = {**adapt, **rep}

            # ── Subtitles ────────────────────────────────────────────────────
            elif "text" in mime or "text" in content_type or "subtitle" in mime:
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
                        "mime": mime,
                        "base_url": base_url,
                        "adapt": adapt,
                        "rep": rep,
                    })

    # Pick a single audio track — prefer 'und' or first available
    best_audio = (
        best_audio_by_lang.get("und")
        or best_audio_by_lang.get("en")
        or (next(iter(best_audio_by_lang.values())) if best_audio_by_lang else None)
    )

    return {
        "video":     best_video,
        "audio":     best_audio,
        "subtitles": subtitle_tracks,
        "pssh":      pssh_b64,
    }


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
            # Number-based template
            start = int(seg_tmpl.get("@startNumber", 1))
            timescale = int(seg_tmpl.get("@timescale", 1))
            duration_attr = seg_tmpl.get("@duration")
            if duration_attr:
                seg_duration = int(duration_attr) / timescale
                # We need total duration — estimate 2 hours
                total_secs = 7200
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

def _download_segments(
    urls: List[str],
    out_path: Path,
    label: str,
    workers: int = 16,
) -> None:
    """Download a list of segment URLs and concatenate into out_path."""
    total = len(urls)
    data_map: Dict[int, bytes] = {}

    def _fetch(idx: int, url: str) -> Tuple[int, bytes]:
        for attempt in range(3):
            try:
                r = requests.get(url, timeout=30, stream=True)
                r.raise_for_status()
                return idx, r.content
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(1.5 ** attempt)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_fetch, i, url): i for i, url in enumerate(urls)}
        done = 0
        for fut in as_completed(futures):
            idx, data = fut.result()
            data_map[idx] = data
            done += 1
            pct = done * 100 // total
            print(f"\r  {label}: {pct:3d}% ({done}/{total} segmenata)", end="", flush=True)

    print()  # newline after progress
    with out_path.open("wb") as f:
        for i in sorted(data_map):
            f.write(data_map[i])


def _download_with_ytdlp(url: str, out_path: Path, headers: Dict[str, str]) -> None:
    """Download a single stream using yt-dlp (for BaseURL style streams)."""
    from yt_dlp import YoutubeDL
    ydl_opts = {
        "outtmpl":  str(out_path),
        "http_headers": headers,
        "quiet":    True,
        "noprogress": False,
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
    """Download subtitle tracks for wanted languages. Returns list of {lang, path}."""
    result = []
    if not wanted_langs or wanted_langs == ["none"]:
        return result

    for track in subtitle_tracks:
        lang = track.get("lang", "und").lower()
        # Check if this language is wanted
        if wanted_langs and not any(lang.startswith(w.lower()) for w in wanted_langs):
            continue

        base_url = track.get("base_url")
        if not base_url:
            # Try to build from SegmentTemplate
            seg_urls = _extract_segment_urls({**track.get("adapt", {}), **track.get("rep", {})}, mpd_base_url)
            if not seg_urls:
                logger.warning(f"Ne mogu naći subtitle URL za {lang}")
                continue
        else:
            seg_urls = [base_url if base_url.startswith("http") else mpd_base_url.rsplit("/", 1)[0] + "/" + base_url]

        out_path = out_dir / f"sub_{lang}.vtt"
        try:
            content_parts = []
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
            logger.info(f"  ✓ Titlovi {lang}: {out_path.name}")
            result.append({"lang": lang, "path": str(out_path)})
        except Exception as e:
            logger.warning(f"  ✗ Titlovi {lang}: {e}")

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
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"mp4decrypt greška:\n{result.stderr}")


# ── mkvmerge ──────────────────────────────────────────────────────────────────

def _mux_mkv(
    video: Path,
    audio: Path,
    out: Path,
    subtitles: Optional[List[Dict]],
    mkvmerge_bin: str,
) -> None:
    """Mux video, audio and optional subtitles into MKV."""
    lang_map = {
        "sr": "srp", "sr-latn": "srp", "sr-cyrl": "srp",
        "hr": "hrv", "mk": "mkd", "bs": "bos",
        "sl": "slv", "en": "eng", "und": "und",
    }

    cmd = [
        mkvmerge_bin, "--ui-language", "en",
        "--output", str(out),
        "--language", "0:und", "--default-track", "0:yes", str(video),
        "--language", "0:und", "--default-track", "0:yes", str(audio),
    ]

    if subtitles:
        for sub in subtitles:
            lang_bcp = sub.get("lang", "und").lower()
            iso = lang_map.get(lang_bcp, lang_bcp[:3])
            cmd += ["--language", f"0:{iso}", "--default-track", "0:no", sub["path"]]

    cmd.append("--no-global-tags")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode not in (0, 1):  # mkvmerge returns 1 for warnings
        raise RuntimeError(f"mkvmerge greška:\n{result.stderr}")


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
        self.cdm         = WidevineCDM(device_path=device_path)
        self.output_dir.mkdir(parents=True, exist_ok=True)

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

    def download(self, video_id: str, wanted_subs: List[str]) -> None:
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

        if not parsed["video"]:
            raise RuntimeError(f"Nije pronađena video reprezentacija ≤{L3_MAX_HEIGHT}p u MPD.")
        if not parsed["audio"]:
            raise RuntimeError("Nije pronađena audio reprezentacija u MPD.")

        vh = parsed["video"].get("@height", "?")
        vbw = int(parsed["video"].get("@bandwidth", 0)) // 1000
        logger.info(f"Video: {vh}p @ {vbw} kbps")
        logger.info(f"Subtitlovi u manifestu: {[t['lang'] for t in parsed['subtitles']]}")

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

        # ── 5. Download segments ──────────────────────────────────────────────
        tmp = Path(tempfile.mkdtemp(prefix="hbomax_"))
        try:
            enc_video = tmp / "video.mp4"
            enc_audio = tmp / "audio.mp4"
            dec_video = tmp / "video_dec.mp4"
            dec_audio = tmp / "audio_dec.mp4"

            logger.info("Preuzimam video segmente …")
            vid_urls = _extract_segment_urls(parsed["video"], mpd_url)
            if not vid_urls:
                raise RuntimeError("Nije pronađen nijedan video segment URL.")
            _download_segments(vid_urls, enc_video, "Video", self.workers)

            logger.info("Preuzimam audio segmente …")
            aud_urls = _extract_segment_urls(parsed["audio"], mpd_url)
            if not aud_urls:
                raise RuntimeError("Nije pronađen nijedan audio segment URL.")
            _download_segments(aud_urls, enc_audio, "Audio", self.workers)

            # ── 6. Decrypt ────────────────────────────────────────────────────
            bins = _require_binaries()

            if keys:
                logger.info("Dekripcija …")
                _decrypt_file(enc_video, dec_video, keys, bins["mp4decrypt"])
                _decrypt_file(enc_audio, dec_audio, keys, bins["mp4decrypt"])
            else:
                # No encryption — rename
                enc_video.rename(dec_video)
                enc_audio.rename(dec_audio)

            # ── 7. Subtitles ───────────────────────────────────────────────────
            subs: List[Dict] = []
            if wanted_subs and wanted_subs != ["none"]:
                logger.info(f"Preuzimam titlove: {', '.join(wanted_subs)} …")
                subs = _download_subtitles(
                    parsed["subtitles"],
                    wanted_subs,
                    tmp,
                    mpd_url,
                    self._sess,
                )

            # ── 8. Mux to MKV ─────────────────────────────────────────────────
            out_path = self.output_dir / f"{safe_title}.mkv"
            logger.info(f"Muxing → {out_path} …")
            _mux_mkv(dec_video, dec_audio, out_path, subs or None, bins["mkvmerge"])
            logger.info(f"✓ Završeno: {out_path}")

        finally:
            # Clean up temp files
            import shutil as _shutil
            _shutil.rmtree(tmp, ignore_errors=True)

    # ── Internal helpers ──────────────────────────────────────────────────────

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

  # Sa titlovima:
  python hbomax_downloader.py -i <id> --subs sr,hr,mk,bs,sl
  python hbomax_downloader.py -i <id> --subs none
""",
    )

    # Auth
    parser.add_argument("--login",  action="store_true", help="Pokrenuti device-code login")
    parser.add_argument("--market", default="emea",      help="Market: emea / latam / us (default: emea)")

    # Download
    parser.add_argument("-i", "--id",   dest="video_id", help="Video ID (UUID) ili puni URL")
    parser.add_argument("--subs",       default=_DEFAULT_SUBS,
                        help=f"Jezici titlova odvojeni zarezom, ili 'none' (default: {_DEFAULT_SUBS})")

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
    if not args.video_id:
        print("Greška: navedite -i <video_id> ili --login")
        return 1

    # Parse subtitle languages
    subs_raw = (args.subs or "").strip().lower()
    if subs_raw in ("none", "no", ""):
        wanted_subs = ["none"]
    else:
        wanted_subs = [s.strip() for s in subs_raw.split(",") if s.strip()]

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
    try:
        dl.download(args.video_id, wanted_subs)
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
