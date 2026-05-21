"""
Voyo.rs Downloader Module
Downloads HLS streams from voyo.rs (AES-128, handled by yt-dlp).
"""

import logging
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .auth import VoyoAuth

logger = logging.getLogger(__name__)

RELEASE_GROUP = 'CrnaBerza'


def _find_tool(name: str, windows_hints: List[str] = None) -> Optional[str]:
    """Find tool in PATH or Windows common locations."""
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


def _sanitize(name: str) -> str:
    """Remove filesystem-invalid characters from filename."""
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip(' .')


def _parse_season_number(season_str) -> int:
    """Extract season number from string."""
    if not season_str:
        return 1
    m = re.search(r'(\d+)', str(season_str))
    return int(m.group(1)) if m else 1


def build_filename(meta: Dict[str, Any], video_id: int,
                   series_title: str = '', resolution: str = '1080p') -> str:
    """Build SxxExx filename from metadata."""
    inner = meta.get('meta', {})
    episode_num = inner.get('episode')
    season_str  = inner.get('season', '')
    year        = inner.get('year')

    if series_title:
        show = _sanitize(series_title)
    elif inner.get('originalTitle'):
        show = _sanitize(inner['originalTitle'])
    else:
        raw = meta.get('title', f'video_{video_id}')
        show = _sanitize(re.sub(r'\s+\d+$', '', raw).strip())

    tag = f'WEB-DL-{RELEASE_GROUP}'

    if episode_num is not None and int(episode_num) > 0:
        season_num = _parse_season_number(season_str)
        se = f'S{season_num:02d}E{int(episode_num):02d}'
        return f'{show}.{se}.{resolution}.{tag}'
    elif year:
        return f'{show}.{year}.{resolution}.{tag}'
    else:
        return f'{show}.{resolution}.{tag}'


def detect_resolution(m3u8_url: str, auth: VoyoAuth) -> str:
    """Probe m3u8 playlist and return resolution tag."""
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

            height = None
            formats = info.get('formats', [])
            video_fmts = [f for f in formats if f.get('vcodec', 'none') != 'none'
                          and f.get('height')]
            if video_fmts:
                height = max(f['height'] for f in video_fmts)
            elif info.get('height'):
                height = info['height']

            if not height:
                return '1080p'

            for threshold, tag in [(2160, '2160p'), (1440, '1440p'),
                                    (1080, '1080p'), (720, '720p'),
                                    (480, '480p'), (360, '360p')]:
                if height >= threshold:
                    return tag
            return f'{height}p'

    except Exception as e:
        logger.debug(f'Resolution detection failed: {e}')
        return '1080p'


def _progress_hook(d: dict):
    """Progress callback for yt-dlp."""
    if d['status'] == 'finished':
        print(f'\r  → Post-processing...                              ', flush=True)
    elif d['status'] == 'downloading':
        pct   = d.get('_percent_str', '?%').strip()
        speed = d.get('_speed_str', '?').strip()
        eta   = d.get('_eta_str', '?').strip()
        print(f'\r  {pct}  speed={speed}  eta={eta}  ', end='', flush=True)


def download_with_ytdlp(m3u8_url: str, temp_stem: str,
                         auth: VoyoAuth, title: str = 'video') -> Optional[str]:
    """Download HLS via yt-dlp to temp_stem.<ext>."""
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


def mux_to_mkv(input_path: str, output_path: str, title: str = '') -> bool:
    """Remux to MKV via mkvmerge."""
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
        if result.returncode in (0, 1):
            Path(input_path).unlink(missing_ok=True)
            logger.info(f'✓ {Path(output_path).name}')
            return True
        logger.error(f'mkvmerge rc={result.returncode}: {result.stderr[:300]}')
        return False
    except Exception as e:
        logger.error(f'mkvmerge error: {e}')
        return False


def _parse_id(url: str) -> Optional[int]:
    """Extract numeric ID from URL or string."""
    s = url.strip()
    if s.isdigit():
        return int(s)
    m = re.search(r'_(\d+)(?:\.html)?(?:\?|$|/)', s)
    if m:
        return int(m.group(1))
    m = re.search(r'_(\d+)$', s.rstrip('/').split('?')[0])
    if m:
        return int(m.group(1))
    return None


def _parse_episode_range(spec: str, total: int) -> Tuple[int, int]:
    """Parse episode range like '1-3', '2-', '-5'."""
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


class VoyoDownloader:
    """Handles Voyo.rs video downloads."""

    def __init__(self, auth: VoyoAuth, output_dir: str = './output',
                 resolution: str = '1080p'):
        self.auth       = auth
        self.output_dir = Path(output_dir)
        self.resolution = resolution
        self.temp_dir   = Path('./temp')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def download_video(self, video_id: int,
                       series_title: str = '',
                       output_stem: str = '') -> bool:
        """Download one video."""
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

        meta = {}
        if not output_stem:
            try:
                meta = self.auth.get_video_metadata(video_id)
            except Exception as e:
                logger.warning(f'Metadata fetch failed: {e}')

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
        """Download video from URL."""
        vid_id = _parse_id(url)
        if not vid_id:
            logger.error(f'Cannot parse video ID from: {url}')
            return False
        return self.download_video(vid_id)

    def _get_series(self, category_id: int) -> Tuple[List[Dict], str]:
        """Fetch episode list for a series."""
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
        """Print episode list."""
        items, series_title = self._get_series(category_id)
        if not items:
            return
        print(f'\nSeries: {series_title}  ({len(items)} episodes)\n')
        for i, ep in enumerate(items, 1):
            inner  = ep.get('meta', {})
            season = _parse_season_number(inner.get('season', ''))
            epnum  = inner.get('episode')
            mins   = ep.get('length', 0) // 60
            drm    = '🔒' if ep.get('drmProtected') else '  '
            sub    = '📄' if ep.get('hasSubtitles') else '  '
            se     = f'S{season:02d}E{int(epnum):02d}' if epnum is not None else '      '
            print(f'  [{i:3d}] {drm}{sub} {se}  [{ep["id"]:>7}]  '
                  f'{ep.get("title", "?"):<40}  ({mins}m)')
        print()

    def download_series(self, category_id: int,
                        episode_range: str = '') -> Tuple[int, int]:
        """Download series episodes."""
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
        """Download series from URL."""
        cat_id = _parse_id(url)
        if not cat_id:
            logger.error(f'Cannot parse category ID from: {url}')
            return 0, 0
        return self.download_series(cat_id, episode_range)
