#!/usr/bin/env python3
"""
Voyo.rs Downloader
Downloads HLS streams from voyo.rs (AES-128, handled by yt-dlp).

Output filename format:
  Series : ShowTitle.S01E03.1080p.WEB-DL-VOYO.mkv
  Movie  : MovieTitle.2019.1080p.WEB-DL-VOYO.mkv

Stream format:
  HLS (.m3u8) from vod.rtlrs-api.com, AES-128 per-segment keys.
  yt-dlp resolves keys automatically. Final mux via mkvmerge.

Usage:
  python voyo_downloader.py --save-credentials -u user@email.com -p password
  python voyo_downloader.py --video 50584
  python voyo_downloader.py https://voyo.rs/uspeh-1_50584.html
  python voyo_downloader.py --series 542
  python voyo_downloader.py --series 542 --episodes 1-3
  python voyo_downloader.py --series 542 --list
  python voyo_downloader.py --video 50584 -o /path/to/output
"""

import argparse
import base64
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
from typing import Any, Dict, List, Optional, Tuple

import requests

from backend.utils.cancellable_subprocess import raise_if_cancelled, run as run_subprocess
from backend.utils.media_validation import temporary_media_path

from .auth import VoyoAuth, VoyoConfig
from .stream_probe import classify_url_info

logger = logging.getLogger(__name__)

requests.packages.urllib3.disable_warnings()

RELEASE_GROUP = 'VOYO'

_RESOLUTION_MAX_HEIGHT = {
    '2160p': 2160,
    '1440p': 1440,
    '1080p': 1080,
    '720p': 720,
    '480p': 480,
    '360p': 360,
}


def _resolution_max_height(resolution: str) -> Optional[int]:
    if not resolution:
        return None
    key = resolution.strip().lower().split()[0]
    if key in _RESOLUTION_MAX_HEIGHT:
        return _RESOLUTION_MAX_HEIGHT[key]
    m = re.search(r'(\d+)', key)
    return int(m.group(1)) if m else None


# ── Tool detection ────────────────────────────────────────────────────────────

def _find_tool(name: str, windows_hints: List[str] = None) -> Optional[str]:
    if shutil.which(name):
        return name
    if platform.system() == 'Windows' and windows_hints:
        for hint in windows_hints:
            p = Path(hint)
            if p.exists():
                return str(p)
    return None


MKVMERGE = _find_tool('mkvmerge', [
    r'C:\Program Files\MKVToolNix\mkvmerge.exe',
    r'C:\Program Files (x86)\MKVToolNix\mkvmerge.exe',
])


# ── Filename helpers ──────────────────────────────────────────────────────────

FFPROBE = _find_tool('ffprobe', [
    r'C:\Program Files\ffmpeg\bin\ffprobe.exe',
    r'C:\Program Files (x86)\ffmpeg\bin\ffprobe.exe',
])

MIN_EXISTING_OUTPUT_BYTES = 1024 * 1024


def _unique_sidecar_path(path: Path, suffix: str) -> Path:
    candidate = path.with_name(path.name + suffix)
    if not candidate.exists():
        return candidate
    for idx in range(1, 1000):
        candidate = path.with_name(f'{path.name}{suffix}.{idx}')
        if not candidate.exists():
            return candidate
    return path.with_name(f'{path.name}{suffix}.{uuid.uuid4().hex}')


def _existing_output_is_complete(path: Path) -> bool:
    try:
        if not path.is_file():
            return False
        size = path.stat().st_size
    except OSError as e:
        logger.warning(f'Cannot inspect existing output {path.name}: {e}')
        return False

    if size < MIN_EXISTING_OUTPUT_BYTES:
        logger.warning(
            f'Existing output looks incomplete ({size} bytes): {path.name}'
        )
        return False

    if FFPROBE:
        cmd = [
            FFPROBE,
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(path),
        ]
        try:
            result = run_subprocess(
                cmd,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception as e:
            logger.warning(f'ffprobe failed for existing output {path.name}: {e}')
            return False
        duration_text = (result.stdout or '').strip().splitlines()
        try:
            duration = float(duration_text[0]) if duration_text else 0.0
        except ValueError:
            duration = 0.0
        if result.returncode != 0 or duration <= 1.0:
            logger.warning(f'Existing output failed media validation: {path.name}')
            return False
        return True

    if MKVMERGE:
        try:
            result = run_subprocess(
                [MKVMERGE, '--identify', str(path)],
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception as e:
            logger.warning(f'mkvmerge identify failed for {path.name}: {e}')
            return False
        if result.returncode != 0 or 'Track ID' not in (result.stdout or ''):
            logger.warning(f'Existing output failed MKV validation: {path.name}')
            return False

    return True


def _move_incomplete_output(path: Path) -> bool:
    target = _unique_sidecar_path(path, '.incomplete')
    try:
        path.rename(target)
    except OSError as e:
        logger.error(f'Cannot move incomplete output {path.name}: {e}')
        return False
    logger.warning(f'Moved incomplete output aside: {target.name}')
    return True


def _sanitize(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip(' .')


def _parse_season_number(season_str) -> int:
    if not season_str:
        return 1
    m = re.search(r'(\d+)', str(season_str))
    return int(m.group(1)) if m else 1


def build_filename(meta: Dict[str, Any], video_id: int,
                   series_title: str = '', resolution: str = '1080p') -> str:
    """
    Build SxxExx filename from metadata.

    Priority for show name: series_title param > meta.originalTitle > meta.title
    Season/episode come from meta.meta.season and meta.meta.episode.
    """
    inner = meta.get('meta', {})

    episode_num = inner.get('episode')
    season_str  = inner.get('season', '')
    year        = inner.get('year')

    # Best show name: caller-supplied series_title > originalTitle > strip episode suffix
    if series_title:
        show = _sanitize(series_title)
    elif inner.get('originalTitle'):
        show = _sanitize(inner['originalTitle'])
    else:
        # Strip trailing " N" episode number from title, e.g. "Uspeh 1" -> "Uspeh"
        raw = meta.get('title', f'video_{video_id}')
        show = _sanitize(re.sub(r'\s+\d+$', '', raw).strip())

    tag = f'WEB-DL-{RELEASE_GROUP}'

    if episode_num is not None and int(episode_num) > 0:
        # episode=0 means movie/standalone, not a series episode
        season_num = _parse_season_number(season_str)
        se = f'S{season_num:02d}E{int(episode_num):02d}'
        return f'{show}.{se}.{resolution}.{tag}'
    elif year:
        return f'{show}.{year}.{resolution}.{tag}'
    else:
        return f'{show}.{resolution}.{tag}'


# ── yt-dlp download ───────────────────────────────────────────────────────────

def detect_resolution(m3u8_url: str, auth: VoyoAuth) -> str:
    """
    Probe the m3u8 playlist (no download) and return a resolution tag.

    Returns strings like '2160p', '1080p', '720p', '480p', '360p'.
    Falls back to '1080p' if detection fails.
    """
    try:
        import yt_dlp
    except ImportError:
        return '1080p'

    headers = dict(auth.session.headers)
    headers.pop('Content-Type', None)
    headers['device-id'] = auth.state.device_id

    ydl_opts = {
        'quiet':                    True,
        'no_warnings':              True,
        'http_headers':             headers,
        'allow_unplayable_formats': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(m3u8_url, download=False)
            if info is None:
                return '1080p'

            # Look for the best video format's height
            height = None
            formats = info.get('formats', [])
            # Pick the format yt-dlp would select as 'bestvideo'
            video_fmts = [f for f in formats if f.get('vcodec', 'none') != 'none'
                          and f.get('height')]
            if video_fmts:
                height = max(f['height'] for f in video_fmts)
            elif info.get('height'):
                height = info['height']

            if not height:
                return '1080p'

            # Map height to standard tag
            for threshold, tag in [(2160, '2160p'), (1440, '1440p'),
                                    (1080, '1080p'), (720, '720p'),
                                    (480, '480p'), (360, '360p')]:
                if height >= threshold:
                    return tag
            return f'{height}p'

    except Exception as e:
        logger.debug(f'Resolution detection failed: {e}')
        return '1080p'


import urllib.parse
from Crypto.Cipher import AES

def resolve_variant_url(
    master_content: str,
    master_url: str,
    max_height: Optional[int] = None,
) -> str:
    """Parse HLS master playlist and return the best variant URL up to max_height."""
    lines = master_content.splitlines()
    variants: List[Tuple[int, int, str]] = []
    current_bandwidth = 0
    current_height = 0
    current_url = ""

    for line in lines:
        line = line.strip()
        if line.startswith("#EXT-X-STREAM-INF"):
            bw = re.search(r"BANDWIDTH=(\d+)", line)
            current_bandwidth = int(bw.group(1)) if bw else 0
            res = re.search(r"RESOLUTION=(\d+)x(\d+)", line)
            current_height = int(res.group(2)) if res else 0
        elif line and not line.startswith("#"):
            current_url = urllib.parse.urljoin(master_url, line)
            variants.append((current_height, current_bandwidth, current_url))

    if not variants:
        return master_url

    if max_height:
        capped = [v for v in variants if not v[0] or v[0] <= max_height]
        if capped:
            variants = capped

    variants.sort(key=lambda x: (x[0] or 0, x[1]), reverse=True)
    return variants[0][2]

def parse_m3u8(playlist_content: str, playlist_url: str) -> Tuple[List[str], Optional[Dict[str, Any]]]:
    """Parse HLS m3u8 playlist and extract segment URLs and decryption key info."""
    lines = playlist_content.splitlines()
    segment_urls: List[str] = []
    segment_keys: List[Optional[Dict[str, Any]]] = []
    current_key: Optional[Dict[str, Any]] = None
    media_sequence = 0
    segment_index = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("#EXT-X-MEDIA-SEQUENCE"):
            try:
                media_sequence = int(line.split(":", 1)[1].strip())
            except (IndexError, ValueError):
                media_sequence = 0
        elif line.startswith("#EXT-X-KEY"):
            parts = line.split(":", 1)[1]
            key_attrs = {}
            for part in re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', parts):
                if "=" in part:
                    k, v = part.split("=", 1)
                    key_attrs[k.strip()] = v.strip().replace('"', '')
            
            method = key_attrs.get("METHOD")
            if method == "AES-128" and key_attrs.get("URI"):
                current_key = {
                    "uri": urllib.parse.urljoin(playlist_url, key_attrs["URI"]),
                    "iv": key_attrs.get("IV")
                }
            elif method == "NONE":
                current_key = None
        elif not line.startswith("#"):
            segment_urls.append(urllib.parse.urljoin(playlist_url, line))
            if current_key:
                segment_keys.append({
                    **current_key,
                    "sequence": media_sequence + segment_index,
                })
            else:
                segment_keys.append(None)
            segment_index += 1

    keyed_segments = [k for k in segment_keys if k]
    key_info: Optional[Dict[str, Any]] = None
    if keyed_segments:
        first_key = keyed_segments[0]
        key_info = {
            "uri": first_key["uri"],
            "iv": first_key.get("iv"),
            "media_sequence": media_sequence,
            "segment_keys": segment_keys,
        }

    return segment_urls, key_info

def decrypt_segment(encrypted_data: bytes, key: bytes, sequence_number: int, key_iv: str = None) -> bytes:
    """Decrypt HLS segment using AES-128."""
    if key_iv:
        iv_hex = key_iv.replace("0x", "").strip()
        iv = bytes.fromhex(iv_hex)
    else:
        iv = sequence_number.to_bytes(16, byteorder="big")
        
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.decrypt(encrypted_data)

def _voyo_headers(auth: VoyoAuth) -> Dict[str, str]:
    headers = dict(auth.session.headers)
    headers.pop("Content-Type", None)
    headers["device-id"] = auth.state.device_id
    return headers


def _fetch_text(session, url: str, headers: Dict[str, str]) -> str:
    resp = session.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def download_native_resumable(
    m3u8_url: str,
    temp_stem: str,
    auth: VoyoAuth,
    title: str = "video",
    max_height: Optional[int] = None,
) -> Optional[str]:
    """
    Native HLS download with segment-level checkpoint resume.

    Segments live under ~/.videodownload/jobs/<id>/segments/hls/ so a failed
    job can continue without re-downloading completed pieces.
    """
    from backend.core.pipeline import JobCheckpoint, download_segments_resumable

    raise_if_cancelled()
    logger.info("Voyo native HLS (resumable segments): %s", title)

    headers = _voyo_headers(auth)
    session = auth.session
    output_path = Path(temp_stem + ".ts")

    # Fast resume: already-assembled TS for this title/url
    # (open checkpoint after we know final variant URL when possible)
    try:
        content = _fetch_text(session, m3u8_url, headers)
    except Exception as e:
        logger.error("Failed to fetch master playlist: %s", e)
        return None

    if "#EXT-X-STREAM-INF" in content:
        variant_url = resolve_variant_url(content, m3u8_url, max_height=max_height)
        logger.info("Resolved master playlist to variant: %s", variant_url)
        try:
            content = _fetch_text(session, variant_url, headers)
            m3u8_url = variant_url
        except Exception as e:
            logger.error("Failed to fetch variant playlist: %s", e)
            return None

    segments, key_info = parse_m3u8(content, m3u8_url)
    if not segments:
        logger.error("No HLS segments found in playlist.")
        return None
    logger.info("HLS variant: %s segments", len(segments))

    # AES-128 keys (cached in checkpoint meta as base64 for resume without re-fetch)
    cp = JobCheckpoint.open(
        service="voyo",
        mpd_url=m3u8_url,
        title=title or "voyo",
    )
    # Reuse previous assemble if still valid
    prev_ts = (cp.data.get("meta") or {}).get("assembled_ts") or ""
    if prev_ts:
        prev_path = Path(prev_ts)
        if prev_path.is_file() and prev_path.stat().st_size > 100_000:
            logger.info("Voyo: reuse assembled TS from checkpoint (%s)", prev_path.name)
            return str(prev_path)
    if output_path.is_file() and output_path.stat().st_size > 100_000:
        # Temp stem from previous interrupted mux attempt
        logger.info("Voyo: reuse existing temp TS %s", output_path.name)
        return str(output_path)
    key_cache: Dict[str, bytes] = {}
    meta_keys = (cp.data.get("meta") or {}).get("aes_keys") or {}
    for uri, b64 in meta_keys.items():
        try:
            key_cache[uri] = base64.b64decode(b64)
        except Exception:
            pass

    if key_info:
        segment_keys = key_info.get("segment_keys") or []
        key_uris = sorted({k["uri"] for k in segment_keys if k and k.get("uri")})
        logger.info("AES-128 stream — %s key URI(s)", len(key_uris))
        for key_uri in key_uris:
            if key_uri in key_cache:
                continue
            try:
                resp = session.get(key_uri, headers=headers, timeout=20)
                resp.raise_for_status()
                key_cache[key_uri] = resp.content
            except Exception as e:
                logger.error("Failed to fetch AES-128 key: %s", e)
                return None
        # Persist keys for resume
        meta = dict(cp.data.get("meta") or {})
        meta["aes_keys"] = {
            uri: base64.b64encode(raw).decode("ascii") for uri, raw in key_cache.items()
        }
        if key_info.get("segment_keys"):
            # lightweight serializable map for IV/sequence
            meta["segment_key_meta"] = [
                {
                    "uri": (sk or {}).get("uri"),
                    "iv": (sk or {}).get("iv"),
                    "sequence": (sk or {}).get("sequence"),
                }
                if sk
                else None
                for sk in key_info.get("segment_keys") or []
            ]
        cp.data["meta"] = meta
        cp.save()

    def progress(done: int, total: int) -> None:
        raise_if_cancelled()
        if total and (done == total or done % max(1, total // 20) == 0):
            logger.info("Voyo segments %s/%s (%.0f%%)", done, total, 100.0 * done / total)

    try:
        dest_paths = download_segments_resumable(
            segments,
            track="hls",
            checkpoint=cp,
            headers=headers,
            workers=16,
            progress=progress,
            session=session,
        )
    except Exception as e:
        logger.error("HLS segment download failed: %s", e)
        return None

    logger.info("Assembling and decrypting sequential TS…")
    segment_keys = (key_info or {}).get("segment_keys") or []
    # Prefer live key_info; fall back to checkpoint meta
    if not segment_keys and (cp.data.get("meta") or {}).get("segment_key_meta"):
        segment_keys = cp.data["meta"]["segment_key_meta"]

    try:
        with open(output_path, "wb") as out_f:
            for i, path in enumerate(dest_paths):
                raise_if_cancelled()
                if not path.exists():
                    logger.error("Segment %s missing after download", i)
                    output_path.unlink(missing_ok=True)
                    return None
                data = path.read_bytes()
                sk = segment_keys[i] if i < len(segment_keys) else None
                if sk and sk.get("uri"):
                    key_bytes = key_cache.get(sk["uri"])
                    if not key_bytes:
                        logger.error("Missing AES key for segment %s", i)
                        output_path.unlink(missing_ok=True)
                        return None
                    data = decrypt_segment(
                        data,
                        key_bytes,
                        int(sk.get("sequence", i)),
                        sk.get("iv"),
                    )
                out_f.write(data)
    except Exception as e:
        logger.error("Assemble/decrypt failed: %s", e)
        output_path.unlink(missing_ok=True)
        return None

    cp.set_output(output_path)
    # Keep segment files for potential re-mux; cleanup after successful mux in caller
    # Optionally prune on success via flag in meta
    cp.data.setdefault("meta", {})["assembled_ts"] = str(output_path)
    cp.save()
    return str(output_path)


async def download_native_async(
    m3u8_url: str,
    temp_stem: str,
    auth: VoyoAuth,
    title: str = 'video',
    max_height: Optional[int] = None,
) -> Optional[str]:
    """Backward-compatible wrapper → resumable native HLS."""
    return download_native_resumable(
        m3u8_url, temp_stem, auth, title, max_height=max_height
    )


def download_with_ytdlp(
    m3u8_url: str,
    temp_stem: str,
    auth: VoyoAuth,
    title: str = 'video',
    max_height: Optional[int] = None,
) -> Optional[str]:
    """
    Download HLS using resumable native segment engine, falling back to yt-dlp.
    """
    try:
        native_result = download_native_resumable(
            m3u8_url, temp_stem, auth, title, max_height=max_height
        )
        if native_result:
            return native_result
        logger.warning("Native resumable engine did not produce output. Falling back to yt-dlp...")
    except Exception as e:
        logger.error(f"Native resumable engine failed: {e}. Falling back to standard yt-dlp...")

    try:
        import yt_dlp
    except ImportError:
        logger.error('yt-dlp not installed. Run: pip install yt-dlp')
        return None

    headers = dict(auth.session.headers)
    headers.pop('Content-Type', None)
    headers['device-id'] = auth.state.device_id

    fmt = 'bestvideo+bestaudio/best'
    if max_height:
        fmt = f'bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best'

    ydl_opts = {
        'outtmpl':                       temp_stem + '.%(ext)s',
        'format':                        fmt,
        'http_headers':                  headers,
        'allow_unplayable_formats':      True,
        'continuedl':                    True,
        'retries':                       5,
        'fragment_retries':              10,
        'concurrent_fragment_downloads': 5,
        'updatetime':                    False,
        'quiet':                         False,
        'no_warnings':                   False,
        'progress_hooks':                [_progress_hook],
    }

    logger.info(f'Downloading: {title}')
    logger.info(f'  URL: {m3u8_url[:100]}...')

    try:
        fallback_started = time.time()
        Path(temp_stem + '.ts').unlink(missing_ok=True)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(m3u8_url, download=True)
            if info is None:
                return None
            filename = ydl.prepare_filename(info)

        prepared = Path(filename)
        if prepared.exists() and prepared.stat().st_mtime >= fallback_started - 1:
            return filename

        for ext in ['mp4', 'ts', 'mkv', 'm4a', 'webm', '']:
            candidate = temp_stem + (f'.{ext}' if ext else '')
            candidate_path = Path(candidate)
            if candidate_path.exists() and candidate_path.stat().st_mtime >= fallback_started - 1:
                return candidate
        return None
    except Exception as e:
        logger.error(f'yt-dlp error: {e}')
        return None


def _progress_hook(d: dict):
    raise_if_cancelled()
    if d['status'] == 'finished':
        logger.info("Post-processing...")
    elif d['status'] == 'downloading':
        pct   = d.get('_percent_str', '?%').strip()
        speed = d.get('_speed_str', '?').strip()
        eta   = d.get('_eta_str', '?').strip()
        logger.info(f"{pct}  speed={speed}  eta={eta}")


# ── mkvmerge mux ─────────────────────────────────────────────────────────────

def mux_to_mkv(input_path: str, output_path: str, title: str = '') -> bool:
    """Remux to MKV via mkvmerge. Falls back to rename if mkvmerge missing."""
    output = Path(output_path)
    tmp_output = temporary_media_path(output)

    if not MKVMERGE:
        logger.warning('mkvmerge not found — renaming to .mkv')
        try:
            shutil.move(input_path, tmp_output)
            if not _existing_output_is_complete(tmp_output):
                logger.error(f'Renamed output failed validation: {output.name}')
                tmp_output.unlink(missing_ok=True)
                return False
            tmp_output.replace(output)
            return True
        except Exception as e:
            logger.error(f'rename to mkv error: {e}')
            tmp_output.unlink(missing_ok=True)
            return False

    cmd = [MKVMERGE, '-o', str(tmp_output)]
    if title:
        cmd += ['--title', title]
    cmd.append(input_path)

    logger.info(f'Muxing → {Path(output_path).name}')
    try:
        result = run_subprocess(cmd, capture_output=True, text=True)
        if result.returncode in (0, 1):   # 0 = OK, 1 = warnings
            if not _existing_output_is_complete(tmp_output):
                logger.error(f'Muxed output failed validation: {output.name}')
                tmp_output.unlink(missing_ok=True)
                return False
            tmp_output.replace(output)
            Path(input_path).unlink(missing_ok=True)
            logger.info(f'✓ {Path(output_path).name}')
            return True
        logger.error(f'mkvmerge rc={result.returncode}: {result.stderr[:300]}')
        tmp_output.unlink(missing_ok=True)
        return False
    except Exception as e:
        logger.error(f'mkvmerge error: {e}')
        tmp_output.unlink(missing_ok=True)
        return False


# ── ID / URL parsing ─────────────────────────────────────────────────────────

def _parse_id(url: str) -> Optional[int]:
    s = url.strip()
    if s.isdigit():
        return int(s)
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(s).query)
    if 'id' in qs:
        try:
            return int(qs['id'][0])
        except (ValueError, IndexError):
            pass
    m = re.search(r'_(\d+)(?:\.html)?(?:\?|$|/)', s)
    if m:
        return int(m.group(1))
    m = re.search(r'_(\d+)$', s.rstrip('/').split('?')[0])
    if m:
        return int(m.group(1))
    return None


def _parse_episode_range(spec: str, total: int) -> Tuple[int, int]:
    spec = spec.strip()
    if '-' in spec:
        parts = spec.split('-', 1)
        start_s, end_s = parts[0].strip(), parts[1].strip()
        start = (int(start_s) - 1) if start_s else 0
        end   = int(end_s) if end_s else total
    else:
        n = int(spec)
        start, end = n - 1, n
    return max(0, start), min(total, end)


def _parse_episode_selection(spec: str, total: int) -> List[int]:
    """Return 0-based episode indices from specs like '1-3,5'."""
    spec = spec.strip()
    if not spec:
        return list(range(total))

    selected: List[int] = []
    seen = set()
    for part in (p.strip() for p in spec.split(',')):
        if not part:
            continue
        start, end = _parse_episode_range(part, total)
        for idx in range(start, end):
            if 0 <= idx < total and idx not in seen:
                seen.add(idx)
                selected.append(idx)
    return selected


# ── Main downloader ───────────────────────────────────────────────────────────

class VoyoDownloader:

    def __init__(self, auth: VoyoAuth, output_dir: str = './output',
                 resolution: str = '1080p'):
        self.auth       = auth
        self.output_dir = Path(output_dir)
        self.resolution = resolution
        self.temp_dir   = Path('./temp')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    # ── single video ─────────────────────────────────────────────────────────

    def download_video(self, video_id: int,
                       series_title: str = '',
                       output_stem: str = '') -> bool:
        """
        Download one video. Fetches metadata for SxxExx naming.

        Args:
            video_id:     Numeric video ID
            series_title: Series name from category (used in filename)
            output_stem:  Full filename stem override (no extension)
        """
        logger.info(f'Fetching stream URL for video {video_id}...')
        m3u8_url = ""
        try:
            from backend.core.pipeline import StreamResolve, with_api_refresh_sniffer

            def path_api():
                info = self.auth.get_video_url(video_id)
                probe = classify_url_info(info)
                if not probe.get("streamable"):
                    raise RuntimeError(probe.get("reason") or "stream unavailable")
                return StreamResolve(
                    mpd_url=info["url"],
                    license_url="",
                    title=str(video_id),
                    source="api",
                    meta={"url_info": info},
                )

            def path_refresh():
                # Re-link device (mandatory for videoUrlV2) then retry stream URL
                try:
                    self.auth.link_device()
                except Exception as relink_err:
                    logger.warning("Voyo device re-link: %s", relink_err)
                return path_api()

            resolved = with_api_refresh_sniffer(
                "voyo",
                api=path_api,
                refresh=path_refresh,
                require_license=False,
            )
            m3u8_url = resolved.mpd_url
            if resolved.source == "sniffer":
                logger.info("Voyo stream URL iz sniffera")
        except Exception as e:
            logger.error(f'Failed to get stream URL: {e}')
            return False

        if not m3u8_url:
            logger.error("Video %s: empty stream URL", video_id)
            return False

        # Fetch metadata for filename
        meta = {}
        if not output_stem:
            try:
                meta = self.auth.get_video_metadata(video_id)
            except Exception as e:
                logger.warning(f'Metadata fetch failed: {e}')

            # Detect actual resolution from the stream (overrides --resolution default)
            logger.info('Detecting stream resolution...')
            detected = detect_resolution(m3u8_url, self.auth)
            max_h = _resolution_max_height(self.resolution)
            det_h = _resolution_max_height(detected)
            if max_h and det_h and det_h > max_h:
                resolution = self.resolution
            else:
                resolution = detected
            logger.info(f'  Stream: {resolution} (limit {self.resolution})')

            output_stem = build_filename(
                meta, video_id, series_title, resolution)

        final_path_obj = self.output_dir / (output_stem + '.mkv')
        final_path = str(final_path_obj)
        if final_path_obj.exists():
            if _existing_output_is_complete(final_path_obj):
                logger.info(f'Already exists, skipping: {output_stem}.mkv')
                return True
            if not _move_incomplete_output(final_path_obj):
                return False

        temp_stem = str(self.temp_dir / f'voyo_{video_id}')
        logger.info(f'Output: {output_stem}.mkv')

        max_height = _resolution_max_height(self.resolution)
        downloaded = download_with_ytdlp(
            m3u8_url, temp_stem, self.auth, output_stem, max_height=max_height
        )
        if not downloaded:
            logger.error(f'Download failed for {video_id}')
            return False

        embed_title = meta.get('title', output_stem) if meta else output_stem
        ok = mux_to_mkv(downloaded, final_path, title=embed_title)
        if ok:
            # Free disk: drop resumable segment store for this stream
            try:
                from backend.core.pipeline import JobCheckpoint, purge_job_segments

                # Best-effort: open by known m3u8 + title stem used during download
                jid = None
                # Job id is stable for (voyo, m3u8, title) — title was output_stem
                from backend.core.pipeline.checkpoint import make_job_id

                jid = make_job_id("voyo", m3u8_url, output_stem or "voyo")
                purge_job_segments(jid)
            except Exception as purge_err:
                logger.debug("Voyo segment purge skipped: %s", purge_err)
        return ok

    def download_video_url(self, url: str) -> bool:
        vid_id = _parse_id(url)
        if not vid_id:
            logger.error(f'Cannot parse video ID from: {url}')
            return False
        return self.download_video(vid_id)

    # ── series ───────────────────────────────────────────────────────────────

    def _get_series(self, category_id: int) -> Tuple[List[Dict], str]:
        logger.info(f'Fetching episode list for category {category_id}...')
        try:
            cat = self.auth.get_category(category_id)
        except Exception as e:
            logger.error(f'Failed to fetch category: {e}')
            return [], ''
        items = cat.get('items', [])
        title = cat.get('title', f'series_{category_id}')
        logger.info(f'Series: "{title}" — {len(items)} episode(s)')
        return items, title

    def list_episodes(self, category_id: int):
        items, series_title = self._get_series(category_id)
        if not items:
            return
        logger.info("Series: %s  (%d episodes)", series_title, len(items))
        for i, ep in enumerate(items, 1):
            inner  = ep.get('meta', {})
            season = _parse_season_number(inner.get('season', ''))
            epnum  = inner.get('episode')
            mins   = ep.get('length', 0) // 60
            drm    = '[DRM]' if ep.get('drmProtected') else ''
            sub    = '[SUB]' if ep.get('hasSubtitles') else ''
            se     = f'S{season:02d}E{int(epnum):02d}' if epnum is not None else ''
            logger.info("  [%3d] %s%s %s  [%7s]  %s  (%dm)",
                        i, drm, sub, se, ep.get("id", "?"),
                        ep.get("title", "?"), mins)

    def download_series(self, category_id: int,
                        episode_range: str = '') -> Tuple[int, int]:
        items, series_title = self._get_series(category_id)
        if not items:
            return 0, 0

        try:
            selected_indices = _parse_episode_selection(episode_range, len(items))
        except ValueError as e:
            logger.error(f'Invalid episode range "{episode_range}": {e}')
            return 0, len(items)

        selected = [items[i] for i in selected_indices]
        total    = len(selected)
        logger.info(f'Downloading {total} episode(s) from "{series_title}"')

        success = 0
        for i, ep in enumerate(selected, 1):
            ep_id = ep.get('id')
            logger.info(f'[{i}/{total}] {ep.get("title", "?")} (id={ep_id})')
            ok = self.download_video(ep_id, series_title=series_title)
            if ok:
                success += 1
            else:
                logger.error(f'  ✗ Failed: {ep.get("title")}')
            if i < total:
                time.sleep(1)

        logger.info(f'Done: {success}/{total} downloaded')
        return success, total

    def download_series_url(self, url: str,
                            episode_range: str = '') -> Tuple[int, int]:
        cat_id = _parse_id(url)
        if not cat_id:
            logger.error(f'Cannot parse category ID from: {url}')
            return 0, 0
        return self.download_series(cat_id, episode_range)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Voyo.rs downloader — SxxExx naming, MKV output',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    cred = parser.add_argument_group('credentials')
    cred.add_argument('--save-credentials', action='store_true')
    cred.add_argument('-u', '--username', metavar='EMAIL')
    cred.add_argument('-p', '--password', metavar='PASS')

    cnt = parser.add_argument_group('content')
    cnt.add_argument('url', nargs='?', help='Voyo video or series page URL')
    cnt.add_argument('--video',    metavar='ID',    type=int)
    cnt.add_argument('--series',   metavar='ID',    type=int)
    cnt.add_argument('--episodes', metavar='RANGE', help='"1-3", "2-", "-5", "4"')
    cnt.add_argument('--list',     action='store_true', help='List episodes only')

    parser.add_argument('-o', '--output',     default='./output')
    parser.add_argument('--resolution',       default='1080p',
                        help='Resolution tag in filename (default: 1080p)')
    parser.add_argument('-v', '--verbose',    action='store_true')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    config = VoyoConfig()
    if args.save_credentials:
        if not args.username or not args.password:
            parser.error('--save-credentials requires -u and -p')
        config.set_credentials(args.username, args.password)
        print(f'✓ Credentials saved to {config.config_path}')

    email, password, device_id = config.get_credentials()
    if args.username: email    = args.username
    if args.password: password = args.password
    if not email or not password:
        parser.error('No credentials. Use -u/-p or --save-credentials first.')

    auth = VoyoAuth()
    if device_id:
        auth.state.device_id = device_id
        auth.session.headers['device-id'] = device_id

    try:
        auth.login(email, password)
        config.update_device_id(auth.state.device_id)
    except Exception as e:
        logger.error(f'Authentication failed: {e}')
        sys.exit(1)

    dl = VoyoDownloader(auth=auth, output_dir=args.output,
                        resolution=args.resolution)

    if args.list:
        cat_id = args.series or (args.url and _parse_id(args.url))
        if not cat_id:
            parser.error('--list requires --series <ID> or a series URL')
        dl.list_episodes(cat_id)
        return

    if args.video:
        sys.exit(0 if dl.download_video(args.video) else 1)

    if args.series:
        ok, total = dl.download_series(args.series, args.episodes or '')
        sys.exit(0 if ok == total else 1)

    if args.url:
        url = args.url
        if args.episodes:
            ok, total = dl.download_series_url(url, args.episodes)
            sys.exit(0 if ok == total else 1)

        vid_id = _parse_id(url)
        if vid_id:
            try:
                auth.get_video_url(vid_id)
                sys.exit(0 if dl.download_video(vid_id) else 1)
            except RuntimeError:
                logger.info('Not a single video — trying as series...')

        cat_id = _parse_id(url)
        if cat_id:
            ok, total = dl.download_series(cat_id, args.episodes or '')
            sys.exit(0 if ok > 0 else 1)

        logger.error(f'Cannot determine content type from: {url}')
        sys.exit(1)

    parser.print_help()


if __name__ == '__main__':
    main()
