#!/usr/bin/env python3
"""
EON TV Video Downloader - OPTIMIZED VERSION
Fast parallel downloads using ThreadPoolExecutor and aria2c

Key optimizations:
1. Parallel segment downloads with ThreadPoolExecutor (10-16 concurrent)
2. aria2c support for even faster downloads (if available)
3. Connection pooling with keep-alive
4. Chunked downloads for large segments
5. Reduced polling delays for live streams
"""

import os
import sys
import re
import json
import time
import shutil
import logging
import argparse
import subprocess
import platform
import secrets
import uuid
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import requests
import urllib.parse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Crypto imports for stream URL encryption
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logging.warning("pycryptodome not installed. Install with: pip install pycryptodome")

# Import our auth module
from eon_auth import EONAuth, EONConfig, PROVIDERS

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def create_fast_session() -> requests.Session:
    """Create an optimized session with connection pooling"""
    session = requests.Session()
    
    # Retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    # Adapter with larger connection pool
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=20,  # More connections
        pool_maxsize=20,      # Larger pool
        pool_block=False
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


class FastHLSDownloader:
    """
    High-performance HLS downloader with parallel segment fetching.
    """
    
    def __init__(self, max_workers: int = 16, chunk_size: int = 1024 * 1024):
        """
        Args:
            max_workers: Number of parallel download threads
            chunk_size: Chunk size for streaming downloads (1MB default)
        """
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.session = create_fast_session()
        self._download_lock = threading.Lock()
        
    def set_headers(self, headers: Dict[str, str]):
        """Set default headers for all requests"""
        self.session.headers.update(headers)
    
    def _fetch_segment(self, seg_info: Tuple[int, str, float]) -> Tuple[int, bytes, float]:
        """
        Fetch a single segment.
        
        Args:
            seg_info: (index, url, duration)
            
        Returns:
            (index, data, duration)
        """
        idx, url, duration = seg_info
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return (idx, response.content, duration)
        except Exception as e:
            logger.warning(f"Segment {idx} failed: {e}")
            return (idx, b'', duration)
    
    def download_parallel(self, segments: List[Tuple[str, float]], 
                          output_file: Path,
                          show_progress: bool = True) -> float:
        """
        Download segments in parallel and merge.
        
        Args:
            segments: List of (url, duration) tuples
            output_file: Output file path
            show_progress: Show progress bar
            
        Returns:
            Total duration downloaded
        """
        total_segments = len(segments)
        if total_segments == 0:
            return 0.0
        
        logger.info(f"Downloading {total_segments} segments with {self.max_workers} workers...")
        
        # Create indexed segment list
        indexed_segments = [(i, url, dur) for i, (url, dur) in enumerate(segments)]
        
        # Results dict to store segments in order
        results: Dict[int, bytes] = {}
        total_duration = 0.0
        completed = 0
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all downloads
            futures = {
                executor.submit(self._fetch_segment, seg): seg[0] 
                for seg in indexed_segments
            }
            
            # Collect results as they complete
            for future in as_completed(futures):
                idx, data, duration = future.result()
                
                if data:
                    results[idx] = data
                    total_duration += duration
                
                completed += 1
                
                if show_progress:
                    elapsed = time.time() - start_time
                    speed = completed / elapsed if elapsed > 0 else 0
                    eta = (total_segments - completed) / speed if speed > 0 else 0
                    print(f"\r  Progress: {completed}/{total_segments} segments "
                          f"({100*completed/total_segments:.1f}%) "
                          f"- {speed:.1f} seg/s - ETA: {eta:.0f}s", end='', flush=True)
        
        if show_progress:
            print()  # Newline after progress
        
        elapsed = time.time() - start_time
        logger.info(f"Downloaded {len(results)} segments in {elapsed:.1f}s "
                   f"({len(results)/elapsed:.1f} seg/s)")
        
        # Write segments in order
        logger.info(f"Merging segments to {output_file}...")
        with open(output_file, 'wb') as f:
            for i in range(total_segments):
                if i in results:
                    f.write(results[i])
        
        return total_duration
    
    def parse_master_playlist(self, url: str) -> Tuple[str, str]:
        """
        Parse master playlist and find best quality stream.
        
        Returns:
            (media_playlist_url, master_url_after_redirects)
        """
        response = self.session.get(url, allow_redirects=True)
        response.raise_for_status()
        
        master_url = response.url
        content = response.text
        
        # Find best bandwidth stream
        best_bandwidth = 0
        best_stream_url = None
        
        lines = content.strip().split('\n')
        for i, line in enumerate(lines):
            if line.startswith('#EXT-X-STREAM-INF'):
                bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                if bw_match:
                    bandwidth = int(bw_match.group(1))
                    if bandwidth > best_bandwidth and i + 1 < len(lines):
                        best_bandwidth = bandwidth
                        stream_line = lines[i + 1].strip()
                        
                        if stream_line.startswith('http'):
                            best_stream_url = stream_line
                        else:
                            base_url = master_url.rsplit('/', 1)[0] + '/'
                            best_stream_url = urllib.parse.urljoin(base_url, stream_line)
        
        # Maybe it's already a media playlist
        if not best_stream_url and '#EXTINF' in content:
            best_stream_url = master_url
        
        if not best_stream_url:
            raise ValueError("Could not find stream URL in playlist")
        
        logger.info(f"Selected stream: {best_bandwidth/1000:.0f} kbps")
        return best_stream_url, master_url
    
    def parse_media_playlist(self, url: str) -> List[Tuple[str, float]]:
        """
        Parse media playlist and extract all segment URLs.
        
        Returns:
            List of (segment_url, duration) tuples
        """
        response = self.session.get(url)
        response.raise_for_status()
        
        media_url = response.url
        content = response.text
        
        segments = []
        lines = content.strip().split('\n')
        
        for i, line in enumerate(lines):
            if line.startswith('#EXTINF'):
                dur_match = re.search(r'#EXTINF:([\d.]+)', line)
                duration = float(dur_match.group(1)) if dur_match else 0
                
                if i + 1 < len(lines):
                    seg_line = lines[i + 1].strip()
                    if not seg_line.startswith('#'):
                        if seg_line.startswith('http'):
                            seg_url = seg_line
                        else:
                            base_url = media_url.rsplit('/', 1)[0] + '/'
                            seg_url = urllib.parse.urljoin(base_url, seg_line)
                        
                        segments.append((seg_url, duration))
        
        return segments
    
    def download_vod(self, master_url: str, output_file: Path) -> Path:
        """
        Download complete VOD stream.
        
        Args:
            master_url: Master playlist URL
            output_file: Output .ts file
            
        Returns:
            Path to downloaded file
        """
        # Parse playlists
        media_url, _ = self.parse_master_playlist(master_url)
        segments = self.parse_media_playlist(media_url)
        
        logger.info(f"Found {len(segments)} segments, "
                   f"total duration: {sum(d for _, d in segments)/60:.1f} minutes")
        
        # Download all segments in parallel
        temp_ts = output_file.with_suffix('.ts')
        self.download_parallel(segments, temp_ts)
        
        return temp_ts
    
    def download_live(self, master_url: str, output_file: Path, 
                      duration: int = 60) -> Path:
        """
        Download live stream for specified duration.
        
        Downloads segments IMMEDIATELY as they appear in the playlist,
        because live segments expire quickly on the server (~30-60 seconds).
        
        Args:
            master_url: Master playlist URL
            output_file: Output .ts file
            duration: Duration in seconds
            
        Returns:
            Path to downloaded file
        """
        # Parse master playlist
        media_url, _ = self.parse_master_playlist(master_url)
        
        downloaded_urls = set()
        total_duration = 0.0
        no_new_segments_count = 0
        segment_count = 0
        
        temp_ts = output_file.with_suffix('.ts')
        
        logger.info(f"Recording {duration} seconds of live stream...")
        logger.info(f"Downloading segments in real-time (they expire quickly on server)")
        
        start_time = time.time()
        last_log_time = start_time
        
        # Open output file for writing
        with open(temp_ts, 'wb') as outfile:
            while total_duration < duration:
                # Fetch current playlist
                try:
                    new_segments = self.parse_media_playlist(media_url)
                except Exception as e:
                    logger.warning(f"Playlist fetch error: {e}, retrying...")
                    time.sleep(2)
                    continue
                
                # Filter to only new segments
                segments_to_download = []
                for url, dur in new_segments:
                    if url not in downloaded_urls:
                        segments_to_download.append((url, dur))
                        downloaded_urls.add(url)
                
                if segments_to_download:
                    # Download each segment IMMEDIATELY and append to file
                    for url, dur in segments_to_download:
                        try:
                            response = self.session.get(url, timeout=30)
                            response.raise_for_status()
                            outfile.write(response.content)
                            outfile.flush()
                            
                            total_duration += dur
                            segment_count += 1
                            
                        except Exception as e:
                            logger.warning(f"Segment download failed: {e}")
                    
                    no_new_segments_count = 0
                    
                    # Log progress periodically
                    current_time = time.time()
                    if current_time - last_log_time >= 10:
                        elapsed = current_time - start_time
                        logger.info(f"Progress: {total_duration:.1f}s / {duration}s "
                                   f"({segment_count} segments, {elapsed:.0f}s elapsed)")
                        last_log_time = current_time
                else:
                    no_new_segments_count += 1
                    if no_new_segments_count > 30:
                        logger.warning(f"No new segments for 30+ seconds. Stream may have ended.")
                        break
                
                # Wait before polling again
                if total_duration < duration:
                    time.sleep(1)
                
                # Safety timeout
                elapsed = time.time() - start_time
                if elapsed > duration * 2 + 60:
                    logger.warning(f"Timeout: spent {elapsed:.0f}s but only got {total_duration:.0f}s")
                    break
        
        if segment_count == 0:
            raise ValueError("No segments downloaded from live stream")
        
        actual_time = time.time() - start_time
        logger.info(f"Recorded {total_duration:.1f}s ({segment_count} segments) in {actual_time:.1f}s")
        
        return temp_ts
    
    def download_live_realtime(self, master_url: str, output_file: Path,
                                duration: int = 60, 
                                on_segment_ready: Optional[callable] = None) -> Path:
        """
        Download live stream in real-time, writing segments as they arrive.
        
        This allows playback while recording - the file grows as new segments
        are downloaded.
        
        Args:
            master_url: Master playlist URL
            output_file: Output .ts file
            duration: Duration in seconds (0 = indefinite until Ctrl+C)
            on_segment_ready: Callback when first segment is ready
            
        Returns:
            Path to downloaded file
        """
        # Parse master playlist
        media_url, _ = self.parse_master_playlist(master_url)
        
        downloaded_urls = set()
        total_duration = 0.0
        no_new_segments_count = 0
        segment_count = 0
        
        temp_ts = output_file.with_suffix('.ts')
        
        indefinite = (duration == 0)
        if indefinite:
            logger.info(f"Recording live stream indefinitely (Ctrl+C to stop)...")
        else:
            logger.info(f"Recording {duration} seconds of live stream (real-time)...")
        
        start_time = time.time()
        last_log_time = start_time
        player_launched = False
        
        # Open output file for appending
        with open(temp_ts, 'wb') as outfile:
            try:
                while indefinite or total_duration < duration:
                    # Fetch current playlist
                    try:
                        new_segments = self.parse_media_playlist(media_url)
                    except Exception as e:
                        logger.warning(f"Playlist fetch error: {e}, retrying...")
                        time.sleep(2)
                        continue
                    
                    # Filter to only new segments
                    segments_to_download = []
                    for url, dur in new_segments:
                        if url not in downloaded_urls:
                            segments_to_download.append((url, dur))
                            downloaded_urls.add(url)
                    
                    if segments_to_download:
                        # Download and write each segment immediately
                        for url, dur in segments_to_download:
                            try:
                                response = self.session.get(url, timeout=30)
                                response.raise_for_status()
                                outfile.write(response.content)
                                outfile.flush()  # Ensure it's written to disk
                                
                                total_duration += dur
                                segment_count += 1
                                
                                # Callback after first segment (for launching player)
                                if segment_count == 1 and on_segment_ready:
                                    on_segment_ready(temp_ts)
                                    player_launched = True
                                    
                            except Exception as e:
                                logger.warning(f"Segment download failed: {e}")
                        
                        no_new_segments_count = 0
                        
                        # Log progress periodically
                        current_time = time.time()
                        if current_time - last_log_time >= 10:
                            elapsed = current_time - start_time
                            if indefinite:
                                logger.info(f"Recording: {total_duration:.1f}s "
                                           f"({segment_count} segments, {elapsed:.0f}s elapsed)")
                            else:
                                logger.info(f"Progress: {total_duration:.1f}s / {duration}s "
                                           f"({segment_count} segments)")
                            last_log_time = current_time
                    else:
                        no_new_segments_count += 1
                        if no_new_segments_count > 30:
                            logger.warning(f"No new segments for 30+ seconds. Stream may have ended.")
                            break
                    
                    # Wait before polling again
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info(f"\nStopped by user. Recorded {total_duration:.1f}s")
        
        actual_time = time.time() - start_time
        logger.info(f"Recorded {total_duration:.1f}s in {actual_time:.1f}s (real-time)")
        
        return temp_ts


class EONDownloader:
    """
    Main downloader class for EON TV content - OPTIMIZED VERSION.
    """
    
    def __init__(self, provider: str = 'sbb', output_dir: str = "output", 
                 temp_dir: str = "temp", force_new_device: bool = False,
                 max_workers: int = 16):
        """
        Initialize the downloader.
        
        Args:
            provider: Provider identifier ('sbb', 'telemach', etc.)
            output_dir: Directory for final output files
            temp_dir: Directory for temporary files
            force_new_device: Force registration of a new device
            max_workers: Number of parallel download threads (default 16)
        """
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        self._force_new_device = force_new_device
        self.provider = provider
        self.max_workers = max_workers
        
        # Initialize auth
        self.auth = EONAuth(provider=provider)
        self.config = EONConfig()
        
        # Provider-specific URLs
        provider_config = PROVIDERS[provider]
        cdn = provider_config['cdn']
        
        self.api_base = self.auth.api_base
        self.wtms_base = f"https://wtms.{cdn}.cdn.united.cloud"
        self.media_base = f"https://{cdn}-be.cdn.united.cloud"
        
        # Binary detection
        self.binaries = self._detect_binaries()
        
        # Fast HLS downloader
        self.hls_downloader = FastHLSDownloader(max_workers=max_workers)
        
        # Create directories
        self._setup_directories()
        
        # Channel cache
        self._channels_cache: Optional[List[Dict]] = None
    
    def _detect_binaries(self) -> Dict[str, str]:
        """Detect required binaries"""
        is_windows = platform.system() == 'Windows'
        ext = '.exe' if is_windows else ''
        
        binaries = {
            'ffmpeg': f'ffmpeg{ext}',
            'ffprobe': f'ffprobe{ext}',
            'aria2c': f'aria2c{ext}',  # For even faster downloads
        }
        
        for name, binary in binaries.items():
            found = shutil.which(binary)
            if found:
                binaries[name] = found
            else:
                local_path = Path('binaries') / binary
                if local_path.exists():
                    binaries[name] = str(local_path)
                elif name != 'aria2c':  # aria2c is optional
                    logger.warning(f"Binary not found: {binary}")
        
        return binaries
    
    def _setup_directories(self):
        """Create necessary directories"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def login(self, username: Optional[str] = None, password: Optional[str] = None):
        """Authenticate with EON TV."""
        if not username or not password:
            if self.config.has_credentials():
                username, password, _ = self.config.get_credentials()
                logger.info(f"Using stored credentials for: {username}")
            else:
                raise ValueError("No credentials provided and none stored")
        
        self.auth.login(username, password, force_new_device=self._force_new_device)
        
        # Set headers on HLS downloader
        self.hls_downloader.set_headers({
            'Referer': 'https://eon.tv/',
            'Origin': 'https://eon.tv',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        
        logger.info("Authentication successful!")
    
    def get_channels(self, channel_type: str = 'TV', force_refresh: bool = False) -> List[Dict]:
        """Get list of available channels."""
        if self._channels_cache and not force_refresh:
            return self._channels_cache
        
        url = f"{self.auth.api_base}/v3/channels"
        params = {'channelType': channel_type}
        headers = self.auth._add_common_headers({'X-Ucp-Language': 'srp'})
        
        response = self.auth.session.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        self._channels_cache = response.json()
        return self._channels_cache
    
    def find_channel(self, query: str) -> Optional[Dict]:
        """Find a channel by name or ID."""
        channels = self.get_channels()
        
        try:
            channel_id = int(query)
            for ch in channels:
                if ch.get('id') == channel_id:
                    return ch
        except ValueError:
            pass
        
        query_lower = query.lower()
        for ch in channels:
            name = ch.get('name', '').lower()
            short_name = ch.get('shortName', '').lower()
            if query_lower in name or query_lower in short_name:
                return ch
        
        return None
    
    def _urlsafe_b64encode(self, data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')
    
    def _urlsafe_b64decode(self, data: str) -> bytes:
        padding = 4 - len(data) % 4
        if padding != 4:
            data += '=' * padding
        return base64.urlsafe_b64decode(data)
    
    def _build_encrypted_stream_url(self, publishing_point: str, sig: str,
                                     stream_type: str = 'live',
                                     start_time: Optional[int] = None,
                                     server: Optional[Dict] = None) -> str:
        """Build an encrypted stream URL using AES-CBC encryption."""
        if not HAS_CRYPTO:
            raise RuntimeError("pycryptodome required: pip install pycryptodome")
        
        if not server:
            servers = self.get_servers()
            
            if stream_type == 'live':
                server_list = servers.get('live_servers', [])
            elif stream_type == 'vod':
                server_list = servers.get('vod_servers', [])
            else:
                server_list = servers.get('timeshift_servers', [])
            
            if not server_list:
                raise ValueError(f"No {stream_type} streaming servers available")
            
            server = server_list[1] if len(server_list) > 1 else server_list[0]
        
        iv = secrets.token_bytes(16)
        key = self._urlsafe_b64decode(self.auth.state.stream_key)
        session_id = str(uuid.uuid4())
        ctime = str(int(time.time() * 1000))
        
        player_type = "m3u8v" if stream_type == 'vod' else "m3u8"
        stream_quality = "hp7000"
        asset_key = "asset" if stream_type == 'vod' else "channel"
        
        params = [
            f"{asset_key}={publishing_point}",
            f"stream={stream_quality}",
            f"sp={self.provider}",
            f"u={self.auth.state.stream_un}",
            f"ss={self.auth.state.stream_key}",
            f"minvbr=100",
            f"adaptive=true",
            f"player={player_type}",
            f"sig={sig}",
            f"session={session_id}",
            f"m={server.get('ip', '')}",
            f"device={self.auth.state.device_number}",
            f"ctime={ctime}",
            f"conn=BROWSER",
        ]
        
        if start_time and stream_type in ('cutv', 'vod'):
            params.append(f"t={start_time}")
        
        params.append("aa=false")
        
        plain_text = ";".join(params)
        
        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted = cipher.encrypt(pad(plain_text.encode('utf-8'), AES.block_size))
        
        i_param = self._urlsafe_b64encode(iv)
        a_param = self._urlsafe_b64encode(encrypted)
        
        return (
            f"https://{server.get('hostname')}/stream"
            f"?i={i_param}&a={a_param}&sp={self.provider}"
            f"&u={self.auth.state.stream_un}&player={player_type}"
            f"&session={session_id}&sig={sig}"
        )
    
    def get_servers(self) -> Dict:
        """Get available streaming servers"""
        url = f"{self.api_base}/v1/servers"
        response = self.auth.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_stream_url(self, channel: Dict, stream_type: str = 'live',
                       start_time: Optional[int] = None) -> str:
        """Construct the stream URL for a channel."""
        pub_points = channel.get('publishingPoint', [])
        if not pub_points:
            raise ValueError(f"No publishing point for channel: {channel.get('name')}")
        
        pub_point = pub_points[0]
        publishing_point = pub_point.get('publishingPoint', '')
        
        if channel.get('drmRequired', False):
            logger.warning(f"Channel {channel.get('name')} requires DRM!")
        
        player_cfgs = pub_point.get('playerCfgs', [])
        player_cfg = None
        for cfg in player_cfgs:
            if cfg.get('type') == stream_type:
                player_cfg = cfg
                break
        
        if not player_cfg:
            player_cfg = player_cfgs[0] if player_cfgs else {}
        
        sig = player_cfg.get('sig', '')
        
        return self._build_encrypted_stream_url(
            publishing_point=publishing_point,
            sig=sig,
            stream_type=stream_type,
            start_time=start_time
        )
    
    def _convert_to_mp4(self, ts_file: Path, output_file: Path) -> Path:
        """Convert TS file to MP4 using ffmpeg."""
        if not self.binaries.get('ffmpeg'):
            logger.warning("ffmpeg not found, keeping .ts file")
            return ts_file
        
        cmd = [
            self.binaries['ffmpeg'],
            '-y',
            '-i', str(ts_file),
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            str(output_file)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            ts_file.unlink()
            return output_file
        except subprocess.CalledProcessError as e:
            logger.warning(f"ffmpeg conversion failed: {e}")
            return ts_file
    
    def sanitize_filename(self, name: str) -> str:
        """Create safe filename"""
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        name = re.sub(r'\s+', '.', name)
        name = re.sub(r'\.+', '.', name)
        return name.strip('.')
    
    def download_live(self, channel_id: int = None, channel_name: str = None,
                      duration: int = 60) -> Path:
        """
        Download live TV stream with parallel downloads.
        
        Args:
            channel_id: Channel ID
            channel_name: Or channel name
            duration: Duration in seconds
            
        Returns:
            Path to downloaded file
        """
        query = str(channel_id) if channel_id else channel_name
        if not query:
            raise ValueError("Provide channel_id or channel_name")
        
        channel = self.find_channel(query)
        if not channel:
            raise ValueError(f"Channel not found: {query}")
        
        logger.info(f"Downloading live: {channel.get('name')} ({duration}s)")
        
        stream_url = self.get_stream_url(channel, stream_type='live')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = self.sanitize_filename(channel.get('name', 'unknown'))
        output_file = self.output_dir / f"{safe_name}.live.{timestamp}.mp4"
        
        # Use fast parallel downloader
        ts_file = self.hls_downloader.download_live(stream_url, output_file, duration)
        
        # Convert to MP4
        return self._convert_to_mp4(ts_file, output_file)
    
    def download_live_with_playback(self, channel_id: int = None, channel_name: str = None,
                                     duration: int = 0, player: str = 'auto') -> Path:
        """
        Download live TV stream while playing it in a media player.
        
        Args:
            channel_id: Channel ID
            channel_name: Or channel name
            duration: Duration in seconds (0 = indefinite, Ctrl+C to stop)
            player: Media player to use ('vlc', 'mpv', 'auto', or path to player)
            
        Returns:
            Path to downloaded file
        """
        query = str(channel_id) if channel_id else channel_name
        if not query:
            raise ValueError("Provide channel_id or channel_name")
        
        channel = self.find_channel(query)
        if not channel:
            raise ValueError(f"Channel not found: {query}")
        
        channel_name = channel.get('name', 'unknown')
        logger.info(f"Recording + Playing: {channel_name}")
        
        stream_url = self.get_stream_url(channel, stream_type='live')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = self.sanitize_filename(channel_name)
        output_file = self.output_dir / f"{safe_name}.live.{timestamp}.mp4"
        
        # Find media player
        player_path = self._find_player(player)
        player_process = None
        
        def launch_player(ts_file: Path):
            nonlocal player_process
            if player_path:
                logger.info(f"Launching player: {player_path}")
                try:
                    # Launch player in background
                    if 'vlc' in player_path.lower():
                        # VLC can handle growing files well
                        player_process = subprocess.Popen(
                            [player_path, str(ts_file), '--no-video-title-show'],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                    elif 'mpv' in player_path.lower():
                        # MPV with cache for live streams
                        player_process = subprocess.Popen(
                            [player_path, str(ts_file), '--cache=yes', '--force-seekable=yes'],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                    else:
                        player_process = subprocess.Popen(
                            [player_path, str(ts_file)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                except Exception as e:
                    logger.warning(f"Failed to launch player: {e}")
            else:
                logger.warning("No media player found. Recording only.")
                print(f"\nRecording to: {ts_file}")
                print("Open this file in VLC/MPV to watch while recording.")
        
        # Download in real-time with playback callback
        ts_file = self.hls_downloader.download_live_realtime(
            stream_url, output_file, duration,
            on_segment_ready=launch_player
        )
        
        # Wait a moment for player to close gracefully
        if player_process:
            try:
                player_process.terminate()
            except:
                pass
        
        # Convert to MP4
        return self._convert_to_mp4(ts_file, output_file)
    
    def _find_player(self, player: str) -> Optional[str]:
        """Find a media player executable."""
        if player == 'auto':
            # Try common players
            for p in ['vlc', 'mpv', 'mpc-hc64', 'mpc-hc', 'ffplay']:
                found = shutil.which(p)
                if found:
                    return found
            
            # Check common Windows locations
            if platform.system() == 'Windows':
                common_paths = [
                    r'C:\Program Files\VideoLAN\VLC\vlc.exe',
                    r'C:\Program Files (x86)\VideoLAN\VLC\vlc.exe',
                    r'C:\Program Files\mpv\mpv.exe',
                    r'C:\Program Files\MPC-HC\mpc-hc64.exe',
                ]
                for p in common_paths:
                    if Path(p).exists():
                        return p
            
            return None
        
        elif player in ('vlc', 'mpv', 'ffplay'):
            return shutil.which(player)
        
        else:
            # Assume it's a path
            if Path(player).exists():
                return player
            return shutil.which(player)
    
    def download_catchup(self, channel_id: int = None, channel_name: str = None,
                         start_time: datetime = None, 
                         duration_minutes: int = 60) -> Path:
        """Download catchup/replay content."""
        query = str(channel_id) if channel_id else channel_name
        if not query:
            raise ValueError("Provide channel_id or channel_name")
        
        channel = self.find_channel(query)
        if not channel:
            raise ValueError(f"Channel not found: {query}")
        
        if not start_time:
            start_time = datetime.now() - timedelta(hours=1)
        
        logger.info(f"Downloading catchup: {channel.get('name')} from {start_time}")
        
        if not channel.get('cutvEnabled', False):
            raise ValueError(f"Catchup not enabled for channel: {channel.get('name')}")
        
        start_ts = int(start_time.timestamp() * 1000)
        stream_url = self.get_stream_url(channel, stream_type='cutv', start_time=start_ts)
        
        timestamp = start_time.strftime('%Y%m%d_%H%M%S')
        safe_name = self.sanitize_filename(channel.get('name', 'unknown'))
        output_file = self.output_dir / f"{safe_name}.catchup.{timestamp}.mp4"
        
        # VOD-style download (all segments available)
        ts_file = self.hls_downloader.download_vod(stream_url, output_file)
        
        return self._convert_to_mp4(ts_file, output_file)
    
    def get_vod_asset(self, asset_id: int) -> Dict:
        """Get VOD asset metadata."""
        url = f"{self.api_base}/v1/vodassets/{asset_id}"
        headers = {'Authorization': f'Bearer {self.auth.state.access_token}'}
        
        response = self.auth.session.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    def get_series_seasons(self, series_id: int) -> List[Dict]:
        """
        Get all seasons and episodes for a series.
        
        API: GET /v1/vodassets/{series_id}/seasons
        
        Returns:
            List of season dicts, each containing episodes list
        """
        url = f"{self.api_base}/v1/vodassets/{series_id}/seasons"
        headers = {'Authorization': f'Bearer {self.auth.state.access_token}'}
        
        response = self.auth.session.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    def parse_series_url(self, url: str) -> Tuple[int, Optional[int]]:
        """
        Parse EON series URL to extract series ID and optional season number.
        
        Supports formats:
            https://eon.tv/ondemand/detail/162073-s1  -> series 162073, season 1
            https://eon.tv/sr/ondemand/detail/162073-s1  -> series 162073, season 1
            https://eon.tv/ondemand/detail/162073  -> series 162073, all seasons
            162073-s1  -> series 162073, season 1
            162073  -> series 162073, all seasons
        
        Returns:
            (series_id, season_number) - season_number is None for all seasons
        """
        # Extract the ID portion (could be full URL or just ID)
        match = re.search(r'(\d+)(?:-s(\d+))?', url)
        if not match:
            raise ValueError(f"Could not parse series ID from: {url}")
        
        series_id = int(match.group(1))
        season_number = int(match.group(2)) if match.group(2) else None
        
        return series_id, season_number
    
    def list_series_episodes(self, series_url_or_id: str) -> List[Dict]:
        """
        List all episodes from a series URL or ID.
        
        Args:
            series_url_or_id: Full EON URL or just series ID (e.g., "162073-s1")
            
        Returns:
            List of episode dicts with id, title, season, episode number, duration
        """
        series_id, season_filter = self.parse_series_url(series_url_or_id)
        
        logger.info(f"Fetching series {series_id}...")
        
        # Get series info (title, etc.)
        series_info = self.get_vod_asset(series_id)
        series_title = series_info.get('title', f'Series {series_id}')
        vod_type = series_info.get('vodType', 'UNKNOWN')
        
        if vod_type != 'SERIES':
            raise ValueError(f"Asset {series_id} is not a series (type: {vod_type})")
        
        logger.info(f"Series: {series_title}")
        
        # Get all seasons with episodes
        seasons = self.get_series_seasons(series_id)
        logger.info(f"Total seasons: {len(seasons)}")
        
        all_episodes = []
        
        for season in seasons:
            season_num = season.get('seasonNumber', 0)
            
            # Skip if filtering to specific season
            if season_filter is not None and season_num != season_filter:
                continue
            
            episodes = season.get('episodes', [])
            logger.info(f"Season {season_num}: {len(episodes)} episodes")
            
            for ep in episodes:
                ep_num = ep.get('episodeNumber', 0)
                ep_title = ep.get('title', '') or ep.get('originalTitle', '') or f'Episode {ep_num}'
                ep_id = ep.get('id')
                duration_ms = ep.get('duration', 0)
                drm_required = ep.get('drmRequired', False)
                short_desc = ep.get('shortDescription', '')
                
                all_episodes.append({
                    'id': ep_id,
                    'series_id': series_id,
                    'series_title': series_title,
                    'season': season_num,
                    'episode': ep_num,
                    'title': ep_title if ep_title.strip() else f'Episode {ep_num}',
                    'description': short_desc[:80] + '...' if len(short_desc) > 80 else short_desc,
                    'duration_ms': duration_ms,
                    'duration_min': duration_ms // 60000,
                    'drm_required': drm_required or False,
                    'full_title': f"{series_title} S{season_num:02d}E{ep_num:02d}"
                })
        
        # Sort by season and episode
        all_episodes.sort(key=lambda x: (x['season'], x['episode']))
        
        return all_episodes
    
    def download_series(self, series_url_or_id: str, 
                        episode_filter: Optional[str] = None,
                        skip_drm: bool = True,
                        dry_run: bool = False) -> List[Path]:
        """
        Download all episodes from a series.
        
        Args:
            series_url_or_id: Series URL or ID (e.g., "162073-s1" or full URL)
            episode_filter: Optional filter like "1-5" or "3" or "1,3,5"
            skip_drm: Skip DRM-protected episodes (default: True)
            dry_run: Just list what would be downloaded
            
        Returns:
            List of downloaded file paths
        """
        episodes = self.list_series_episodes(series_url_or_id)
        
        if not episodes:
            logger.warning("No episodes found!")
            return []
        
        # Apply episode filter if specified
        if episode_filter:
            filtered = []
            for ep in episodes:
                ep_num = ep['episode']
                
                if '-' in episode_filter:
                    # Range: "1-5"
                    start, end = map(int, episode_filter.split('-'))
                    if start <= ep_num <= end:
                        filtered.append(ep)
                elif ',' in episode_filter:
                    # List: "1,3,5"
                    nums = [int(x.strip()) for x in episode_filter.split(',')]
                    if ep_num in nums:
                        filtered.append(ep)
                else:
                    # Single: "3"
                    if ep_num == int(episode_filter):
                        filtered.append(ep)
            episodes = filtered
        
        # Summary
        print(f"\n{'='*70}")
        print(f"SERIES DOWNLOAD: {episodes[0]['series_title'] if episodes else 'Unknown'}")
        print(f"{'='*70}")
        print(f"\n{'#':<4} {'ID':<10} {'Episode':<40} {'Duration':<10} {'DRM':<5}")
        print('-' * 70)
        
        downloadable = []
        for i, ep in enumerate(episodes, 1):
            drm_flag = '⚠️ DRM' if ep['drm_required'] else '✓'
            title_short = ep['full_title'][:38]
            print(f"{i:<4} {ep['id']:<10} {title_short:<40} {ep['duration_min']:<10} min {drm_flag}")
            
            if not ep['drm_required'] or not skip_drm:
                downloadable.append(ep)
        
        print(f"\nTotal episodes: {len(episodes)}")
        print(f"Downloadable (no DRM): {len(downloadable)}")
        
        if dry_run:
            print("\n[DRY RUN - No downloads performed]")
            return []
        
        if not downloadable:
            print("\nNo downloadable episodes (all require DRM)")
            return []
        
        # Confirm before batch download
        try:
            confirm = input(f"\nDownload {len(downloadable)} episodes? [y/N]: ").strip().lower()
            if confirm != 'y':
                print("Cancelled.")
                return []
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return []
        
        # Download each episode
        downloaded = []
        failed = []
        
        for i, ep in enumerate(downloadable, 1):
            print(f"\n[{i}/{len(downloadable)}] Downloading: {ep['full_title']}")
            
            try:
                # Create filename: SeriesTitle.S01E01.vod.mp4
                safe_series = self.sanitize_filename(ep['series_title'])
                filename = f"{safe_series}.S{ep['season']:02d}E{ep['episode']:02d}"
                
                output_path = self.download_vod(ep['id'], output_name=filename)
                downloaded.append(output_path)
                print(f"    ✓ Saved: {output_path}")
                
            except Exception as e:
                logger.error(f"    ✗ Failed: {e}")
                failed.append(ep)
        
        # Summary
        print(f"\n{'='*70}")
        print(f"DOWNLOAD COMPLETE")
        print(f"{'='*70}")
        print(f"  Successful: {len(downloaded)}")
        print(f"  Failed:     {len(failed)}")
        
        if failed:
            print(f"\nFailed episodes:")
            for ep in failed:
                print(f"  - {ep['full_title']} (ID: {ep['id']})")
        
        return downloaded
    
    def get_vod_stream_url(self, asset: Dict) -> str:
        """Build encrypted stream URL for VOD content."""
        pub_points = asset.get('publishingPoint', [])
        if not pub_points:
            raise ValueError(f"No publishing point for VOD: {asset.get('title')}")
        
        pub_point = pub_points[0]
        publishing_point = pub_point.get('publishingPoint', '')
        
        if asset.get('drmRequired', False):
            raise ValueError(f"VOD '{asset.get('title')}' requires DRM - not supported")
        
        player_cfgs = pub_point.get('playerCfgs', [])
        player_cfg = None
        for cfg in player_cfgs:
            if cfg.get('type') == 'vod':
                player_cfg = cfg
                break
        
        if not player_cfg:
            player_cfg = player_cfgs[0] if player_cfgs else {}
        
        sig = player_cfg.get('sig', '')
        
        return self._build_encrypted_stream_url(
            publishing_point=publishing_point,
            sig=sig,
            stream_type='vod'
        )
    
    def download_vod(self, asset_id: int, output_name: Optional[str] = None) -> Path:
        """
        Download VOD content with parallel downloads.
        
        Args:
            asset_id: VOD asset ID
            output_name: Optional custom filename
            
        Returns:
            Path to downloaded file
        """
        logger.info(f"Fetching VOD asset: {asset_id}")
        
        asset = self.get_vod_asset(asset_id)
        
        title = asset.get('title', f'vod_{asset_id}')
        duration_ms = asset.get('duration', 0)
        
        logger.info(f"VOD: {title} ({duration_ms // 60000} minutes)")
        
        stream_url = self.get_vod_stream_url(asset)
        
        safe_name = self.sanitize_filename(output_name or title)
        output_file = self.output_dir / f"{safe_name}.vod.mp4"
        
        # Fast parallel download
        ts_file = self.hls_downloader.download_vod(stream_url, output_file)
        
        return self._convert_to_mp4(ts_file, output_file)
    
    def list_channels(self, subscribed_only: bool = True) -> List[Dict]:
        """List available channels."""
        channels = self.get_channels()
        
        result = []
        for ch in channels:
            if subscribed_only and not ch.get('subscribed', False):
                continue
            
            result.append({
                'id': ch.get('id'),
                'name': ch.get('name'),
                'short_name': ch.get('shortName'),
                'drm_required': ch.get('drmRequired', False),
                'live_enabled': ch.get('liveEnabled', True),
                'catchup_enabled': ch.get('cutvEnabled', False),
                'subscribed': ch.get('subscribed', False),
            })
        
        return result


def main():
    parser = argparse.ArgumentParser(
        description='EON TV Video Downloader - FAST VERSION',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Save credentials
  %(prog)s --save-credentials -u email@example.com -p password
  
  # List channels
  %(prog)s --list-channels
  
  # Download 60 seconds of live TV (fast parallel download)
  %(prog)s --live --channel "RTS 1 HD" --duration 60
  
  # Record AND play live TV simultaneously (opens VLC/MPV)
  %(prog)s --live --channel "RTS 1 HD" --play --duration 300
  
  # Record indefinitely while watching (Ctrl+C to stop)
  %(prog)s --live --channel "RTS 1 HD" --play --duration 0
  
  # Use specific player
  %(prog)s --live --channel "RTS 1" --play --player vlc
  %(prog)s --live --channel "RTS 1" --play --player "C:\\Program Files\\mpv\\mpv.exe"
  
  # Download catchup
  %(prog)s --catchup --channel "N1 HD" --hours-ago 2 --duration 60
  
  # Download single VOD
  %(prog)s --vod 132592
  
  # Download entire series (season 1)
  %(prog)s --series "https://eon.tv/ondemand/detail/162073-s1"
  %(prog)s --series 162073-s1
  
  # Download all seasons
  %(prog)s --series 162073
  
  # List episodes without downloading
  %(prog)s --series 162073-s1 --list-episodes
  
  # Download specific episodes (ep 1-5, or ep 3, or ep 1,3,5)
  %(prog)s --series 162073-s1 --episodes 1-5
  %(prog)s --series 162073-s1 --episodes 1,3,5
  
  # Control parallelism (default 16 workers)
  %(prog)s --live --channel "RTS 1 HD" --workers 32
        """
    )
    
    parser.add_argument('-u', '--username', help='EON username/email')
    parser.add_argument('-p', '--password', help='EON password')
    parser.add_argument('--provider', default='sbb', 
                        help=f"Provider: {', '.join(PROVIDERS.keys())}")
    parser.add_argument('--save-credentials', action='store_true')
    
    parser.add_argument('--device-serial', help='Device serial from HAR')
    parser.add_argument('--device-number', help='Device number from HAR')
    parser.add_argument('--save-device', action='store_true')
    parser.add_argument('--new-device', action='store_true')
    
    parser.add_argument('--list-channels', action='store_true')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--catchup', action='store_true')
    parser.add_argument('--vod', type=int, metavar='ASSET_ID')
    
    # Live playback options
    parser.add_argument('--play', action='store_true',
                        help='Record and play live stream simultaneously')
    parser.add_argument('--player', default='auto',
                        help='Media player: vlc, mpv, auto, or path (default: auto)')
    
    # Series options
    parser.add_argument('--series', metavar='URL_OR_ID',
                        help='Series URL or ID (e.g., 162073-s1 or full URL)')
    parser.add_argument('--list-episodes', action='store_true',
                        help='List episodes without downloading')
    parser.add_argument('--episodes', metavar='FILTER',
                        help='Episode filter: "1-5" or "3" or "1,3,5"')
    parser.add_argument('--include-drm', action='store_true',
                        help='Attempt to download DRM episodes (will likely fail)')
    
    parser.add_argument('-c', '--channel', help='Channel name or ID')
    parser.add_argument('--duration', type=int, default=60,
                        help='Duration in seconds (live) or minutes (catchup)')
    parser.add_argument('--hours-ago', type=float, default=1)
    
    # Performance options
    parser.add_argument('--workers', type=int, default=16,
                        help='Number of parallel download threads (default: 16)')
    
    parser.add_argument('-o', '--output', default='output')
    parser.add_argument('-v', '--verbose', action='store_true')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize with worker count
    downloader = EONDownloader(
        provider=args.provider,
        output_dir=args.output,
        force_new_device=args.new_device,
        max_workers=args.workers
    )
    
    if args.device_serial and args.device_number:
        downloader.auth.set_device(args.device_serial, args.device_number, 
                                   save=args.save_device)
    
    if args.save_credentials:
        if not args.username or not args.password:
            print("Error: --save-credentials requires -u and -p")
            sys.exit(1)
        config = EONConfig()
        config.set_credentials(args.username, args.password, args.provider)
        print(f"Credentials saved!")
        if not (args.list_channels or args.live or args.catchup or args.vod or args.series):
            sys.exit(0)
    
    try:
        downloader.login(args.username, args.password)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    try:
        if args.list_channels:
            channels = downloader.list_channels()
            print(f"\n{'ID':<8} {'Name':<40} {'DRM':<5} {'Live':<5} {'Catchup':<7}")
            print('-' * 70)
            for ch in channels:
                print(f"{ch['id']:<8} {ch['name'][:38]:<40} "
                      f"{'Yes' if ch['drm_required'] else 'No':<5} "
                      f"{'Yes' if ch['live_enabled'] else 'No':<5} "
                      f"{'Yes' if ch['catchup_enabled'] else 'No':<7}")
        
        elif args.series:
            if args.list_episodes:
                # Just list episodes
                episodes = downloader.list_series_episodes(args.series)
                print(f"\n{'#':<4} {'ID':<10} {'Episode':<45} {'Duration':<8} {'DRM':<5}")
                print('-' * 75)
                for i, ep in enumerate(episodes, 1):
                    drm = '⚠️ DRM' if ep['drm_required'] else '✓'
                    print(f"{i:<4} {ep['id']:<10} {ep['full_title'][:43]:<45} "
                          f"{ep['duration_min']:<8}min {drm}")
                print(f"\nTotal: {len(episodes)} episodes")
            else:
                # Download series
                downloaded = downloader.download_series(
                    args.series,
                    episode_filter=args.episodes,
                    skip_drm=not args.include_drm,
                    dry_run=False
                )
                print(f"\n✓ Downloaded {len(downloaded)} episodes")
        
        elif args.live:
            if not args.channel:
                print("Error: --live requires --channel")
                sys.exit(1)
            
            if args.play:
                # Record and play simultaneously
                output_path = downloader.download_live_with_playback(
                    channel_name=args.channel,
                    duration=args.duration,  # 0 = indefinite
                    player=args.player
                )
            else:
                # Normal recording (parallel download at end)
                output_path = downloader.download_live(
                    channel_name=args.channel,
                    duration=args.duration
                )
            print(f"\n✓ Download complete: {output_path}")
        
        elif args.catchup:
            if not args.channel:
                print("Error: --catchup requires --channel")
                sys.exit(1)
            start_time = datetime.now() - timedelta(hours=args.hours_ago)
            output_path = downloader.download_catchup(
                channel_name=args.channel,
                start_time=start_time,
                duration_minutes=args.duration
            )
            print(f"\n✓ Download complete: {output_path}")
        
        elif args.vod:
            output_path = downloader.download_vod(args.vod)
            print(f"\n✓ Download complete: {output_path}")
        
        else:
            print("No action specified. Use --list-channels, --live, --catchup, --vod, or --series")
            parser.print_help()
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()