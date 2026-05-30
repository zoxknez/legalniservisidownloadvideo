#!/usr/bin/env python3
"""
RTSPlaneta Video Downloader - Improved Version
- Dynamic authentication (no hardcoded tokens)
- Cross-platform support (Windows/Linux/Mac)
- Better error handling
- Config file support
- Modern pywidevine support
"""

import base64
import time
import os
import sys
import requests
import argparse
import urllib.parse
import json
import re
import subprocess
import shutil
import platform
import logging
from pathlib import Path
from collections import defaultdict
from typing import Optional, List, Dict, Any

import xmltodict
from yt_dlp import YoutubeDL

# Import our auth module
from .rtsplaneta_auth import RTSPlanetaAuth, RTSPlanetaConfig

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class WidevineCDM:
    """
    Wrapper for Widevine CDM operations.
    Supports both modern pywidevine and legacy implementations.
    """
    
    def __init__(self, device_path: Optional[str] = None):
        """
        Initialize CDM with device file.
        
        Args:
            device_path: Path to .wvd device file or directory with legacy format
        """
        self.device_path = device_path
        self.cdm = None
        self.device = None
        self.legacy_mode = False
        self._init_cdm()
    
    def _init_cdm(self):
        """Initialize the CDM based on available library and device format"""
        try:
            # Try modern pywidevine first
            from pywidevine.cdm import Cdm
            from pywidevine.device import Device
            from pywidevine.pssh import PSSH
            
            self.PSSH = PSSH
            
            # Find device file
            device_file = self._find_device_file()
            
            if device_file:
                self.device = Device.load(device_file)
                self.cdm = Cdm.from_device(self.device)
                logger.info(f"Loaded CDM device from: {device_file}")
            else:
                logger.warning("No .wvd device file found. CDM functionality limited.")
                
        except ImportError:
            logger.warning("Modern pywidevine not found, trying legacy...")
            self._init_legacy_cdm()
    
    def _init_legacy_cdm(self):
        """Initialize legacy pywidevine CDM"""
        try:
            from pywidevine.cdm import cdm
            from pywidevine.cdm import deviceconfig
            
            self.cdm = cdm.Cdm()
            self.device_config = deviceconfig
            self.legacy_mode = True
            logger.info("Using legacy pywidevine CDM")
            
        except ImportError as e:
            logger.error(f"Failed to import pywidevine: {e}")
            raise RuntimeError("pywidevine not installed. Run: pip install pywidevine")
    
    def _find_device_file(self) -> Optional[Path]:
        """Find a .wvd device file"""
        search_paths = [
            Path.cwd() / "device.wvd",
            Path.cwd() / "cdm" / "device.wvd",
            Path.home() / ".wvd" / "device.wvd",
            Path.home() / ".rtsplaneta" / "device.wvd",
        ]
        
        # Also check if a path was provided
        if self.device_path:
            p = Path(self.device_path)
            if p.exists():
                if p.is_file() and p.suffix == '.wvd':
                    return p
                elif p.is_dir():
                    wvd_files = list(p.glob("*.wvd"))
                    if wvd_files:
                        return wvd_files[0]
        
        # Check default paths
        for path in search_paths:
            if path.exists():
                return path
        
        return None
    
    def get_keys(self, pssh_b64: str, license_url: str, headers: dict) -> List[str]:
        """
        Get decryption keys from license server.
        
        Args:
            pssh_b64: Base64 encoded PSSH
            license_url: Widevine license URL
            headers: Headers for license request
            
        Returns:
            List of keys in "kid:key" format
        """
        if self.legacy_mode:
            return self._get_keys_legacy(pssh_b64, license_url, headers)
        else:
            return self._get_keys_modern(pssh_b64, license_url, headers)
    
    def _get_keys_modern(self, pssh_b64: str, license_url: str, headers: dict) -> List[str]:
        """Get keys using modern pywidevine"""
        if not self.cdm:
            raise RuntimeError("CDM not initialized. Check device file.")
        
        # Parse PSSH
        pssh = self.PSSH(pssh_b64)
        
        # Open session - modern pywidevine uses open() with no args, then set_service_certificate and get_license_challenge with pssh
        session_id = self.cdm.open()
        
        try:
            # Get challenge
            challenge = self.cdm.get_license_challenge(session_id, pssh)
            
            # Send to license server
            response = requests.post(
                license_url,
                data=challenge,
                headers=headers,
                verify=False
            )
            response.raise_for_status()
            
            # Parse license
            self.cdm.parse_license(session_id, response.content)
            
            # Extract keys
            keys = []
            for key in self.cdm.get_keys(session_id):
                if key.type == 'CONTENT':
                    keys.append(f"{key.kid.hex}:{key.key.hex()}")
            
            return keys
            
        finally:
            self.cdm.close(session_id)
    
    def _get_keys_legacy(self, pssh_b64: str, license_url: str, headers: dict) -> List[str]:
        """Get keys using legacy pywidevine"""
        from pywidevine.decrypt.wvdecryptcustom import WvDecrypt
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                wvdecrypt = WvDecrypt(
                    init_data_b64=pssh_b64.encode(),
                    cert_data_b64=None
                )
                
                challenge = wvdecrypt.get_challenge()
                
                response = requests.post(
                    license_url,
                    data=challenge,
                    headers=headers,
                    verify=False
                )
                response.raise_for_status()
                
                license_b64 = base64.b64encode(response.content)
                wvdecrypt.update_license(license_b64)
                
                success, keys = wvdecrypt.start_process()
                
                if success and keys:
                    return keys
                    
            except Exception as e:
                logger.warning(f"Key fetch attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
        
        raise Exception(f"Failed to fetch keys after {max_retries} attempts")


class RTSPlanetaDownloader:
    """
    Main downloader class with improved architecture.
    """
    
    def __init__(self, output_dir: str = "output", temp_dir: str = "temp", 
                 device_path: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        
        # Initialize auth
        self.auth = RTSPlanetaAuth()
        self.config = RTSPlanetaConfig()
        
        # Initialize CDM
        self.cdm = WidevineCDM(device_path)
        
        # Cross-platform binary detection
        self.binaries = self._detect_binaries()
        
        # Create directories
        self._setup_directories()
    
    def _detect_binaries(self) -> Dict[str, str]:
        """Detect required binaries based on OS"""
        is_windows = platform.system() == 'Windows'
        ext = '.exe' if is_windows else ''
        
        binaries = {
            'aria2c': f'aria2c{ext}',
            'mp4decrypt': f'mp4decrypt{ext}',
            'mkvmerge': f'mkvmerge{ext}',
            'ffmpeg': f'ffmpeg{ext}',
        }
        
        # Check if binaries exist in PATH or current directory
        for name, binary in binaries.items():
            # Try to find in PATH
            found = shutil.which(binary)
            if found:
                binaries[name] = found
            else:
                # Check in binaries subfolder
                local_path = Path('binaries') / binary
                if local_path.exists():
                    binaries[name] = str(local_path)
                else:
                    logger.warning(f"Binary not found: {binary}")
        
        return binaries
    
    def _setup_directories(self):
        """Create necessary directories"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        (self.temp_dir / 'audio').mkdir(exist_ok=True)
        (self.temp_dir / 'video').mkdir(exist_ok=True)
    
    def login(self, username: Optional[str] = None, password: Optional[str] = None):
        """
        Authenticate with RTSPlaneta.
        Uses stored credentials if none provided.
        """
        if not username or not password:
            if self.config.has_credentials():
                username, password = self.config.get_credentials()
                logger.info(f"Using stored credentials for: {username}")
            else:
                raise ValueError("No credentials provided and none stored")
        
        self.auth.login(username, password)
        logger.info("Authentication successful!")
    
    def extract_video_id(self, url: str) -> str:
        """Extract video ID from RTSPlaneta URL"""
        patterns = [
            r'/episode/(\d+)',
            r'/show/(\d+)',
            r'/video/(\d+)',
            r'video_id[=/](\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        raise ValueError(f"Could not extract video ID from URL: {url}")
    
    def extract_series_id(self, url: str) -> Optional[str]:
        """Extract series ID from RTSPlaneta URL"""
        # Pattern: /serial/4276399/... 
        match = re.search(r'/serial/(\d+)', url)
        if match:
            return match.group(1)
        return None
    
    def is_series_url(self, url: str) -> bool:
        """Check if URL is a series page (not an episode)"""
        # Series URL: /serial/4276399/ranjeni-orao
        # Episode URL: /serial/4276399/episode/4276342/...
        return '/serial/' in url and '/episode/' not in url
    
    def get_series_episodes(self, series_url: str) -> List[Dict[str, str]]:
        """
        Fetch all episode IDs from a series page.
        
        Args:
            series_url: URL to the series page
            
        Returns:
            List of dicts with episode info: [{'id': '4276342', 'url': '...'}, ...]
        """
        logger.info(f"Fetching series page: {series_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        response = requests.get(series_url, headers=headers, verify=False)
        response.raise_for_status()
        
        # Find all episode links
        episode_pattern = r'/episode/(\d+)/([^"\'>\s]+)'
        matches = re.findall(episode_pattern, response.text)
        
        # Deduplicate and build episode list
        seen = set()
        episodes = []
        
        for episode_id, slug in matches:
            if episode_id not in seen:
                seen.add(episode_id)
                # Reconstruct the full URL
                series_id = self.extract_series_id(series_url)
                episode_url = f"https://rtsplaneta.rs/sr_lat/serial/{series_id}/episode/{episode_id}/{slug}"
                episodes.append({
                    'id': episode_id,
                    'url': episode_url,
                    'slug': slug
                })
        
        # Sort by episode ID (usually chronological)
        episodes.sort(key=lambda x: int(x['id']))
        
        logger.info(f"Found {len(episodes)} episodes")
        return episodes
    
    def download_series(self, series_url: str, start: int = 1, end: Optional[int] = None) -> List[Path]:
        """
        Download all episodes from a series.
        
        Args:
            series_url: URL to the series page
            start: Starting episode number (1-indexed)
            end: Ending episode number (inclusive), None for all
            
        Returns:
            List of paths to downloaded files
        """
        episodes = self.get_series_episodes(series_url)
        
        if not episodes:
            raise ValueError("No episodes found on series page")
        
        # Apply range filter
        total = len(episodes)
        start_idx = max(0, start - 1)
        end_idx = end if end else total
        
        episodes_to_download = episodes[start_idx:end_idx]
        
        print(f"\n{'='*60}")
        print(f"Series Download: {len(episodes_to_download)} of {total} episodes")
        print(f"Episodes {start} to {end_idx}")
        print(f"{'='*60}\n")
        
        downloaded = []
        failed = []
        
        for i, episode in enumerate(episodes_to_download, start=start):
            print(f"\n[{i}/{end_idx}] Downloading episode ID: {episode['id']}")
            print(f"    URL: {episode['url'][:70]}...")
            
            try:
                output_path = self.download(episode['url'])
                downloaded.append(output_path)
                print(f"    ✓ Success: {output_path.name}")
            except Exception as e:
                logger.error(f"Failed to download episode {episode['id']}: {e}")
                failed.append(episode)
                print(f"    ✗ Failed: {e}")
        
        # Summary
        print(f"\n{'='*60}")
        print(f"Download Summary")
        print(f"{'='*60}")
        print(f"  Successful: {len(downloaded)}")
        print(f"  Failed: {len(failed)}")
        
        if failed:
            print(f"\n  Failed episodes:")
            for ep in failed:
                print(f"    - {ep['id']}: {ep['slug']}")
        
        return downloaded
    
    def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """Get video metadata"""
        return self.auth.get_video_info(video_id)
    
    def get_mpd_info(self, video_id: str) -> Dict[str, Any]:
        """Get MPD manifest URL and DRM info"""
        streaming_info = self.auth.get_streaming_url(video_id)
        
        return {
            'mpd_url': streaming_info.get('url', ''),
            'license_url': streaming_info.get('drm', {}).get('widevine_la_url', ''),
            'drm_protected': streaming_info.get('drm', {}).get('protected', False),
        }
    
    def download_manifest_info(self, mpd_url: str) -> Dict[str, Any]:
        """Download and parse MPD manifest XML directly."""
        resp = requests.get(mpd_url, verify=False, timeout=30)
        resp.raise_for_status()
        return xmltodict.parse(resp.text)

    def get_best_formats(self, manifest_data: Dict) -> Dict[str, List[str]]:
        """Build fragment URLs from the parsed MPD XML."""
        result: Dict[str, List[str]] = {'video': [], 'audio': []}
        mpd = manifest_data.get('MPD', {})
        period = mpd.get('Period', {})
        adaptation_sets = period.get('AdaptationSet', [])
        if isinstance(adaptation_sets, dict):
            adaptation_sets = [adaptation_sets]

        video_reps: List[Dict] = []
        audio_reps: List[Dict] = []

        for aset in adaptation_sets:
            seg_tpl = aset.get('SegmentTemplate', {})
            media_tpl = seg_tpl.get('@media', '')
            init_tpl = seg_tpl.get('@initialization', '')
            start_number = int(seg_tpl.get('@startNumber', '1'))
            timeline = seg_tpl.get('SegmentTimeline', {})

            segments_s = timeline.get('S', [])
            if isinstance(segments_s, dict):
                segments_s = [segments_s]
            num_segments = 0
            for s in segments_s:
                repeat = int(s.get('@r', '0'))
                num_segments += 1 + repeat

            reps = aset.get('Representation', [])
            if isinstance(reps, dict):
                reps = [reps]

            for rep in reps:
                rep_id = rep.get('@id', '')
                bandwidth = int(rep.get('@bandwidth', '0'))
                mime = rep.get('@mimeType', aset.get('@mimeType', ''))

                seg_tpl_rep = rep.get('SegmentTemplate', seg_tpl)
                media_tpl_r = seg_tpl_rep.get('@media', media_tpl)
                init_tpl_r = seg_tpl_rep.get('@initialization', init_tpl)

                entry = {
                    'rep_id': rep_id,
                    'bandwidth': bandwidth,
                    'media_tpl': media_tpl_r,
                    'init_tpl': init_tpl_r,
                    'start_number': start_number,
                    'num_segments': num_segments,
                }

                if 'video' in mime:
                    video_reps.append(entry)
                elif 'audio' in mime:
                    audio_reps.append(entry)

        def build_urls(entry: Dict) -> List[str]:
            urls = []
            init_url = entry['init_tpl'].replace('$RepresentationID$', entry['rep_id'])
            urls.append(init_url)
            for i in range(entry['num_segments']):
                seg_url = entry['media_tpl'].replace(
                    '$RepresentationID$', entry['rep_id']
                ).replace('$Number$', str(entry['start_number'] + i))
                urls.append(seg_url)
            return urls

        if video_reps:
            best_video = max(video_reps, key=lambda r: r['bandwidth'])
            result['video'] = build_urls(best_video)
            logger.info(f"Selected video: {best_video['rep_id']} ({best_video['bandwidth']} bps, {best_video['num_segments']} segments)")

        if audio_reps:
            best_audio = max(audio_reps, key=lambda r: r['bandwidth'])
            result['audio'] = build_urls(best_audio)
            logger.info(f"Selected audio: {best_audio['rep_id']} ({best_audio['bandwidth']} bps, {best_audio['num_segments']} segments)")

        return result
    
    def download_fragments(self, urls: List[str], output_dir: Path):
        """Download fragments using aria2c"""
        if not urls:
            logger.warning("No URLs to download")
            return
        
        url_file = self.temp_dir / 'urls.txt'
        with open(url_file, 'w') as f:
            f.write('\n'.join(urls) + '\n')
        
        cmd = [
            self.binaries['aria2c'],
            f'--input-file={url_file}',
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            '--summary-interval=0',
            '--console-log-level=warn',
            '-x16', '-j16', '-s16',
            f'--dir={output_dir}'
        ]
        
        logger.info(f"Downloading {len(urls)} fragments to {output_dir}")
        subprocess.run(cmd, check=True)
    
    @staticmethod
    def natural_sort_key(s):
        """Natural sorting key for filenames"""
        return [int(t) if t.isdigit() else t.lower() 
                for t in re.split(r'(\d+)', str(s))]
    
    def merge_fragments(self, input_dir: Path, output_file: Path):
        """Merge fragment files into single file"""
        files = sorted(input_dir.glob('*'), key=self.natural_sort_key)
        
        logger.info(f"Merging {len(files)} fragments into {output_file}")
        
        with open(output_file, 'wb') as out_fd:
            for f in files:
                with open(f, 'rb') as in_fd:
                    shutil.copyfileobj(in_fd, out_fd)
    
    def extract_pssh_from_mpd(self, mpd_url: str) -> Optional[str]:
        """Try to extract PSSH from MPD manifest ContentProtection elements."""
        try:
            response = requests.get(mpd_url, verify=False, timeout=15)
            mpd_data = xmltodict.parse(response.text)

            period = mpd_data['MPD']['Period']
            adaptations = period.get('AdaptationSet', [])
            if not isinstance(adaptations, list):
                adaptations = [adaptations]

            for adaptation in adaptations:
                protections = adaptation.get('ContentProtection', [])
                if not isinstance(protections, list):
                    protections = [protections]

                for prot in protections:
                    scheme = prot.get('@schemeIdUri', '').lower()
                    if 'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed' in scheme:
                        pssh = prot.get('cenc:pssh') or prot.get('pssh')
                        if pssh:
                            return pssh.strip()

                reps = adaptation.get('Representation', [])
                if not isinstance(reps, list):
                    reps = [reps]
                for rep in reps:
                    protections = rep.get('ContentProtection', [])
                    if not isinstance(protections, list):
                        protections = [protections]
                    for prot in protections:
                        scheme = prot.get('@schemeIdUri', '').lower()
                        if 'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed' in scheme:
                            pssh = prot.get('cenc:pssh') or prot.get('pssh')
                            if pssh:
                                return pssh.strip()
        except Exception as e:
            logger.warning(f"Could not extract PSSH from MPD: {e}")

        return None

    @staticmethod
    def extract_pssh_from_mp4(file_path: Path) -> Optional[str]:
        """Extract Widevine PSSH box from an MP4/M4A init segment."""
        WIDEVINE_SYSTEM_ID = b'\xed\xef\x8b\xa9\x79\xd6\x4a\xce\xa3\xc8\x27\xdc\xd5\x1d\x21\xed'
        try:
            data = file_path.read_bytes()
            offset = 0
            while offset < len(data) - 8:
                box_size = int.from_bytes(data[offset:offset + 4], 'big')
                box_type = data[offset + 4:offset + 8]
                if box_size < 8:
                    break
                if box_type == b'pssh':
                    system_id = data[offset + 12:offset + 28]
                    if system_id == WIDEVINE_SYSTEM_ID:
                        pssh_box = data[offset:offset + box_size]
                        return base64.b64encode(pssh_box).decode()
                offset += box_size
        except Exception as e:
            logger.warning(f"Could not extract PSSH from {file_path}: {e}")
        return None

    def get_decryption_keys(self, mpd_url: str, license_url: str,
                            enc_video: Path = None, enc_audio: Path = None) -> List[str]:
        """Get Widevine decryption keys (tries MPD first, then encrypted files)."""
        pssh = self.extract_pssh_from_mpd(mpd_url)

        if not pssh and enc_video:
            logger.info("PSSH not in MPD, extracting from encrypted video...")
            pssh = self.extract_pssh_from_mp4(enc_video)

        if not pssh and enc_audio:
            logger.info("PSSH not in video, trying encrypted audio...")
            pssh = self.extract_pssh_from_mp4(enc_audio)

        if not pssh:
            raise ValueError("Could not find PSSH in MPD or encrypted files")

        logger.info(f"Found PSSH: {pssh[:40]}...")

        headers = {
            'Accept': '*/*',
            'Origin': 'https://rtsplaneta.rs',
            'Referer': 'https://rtsplaneta.rs/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }

        return self.cdm.get_keys(pssh, license_url, headers)
    
    def decrypt_media(self, input_file: Path, output_file: Path, keys: List[str]):
        """Decrypt media file using mp4decrypt"""
        cmd = [self.binaries['mp4decrypt']]
        
        for key in keys:
            cmd.extend(['--key', key])
        
        cmd.extend([str(input_file), str(output_file)])
        
        logger.info(f"Decrypting {input_file.name}")
        subprocess.run(cmd, check=True)
    
    def fix_media_container(self, input_file: Path, output_file: Path):
        """Fix container issues with ffmpeg"""
        cmd = [
            self.binaries['ffmpeg'],
            '-i', str(input_file),
            '-c', 'copy',
            '-y',
            str(output_file)
        ]
        
        logger.info(f"Fixing container: {input_file.name}")
        subprocess.run(cmd, check=True, capture_output=True)
    
    @staticmethod
    def _is_encrypted(mp4_path: Path) -> bool:
        """Check if an MP4 file uses encrypted sample entries (encv/enca)."""
        try:
            data = mp4_path.read_bytes()
            offset = 0
            while offset < len(data) - 8:
                box_size = int.from_bytes(data[offset:offset + 4], 'big')
                box_type = data[offset + 4:offset + 8]
                if box_size < 8:
                    break
                if box_type == b'moov':
                    chunk = data[offset:offset + box_size]
                    if b'encv' in chunk or b'enca' in chunk:
                        return True
                    return False
                offset += box_size
        except Exception:
            pass
        return False

    def _mux_with_ffmpeg(self, video_file: Path, audio_file: Path, output_file: Path):
        """Mux video and audio into MKV using ffmpeg."""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.binaries['ffmpeg'],
            '-y',
            '-i', str(video_file),
            '-i', str(audio_file),
            '-c', 'copy',
            '-movflags', '+faststart',
            str(output_file),
        ]
        logger.info(f"Muxing to: {output_file.name}")
        subprocess.run(cmd, check=True, capture_output=True)

    def mux_to_mkv(self, video_file: Path, audio_file: Path, output_file: Path):
        """Mux video and audio into MKV container using mkvmerge"""
        cmd = [
            self.binaries['mkvmerge'],
            '--ui-language', 'en',
            '--output', str(output_file),
            '--language', '0:und',
            '--default-track', '0:yes',
            str(video_file),
            '--language', '0:und',
            '--default-track', '0:yes',
            str(audio_file)
        ]
        
        logger.info(f"Muxing to: {output_file.name}")
        subprocess.run(cmd, check=True)
    
    def sanitize_filename(self, name: str) -> str:
        """Create safe filename"""
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        name = re.sub(r'\s+', '.', name)
        name = re.sub(r'\.+', '.', name)
        return name.strip('.')
    
    def cleanup(self):
        """Clean up temporary files"""
        logger.info("Cleaning up temporary files...")
        
        try:
            shutil.rmtree(self.temp_dir / 'audio', ignore_errors=True)
            shutil.rmtree(self.temp_dir / 'video', ignore_errors=True)
            
            for pattern in ['*.mp4', '*.txt', '*.json', '*.h264', '*.aac']:
                for f in self.temp_dir.glob(pattern):
                    f.unlink()
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
    
    def _download_streams_ytdlp(self, mpd_url: str) -> tuple:
        """Download encrypted video/audio streams via yt-dlp (handles CDN redirects)."""
        enc_video = self.temp_dir / 'encrypted_video.mp4'
        enc_audio = self.temp_dir / 'encrypted_audio.m4a'

        opts_video = {
            'quiet': True,
            'no_warnings': True,
            'allow_unplayable_formats': True,
            'format': 'bestvideo',
            'outtmpl': str(enc_video),
            'fixup': 'never',
        }
        opts_audio = {
            'quiet': True,
            'no_warnings': True,
            'allow_unplayable_formats': True,
            'format': 'bestaudio',
            'outtmpl': str(enc_audio),
            'fixup': 'never',
        }

        logger.info("Downloading encrypted video stream...")
        with YoutubeDL(opts_video) as ydl:
            ydl.download([mpd_url])

        logger.info("Downloading encrypted audio stream...")
        with YoutubeDL(opts_audio) as ydl:
            ydl.download([mpd_url])

        # yt-dlp may append format id to filename
        if not enc_video.exists():
            for p in self.temp_dir.glob('encrypted_video*'):
                enc_video = p
                break
        if not enc_audio.exists():
            for p in self.temp_dir.glob('encrypted_audio*'):
                enc_audio = p
                break

        if not enc_video.exists() or not enc_audio.exists():
            raise ValueError("yt-dlp failed to download streams")

        logger.info(f"Encrypted video: {enc_video.name} ({enc_video.stat().st_size} bytes)")
        logger.info(f"Encrypted audio: {enc_audio.name} ({enc_audio.stat().st_size} bytes)")
        return enc_video, enc_audio

    def download(self, url: str) -> Path:
        """
        Main download method.
        
        Args:
            url: RTSPlaneta video URL
            
        Returns:
            Path to downloaded MKV file
        """
        video_id = self.extract_video_id(url)
        logger.info(f"Video ID: {video_id}")

        video_info = self.get_video_info(video_id)
        title = video_info.get('video', [{}])[0].get('title', {}).get('title_long', f'video_{video_id}')
        logger.info(f"Title: {title}")

        mpd_info = self.get_mpd_info(video_id)
        mpd_url = mpd_info['mpd_url']
        license_url = mpd_info['license_url']

        logger.info(f"MPD URL: {mpd_url[:80]}...")
        logger.info(f"License URL: {license_url}")

        self._setup_directories()

        # Use yt-dlp to download streams (handles CDN redirects properly)
        enc_video, enc_audio = self._download_streams_ytdlp(mpd_url)

        # Check if content is actually encrypted (codec == encv/enca)
        encrypted = self._is_encrypted(enc_video)

        if encrypted:
            logger.info("Content is DRM-encrypted, fetching keys...")
            keys = self.get_decryption_keys(mpd_url, license_url, enc_video, enc_audio)
            logger.info(f"Got {len(keys)} decryption key(s)")

            dec_audio = self.temp_dir / 'decrypted_audio.mp4'
            dec_video = self.temp_dir / 'decrypted_video.mp4'

            self.decrypt_media(enc_video, dec_video, keys)
            self.decrypt_media(enc_audio, dec_audio, keys)

            fixed_audio = self.temp_dir / 'audio.aac'
            fixed_video = self.temp_dir / 'video.h264'

            self.fix_media_container(dec_audio, fixed_audio)
            self.fix_media_container(dec_video, fixed_video)
        else:
            logger.info("Content is NOT encrypted, skipping decryption")
            fixed_video = enc_video
            fixed_audio = enc_audio

        # Mux to MKV using ffmpeg
        safe_title = self.sanitize_filename(title)
        output_file = self.output_dir / f"{safe_title}.WEB-DL.mkv"

        self._mux_with_ffmpeg(fixed_video, fixed_audio, output_file)

        # Cleanup
        self.cleanup()

        logger.info(f"Download complete: {output_file}")
        return output_file


def main():
    parser = argparse.ArgumentParser(
        description='RTSPlaneta Video Downloader',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download single episode
  %(prog)s -i https://rtsplaneta.rs/sr_lat/serial/4647353/episode/4712433/...
  
  # Download entire series
  %(prog)s -i https://rtsplaneta.rs/sr_lat/serial/4276399/ranjeni-orao
  
  # Download episodes 1-5 of a series
  %(prog)s -i https://rtsplaneta.rs/sr_lat/serial/4276399/ranjeni-orao --start 1 --end 5
  
  # Download from episode 10 onwards
  %(prog)s -i https://rtsplaneta.rs/sr_lat/serial/4276399/ranjeni-orao --start 10
  
  # Save credentials
  %(prog)s --save-credentials -u email@example.com -p password
        """
    )
    
    parser.add_argument('-i', '--input', dest='url', help='Video or Series URL')
    parser.add_argument('-u', '--username', help='RTSPlaneta username/email')
    parser.add_argument('-p', '--password', help='RTSPlaneta password')
    parser.add_argument('-o', '--output', default='output', help='Output directory')
    parser.add_argument('-d', '--device', help='Path to .wvd device file')
    parser.add_argument('--save-credentials', action='store_true', 
                       help='Save credentials for future use')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    # Series options
    parser.add_argument('--start', type=int, default=1, 
                       help='Starting episode number (default: 1)')
    parser.add_argument('--end', type=int, default=None,
                       help='Ending episode number (default: all)')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize downloader
    downloader = RTSPlanetaDownloader(
        output_dir=args.output,
        device_path=args.device
    )
    
    # Handle credentials
    if args.save_credentials:
        if not args.username or not args.password:
            print("Error: --save-credentials requires -u and -p")
            sys.exit(1)
        
        config = RTSPlanetaConfig()
        config.set_credentials(args.username, args.password)
        print(f"Credentials saved to: {config.config_path}")
        
        if not args.url:
            sys.exit(0)
    
    # Login
    try:
        downloader.login(args.username, args.password)
    except ValueError as e:
        print(f"Error: {e}")
        print("Please provide credentials with -u and -p, or save them with --save-credentials")
        sys.exit(1)
    
    # Download
    if args.url:
        try:
            # Check if this is a series URL or single episode
            if downloader.is_series_url(args.url):
                print(f"Detected series URL. Fetching episode list...")
                downloaded = downloader.download_series(
                    args.url, 
                    start=args.start, 
                    end=args.end
                )
                print(f"\n✓ Series download complete: {len(downloaded)} episodes")
            else:
                output_path = downloader.download(args.url)
                print(f"\n✓ Download complete: {output_path}")
                
        except Exception as e:
            logger.error(f"Download failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)
    else:
        print("No URL provided. Use -i to specify video URL.")
        sys.exit(1)


if __name__ == "__main__":
    main()
