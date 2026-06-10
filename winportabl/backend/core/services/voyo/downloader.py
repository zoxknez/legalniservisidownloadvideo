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
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from .auth import VoyoAuth, VoyoConfig

logger = logging.getLogger(__name__)

requests.packages.urllib3.disable_warnings()

RELEASE_GROUP = 'VOYO'


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

def resolve_variant_url(master_content: str, master_url: str) -> str:
    """Parse HLS master playlist and return the best quality variant URL."""
    lines = master_content.splitlines()
    variants = []
    current_bandwidth = 0
    current_url = ""
    
    for line in lines:
        line = line.strip()
        if line.startswith("#EXT-X-STREAM-INF"):
            m = re.search(r"BANDWIDTH=(\d+)", line)
            current_bandwidth = int(m.group(1)) if m else 0
        elif line and not line.startswith("#"):
            current_url = urllib.parse.urljoin(master_url, line)
            variants.append((current_bandwidth, current_url))
            
    if variants:
        variants.sort(key=lambda x: x[0], reverse=True)
        return variants[0][1]
        
    return master_url

def parse_m3u8(playlist_content: str, playlist_url: str) -> Tuple[List[str], Optional[Dict[str, Any]]]:
    """Parse HLS m3u8 playlist and extract segment URLs and decryption key info."""
    lines = playlist_content.splitlines()
    segment_urls = []
    key_info = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("#EXT-X-KEY"):
            parts = line.split(":", 1)[1]
            key_attrs = {}
            for part in re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', parts):
                if "=" in part:
                    k, v = part.split("=", 1)
                    key_attrs[k.strip()] = v.strip().replace('"', '')
            
            if key_attrs.get("METHOD") == "AES-128":
                key_info = {
                    "uri": urllib.parse.urljoin(playlist_url, key_attrs["URI"]),
                    "iv": key_attrs.get("IV")
                }
        elif not line.startswith("#"):
            segment_urls.append(urllib.parse.urljoin(playlist_url, line))
            
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

async def download_native_async(m3u8_url: str, temp_stem: str, auth: VoyoAuth, title: str = 'video') -> Optional[str]:
    """Download HLS natively using asynchronous connection pool and parallel workers."""
    from backend.core.services.async_engine import AsyncDownloadEngine
    import aiohttp
    
    logger.info(f"Using high-performance native HLS async engine for: {title}")
    
    headers = dict(auth.session.headers)
    headers.pop('Content-Type', None)
    headers['device-id'] = auth.state.device_id
    
    connector = aiohttp.TCPConnector(limit=16, force_close=False, enable_cleanup_closed=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        # 1. Fetch playlist content
        async with session.get(m3u8_url, headers=headers) as resp:
            if resp.status != 200:
                logger.error(f"Failed to fetch master playlist: HTTP {resp.status}")
                return None
            content = await resp.text()
            
        # 2. Handle master playlist variants
        if "#EXT-X-STREAM-INF" in content:
            variant_url = resolve_variant_url(content, m3u8_url)
            logger.info(f"Resolved master playlist to variant: {variant_url}")
            async with session.get(variant_url, headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch variant playlist: HTTP {resp.status}")
                    return None
                content = await resp.text()
                m3u8_url = variant_url
                
        # 3. Parse segments and keys
        segments, key_info = parse_m3u8(content, m3u8_url)
        if not segments:
            logger.error("No HLS segments found in playlist.")
            return None
            
        logger.info(f"HLS Variant parsed: {len(segments)} segments detected.")
        
        # 4. Fetch AES key
        key_bytes = None
        if key_info:
            logger.info(f"Stream is AES-128 encrypted. Fetching key from: {key_info['uri']}")
            async with session.get(key_info["uri"], headers=headers) as resp:
                if resp.status == 200:
                    key_bytes = await resp.read()
                else:
                    logger.error(f"Failed to fetch AES-128 decryption key: HTTP {resp.status}")
                    return None
                    
        # 5. Prepare temp segments folder
        temp_dir = Path(temp_stem).parent / f"hls_temp_{int(time.time())}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        dest_paths = [temp_dir / f"seg_{i:05d}.ts" for i in range(len(segments))]
        
        # 6. Initialize AsyncDownloadEngine
        engine = AsyncDownloadEngine(max_workers=16)
        
        # Real-time progress tracker with speed/ETA in yt-dlp format
        start_time = time.monotonic()
        total_estimated_bytes = len(segments) * 1.5 * 1024 * 1024  # estimate 1.5MB per segment
        
        def progress_callback(downloaded_bytes, total_bytes):
            pct = (downloaded_bytes / total_bytes) * 100 if total_bytes > 0 else 0
            if pct > 100: pct = 100.0
            elapsed = time.monotonic() - start_time
            speed_bps = downloaded_bytes / elapsed if elapsed > 0 else 0
            speed_str = f"{speed_bps / (1024*1024):.2f}MiB/s"
            eta_sec = (total_bytes - downloaded_bytes) / speed_bps if speed_bps > 0 else 0
            eta_str = f"{int(eta_sec)}s" if eta_sec < 3600 else f"{int(eta_sec/3600)}h{int((eta_sec%3600)/60)}m"
            logger.info(f"Download {pct:.1f}%  speed={speed_str}  eta={eta_str}")

        logger.info(f"Downloading {len(segments)} segments concurrently...")
        success = await engine.download_segments(
            urls=segments,
            dest_paths=dest_paths,
            headers=headers,
            progress_callback=progress_callback
        )
        
        if not success:
            logger.error("HLS segment download failed.")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None
            
        # 7. Decrypt & assemble sequential file block
        output_ts = temp_stem + ".ts"
        logger.info("Assembling and decrypting sequential TS file...")
        
        with open(output_ts, "wb") as out_f:
            for i, path in enumerate(dest_paths):
                if not path.exists():
                    logger.error(f"Decryption failed: segment {i} file missing!")
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return None
                    
                with open(path, "rb") as seg_f:
                    data = seg_f.read()
                    
                if key_bytes:
                    decrypted_data = decrypt_segment(data, key_bytes, i, key_info.get("iv"))
                    out_f.write(decrypted_data)
                else:
                    out_f.write(data)
                    
        # Cleanup segments
        shutil.rmtree(temp_dir, ignore_errors=True)
        return output_ts

def download_with_ytdlp(m3u8_url: str, temp_stem: str,
                         auth: VoyoAuth, title: str = 'video') -> Optional[str]:
    """
    Download HLS using native parallel async engine, falling back to yt-dlp if needed.
    """
    import asyncio
    try:
        return asyncio.run(download_native_async(m3u8_url, temp_stem, auth, title))
    except Exception as e:
        logger.error(f"Native async engine failed: {e}. Falling back to standard yt-dlp...")

    try:
        import yt_dlp
    except ImportError:
        logger.error('yt-dlp not installed. Run: pip install yt-dlp')
        return None

    headers = dict(auth.session.headers)
    headers.pop('Content-Type', None)
    headers['device-id'] = auth.state.device_id

    ydl_opts = {
        'outtmpl':                       temp_stem + '.%(ext)s',
        'format':                        'bestvideo+bestaudio/best',
        'http_headers':                  headers,
        'allow_unplayable_formats':      True,
        'continuedl':                    True,
        'retries':                       5,
        'fragment_retries':              10,
        'concurrent_fragment_downloads': 5,
        'quiet':                         False,
        'no_warnings':                   False,
        'progress_hooks':                [_progress_hook],
    }

    logger.info(f'Downloading: {title}')
    logger.info(f'  URL: {m3u8_url[:100]}...')

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(m3u8_url, download=True)
            if info is None:
                return None
            filename = ydl.prepare_filename(info)

        for ext in ['mp4', 'ts', 'mkv', 'm4a', 'webm', '']:
            candidate = temp_stem + (f'.{ext}' if ext else '')
            if Path(candidate).exists():
                return candidate
        if Path(filename).exists():
            return filename
        return None
    except Exception as e:
        logger.error(f'yt-dlp error: {e}')
        return None


def _progress_hook(d: dict):
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
    if not MKVMERGE:
        logger.warning('mkvmerge not found — renaming to .mkv')
        shutil.move(input_path, output_path)
        return True

    cmd = [MKVMERGE, '-o', output_path]
    if title:
        cmd += ['--title', title]
    cmd.append(input_path)

    logger.info(f'Muxing → {Path(output_path).name}')
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode in (0, 1):   # 0 = OK, 1 = warnings
            Path(input_path).unlink(missing_ok=True)
            logger.info(f'✓ {Path(output_path).name}')
            return True
        logger.error(f'mkvmerge rc={result.returncode}: {result.stderr[:300]}')
        return False
    except Exception as e:
        logger.error(f'mkvmerge error: {e}')
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
        try:
            url_info = self.auth.get_video_url(video_id)
        except Exception as e:
            logger.error(f'Failed to get stream URL: {e}')
            return False

        info_code = url_info.get('infoCode', 0)
        if info_code != 0:
            logger.error(f'Stream not available (infoCode={info_code}): '
                         f'{url_info.get("info", "")}')
            return False

        m3u8_url = url_info['url']

        # Fetch metadata for filename
        meta = {}
        if not output_stem:
            try:
                meta = self.auth.get_video_metadata(video_id)
            except Exception as e:
                logger.warning(f'Metadata fetch failed: {e}')

            # Detect actual resolution from the stream (overrides --resolution default)
            logger.info('Detecting stream resolution...')
            resolution = detect_resolution(m3u8_url, self.auth)
            logger.info(f'  Detected: {resolution}')

            output_stem = build_filename(
                meta, video_id, series_title, resolution)

        final_path = str(self.output_dir / (output_stem + '.mkv'))
        if Path(final_path).exists():
            logger.info(f'Already exists, skipping: {output_stem}.mkv')
            return True

        temp_stem = str(self.temp_dir / f'voyo_{video_id}')
        logger.info(f'Output: {output_stem}.mkv')

        downloaded = download_with_ytdlp(m3u8_url, temp_stem,
                                          self.auth, output_stem)
        if not downloaded:
            logger.error(f'Download failed for {video_id}')
            return False

        embed_title = meta.get('title', output_stem) if meta else output_stem
        return mux_to_mkv(downloaded, final_path, title=embed_title)

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

        start, end = 0, len(items)
        if episode_range:
            start, end = _parse_episode_range(episode_range, len(items))

        selected = items[start:end]
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
