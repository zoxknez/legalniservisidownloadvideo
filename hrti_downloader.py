#!/usr/bin/env python3
"""
HRTI (hrti.hrt.hr) Video Downloader
Supports VOD content with Widevine DRM (DRMtoday / aviion2 merchant).

Usage:
    # Save credentials once
    python hrti_downloader.py --save-credentials -u user@email.com -p YourPassword

    # Download a VOD by URL
    python hrti_downloader.py "https://hrti.hrt.hr/video/vod/9a7bb881-0b1b-bc57-ab38-07b93d293a56/slatka-simona"

    # Download by reference ID directly
    python hrti_downloader.py --ref-id 9a7bb881-0b1b-bc57-ab38-07b93d293a56

    # Override output filename
    python hrti_downloader.py --ref-id ... --title "Slatka.Simona.2023"
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
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests
import xmltodict
from yt_dlp import YoutubeDL

from hrti_auth import HRTIAuth

# Use centralized DRM Manager (shared singleton with key caching, WVD diagnostics, multi-PSSH)
try:
    import sys, os
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from backend.services.drm_manager import drm_manager as _drm_manager
    _USE_CENTRAL_DRM = True
except ImportError:
    _USE_CENTRAL_DRM = False
    _drm_manager = None

logger = logging.getLogger(__name__)

LICENSE_URL = "https://lic.drmtoday.com/license-proxy-widevine/cenc/"


# ---------------------------------------------------------------------------
# Fallback WidevineCDM (used only if backend DRM Manager is unavailable)
# ---------------------------------------------------------------------------

class WidevineCDM:
    """Standalone CDM wrapper used when backend.services.drm_manager is not importable."""

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
            Path.home() / ".hrti" / "device.wvd",
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

    def get_keys(self, pssh_b64: str, license_url: str, headers: dict, service_name: str = "") -> List[str]:
        if self.legacy_mode:
            return self._get_keys_legacy(pssh_b64, license_url, headers)
        return self._get_keys_modern(pssh_b64, license_url, headers)

    def _unwrap_license(self, resp: requests.Response) -> bytes:
        try:
            j = resp.json()
            if j.get("status") == "OK" and "license" in j:
                return base64.b64decode(j["license"])
            for field in ("license", "ckc", "message", "licenseData",
                          "license_data", "widevine_license", "LicenseMessage"):
                if field in j:
                    try:
                        return base64.b64decode(j[field])
                    except Exception:
                        continue
        except Exception:
            pass
        return resp.content

    def _get_keys_modern(self, pssh_b64: str, license_url: str, headers: dict) -> List[str]:
        if not self.cdm:
            raise RuntimeError("CDM not initialized. Check device.wvd file.")
        pssh = self.PSSH(pssh_b64)
        session_id = self.cdm.open()
        try:
            challenge = self.cdm.get_license_challenge(session_id, pssh)
            resp = requests.post(license_url, data=challenge, headers=headers, timeout=20)
            resp.raise_for_status()
            logger.debug(f"License response: CT={resp.headers.get('Content-Type')} "
                         f"size={len(resp.content)}B first_bytes={resp.content[:8].hex()}")
            license_bytes = self._unwrap_license(resp)
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
                resp = requests.post(license_url, data=challenge, headers=headers, timeout=20)
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
# Binary detection
# ---------------------------------------------------------------------------

def detect_binaries() -> Dict[str, str]:
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
        path = shutil.which(binary) or (
            str(Path("binaries") / binary) if (Path("binaries") / binary).exists() else None
        )
        if path:
            found[key] = path
        else:
            logger.warning(f"Binary not found in PATH: {binary}")
            found[key] = binary  # fall back to bare name, let subprocess fail with a clear error
    return found


# ---------------------------------------------------------------------------
# MPD parsing helpers
# ---------------------------------------------------------------------------

def extract_pssh_from_mpd(mpd_text: str) -> Optional[str]:
    """Extract the first Widevine PSSH (systemID 1077efec) from MPD XML."""
    WIDEVINE_SYSTEM_ID = "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"
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


def get_best_streams(mpd_text: str) -> Dict[str, Any]:
    """
    Parse MPD and return the best (highest bitrate) video and audio stream info.
    """
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


# ---------------------------------------------------------------------------
# Main downloader class
# ---------------------------------------------------------------------------

class HRTIDownloader:
    def __init__(
        self,
        output_dir: str = "output",
        temp_dir: str = "temp",
        device_path: Optional[str] = None,
        workers: int = 16,
    ):
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        self.auth = HRTIAuth()
        # Prefer centralized DRM manager (shared singleton with key caching)
        if _USE_CENTRAL_DRM and _drm_manager and _drm_manager.is_ready():
            self.cdm = _drm_manager
            logger.info("[HRTIDownloader] Using centralized DRM manager (key caching enabled)")
        else:
            self.cdm = WidevineCDM(device_path)
            logger.info("[HRTIDownloader] Using standalone WidevineCDM")
        self.bins = detect_binaries()
        self.workers = workers

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def login(self, username: Optional[str] = None, password: Optional[str] = None):
        self.auth.login(username, password)
        logger.info("Authentication successful!")

    # ------------------------------------------------------------------
    # URL / ID helpers
    # ------------------------------------------------------------------

    def extract_reference_id(self, url: str) -> str:
        """
        Extract UUID-format reference ID from HRTI URL.
        """
        # UUID pattern
        m = re.search(
            r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
            url,
            re.IGNORECASE,
        )
        if m:
            return m.group(1)
        raise ValueError(f"Could not extract reference ID from URL: {url}")

    # ------------------------------------------------------------------
    # Core download steps
    # ------------------------------------------------------------------

    def get_decryption_keys(
        self,
        mpd_url: str,
        license_url: str,
        drm_headers: Dict[str, str],
    ) -> List[str]:
        """Fetch MPD, extract all PSSHs, get Widevine decryption keys via DRM Manager."""
        logger.info(f"Fetching MPD: {mpd_url}")
        resp = requests.get(mpd_url, timeout=30)
        resp.raise_for_status()
        mpd_text = resp.text

        # Log stream quality
        streams = get_best_streams(mpd_text)
        if streams:
            vbr = streams.get("video_bitrate", 0)
            abr = streams.get("audio_bitrate", 0)
            logger.info(f"Best streams — video: {vbr//1000}kbps, audio: {abr//1000}kbps")

        lic_headers = {"Content-Type": "application/octet-stream", **drm_headers}

        # Use multi-PSSH if centralized DRM manager, else single PSSH fallback
        if _USE_CENTRAL_DRM and _drm_manager and hasattr(_drm_manager, 'extract_all_pssh_from_mpd'):
            pssh_list = _drm_manager.extract_all_pssh_from_mpd(mpd_text)
            if not pssh_list:
                raise Exception("Could not find Widevine PSSH in MPD")
            logger.info(f"Found {len(pssh_list)} PSSH(s). Fetching keys from DRMtoday...")
            keys = _drm_manager.get_keys_multi_pssh(pssh_list, license_url, lic_headers, "hrti")
        else:
            pssh = extract_pssh_from_mpd(mpd_text)
            if not pssh:
                raise Exception("Could not find Widevine PSSH in MPD")
            logger.info(f"PSSH: {pssh[:40]}...")
            logger.info("Fetching decryption keys from DRMtoday...")
            keys = self.cdm.get_keys(pssh, license_url, lic_headers, "hrti")

        if not keys:
            raise Exception("No CONTENT keys returned from license server")
        for k in keys:
            logger.info(f"  Key: {k}")
        return keys

    def download_fragments(self, mpd_url: str, output_name: str,
                           workers: int = 16) -> tuple[Path, Path]:
        """
        Download encrypted audio and video fragments via yt-dlp.
        Uses concurrent fragment downloads for speed.
        Returns (video_path, audio_path).
        """
        video_out = self.temp_dir / f"{output_name}_enc_video.mp4"
        audio_out = self.temp_dir / f"{output_name}_enc_audio.mp4"

        aria2c = self.bins.get("aria2c")
        use_aria2c = aria2c and (shutil.which(aria2c) or Path(aria2c).exists())

        def _progress(d):
            if d.get("status") == "downloading":
                fname   = d.get("filename", "")
                track   = "Video" if "video" in fname.lower() else "Audio"
                done    = d.get("downloaded_bytes", 0)
                total   = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                speed   = d.get("speed") or 0
                eta     = d.get("eta") or 0
                fi      = d.get("fragment_index")
                fc      = d.get("fragment_count")
                spd_str = f"{speed/1024/1024:.1f}MB/s" if speed else "??MB/s"
                eta_str = f"ETA {eta}s" if eta else ""
                if total:
                    pct    = done / total * 100
                    filled = int(20 * done / total)
                    bar    = "█" * filled + "░" * (20 - filled)
                    size   = f"{total/1024/1024:.1f}MB"
                    frag   = f" frag {fi}/{fc}" if fi else ""
                    line   = f"  {track} [{bar}] {pct:5.1f}% of {size}  {spd_str}  {eta_str}{frag}"
                elif fi:
                    line   = f"  {track} frag {fi}/{fc or '?'}  {spd_str}  {eta_str}"
                else:
                    line   = f"  {track} {done//1024}KB  {spd_str}"
                print(f"\r{line:<70}", end="", flush=True)
            elif d.get("status") == "finished":
                fname = d.get("filename", "")
                track = "Video" if "video" in fname.lower() else "Audio"
                size  = (d.get("total_bytes") or d.get("downloaded_bytes", 0)) / 1024 / 1024
                print(f"\r  {track} ✓  {size:.1f}MB" + " " * 40)

        ydl_opts = {
            "allow_unplayable_formats": True,
            "outtmpl": str(self.temp_dir / f"{output_name}_enc.%(ext)s"),
            "format": "bestvideo+bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
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

        logger.info(f"Downloading fragments from: {mpd_url}")
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(mpd_url, download=True)

        # yt-dlp writes separate files for video and audio when format = bestvideo+bestaudio
        base = self.temp_dir / f"{output_name}_enc"
        v_candidates = list(self.temp_dir.glob(f"{output_name}_enc.f*.mp4")) + \
                       list(self.temp_dir.glob(f"{output_name}_enc.mp4"))
        a_candidates = list(self.temp_dir.glob(f"{output_name}_enc.f*.m4a")) + \
                       list(self.temp_dir.glob(f"{output_name}_enc.m4a")) + \
                       list(self.temp_dir.glob(f"{output_name}_enc.f*.mp4"))

        # Filter out duplicates
        v_candidates = [p for p in v_candidates if p != video_out]
        a_candidates = [p for p in a_candidates if p != audio_out and p != video_out]

        if not v_candidates and not a_candidates:
            merged = list(self.temp_dir.glob(f"{output_name}_enc.*"))
            if merged:
                logger.warning("yt-dlp produced a single merged file (unexpected for DRM). "
                               "Will attempt decryption of combined file.")
                return merged[0], merged[0]
            raise FileNotFoundError("yt-dlp produced no output files")

        if v_candidates:
            v_candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
            shutil.copy2(v_candidates[0], video_out)
        if a_candidates:
            a_candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
            shutil.copy2(a_candidates[0], audio_out)

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
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"mp4decrypt failed: {result.stderr}")
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
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"ffmpeg fix failed (non-fatal): {result.stderr[-300:]}")
            return input_path
        return fixed

    def mux_output(self, video_path: Path, audio_path: Path, output_path: Path) -> Path:
        """Mux video and audio with mkvmerge."""
        cmd = [
            self.bins["mkvmerge"],
            "-o", str(output_path),
            str(video_path),
            str(audio_path),
        ]
        logger.info(f"Muxing to: {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode not in (0, 1):
            raise Exception(f"mkvmerge failed: {result.stderr}")
        logger.info(f"Output: {output_path}")
        return output_path

    def cleanup(self, name: str):
        """Remove temp files for a given download name."""
        for pattern in [f"{name}_enc*", f"{name}_dec*", f"{name}_fixed*"]:
            for f in self.temp_dir.glob(pattern):
                try:
                    f.unlink()
                except Exception:
                    pass

    @staticmethod
    def sanitize_filename(name: str) -> str:
        name = re.sub(r'[<>:"/\\|?*]', "", name)
        name = re.sub(r"\s+", ".", name)
        return name.strip(".") or "hrti_video"

    # ------------------------------------------------------------------
    # Main download entry point
    # ------------------------------------------------------------------

    def download(
        self,
        url_or_ref: str,
        title_override: Optional[str] = None,
    ) -> Path:
        """Download a HRTI VOD item."""
        if not self.auth.is_authenticated():
            raise Exception("Not authenticated. Call login() first.")

        if re.match(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                    url_or_ref, re.IGNORECASE):
            ref_id = url_or_ref
        else:
            ref_id = self.extract_reference_id(url_or_ref)
        logger.info(f"Reference ID: {ref_id}")

        info = self.auth.get_stream_info(ref_id)
        mpd_url = info["mpd_url"]
        license_url = info["license_url"]
        drm_headers = info["drm_headers"]
        title = title_override or info["title"]

        safe_name = self.sanitize_filename(title)
        logger.info(f"Title: {title}")
        logger.info(f"MPD:   {mpd_url}")

        keys = self.get_decryption_keys(mpd_url, license_url, drm_headers)
        enc_video, enc_audio = self.download_fragments(mpd_url, safe_name, self.workers)

        dec_video = self.decrypt_file(enc_video, keys)
        dec_audio = self.decrypt_file(enc_audio, keys)

        output_path = self.output_dir / f"{safe_name}.mkv"
        self.mux_output(dec_video, dec_audio, output_path)
        self.cleanup(safe_name)

        return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="HRTI (hrti.hrt.hr) Video Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Save credentials
  python hrti_downloader.py --save-credentials -u user@email.com -p Password1

  # Download by URL
  python hrti_downloader.py "https://hrti.hrt.hr/video/vod/9a7bb881-0b1b-bc57-ab38-07b93d293a56/slatka-simona"

  # Download by reference ID
  python hrti_downloader.py --ref-id 9a7bb881-0b1b-bc57-ab38-07b93d293a56

  # Custom output title
  python hrti_downloader.py --ref-id 9a7bb881-... --title "Slatka.Simona.2023.Croatian"
        """,
    )

    parser.add_argument("url", nargs="?", help="HRTI video URL")
    parser.add_argument("--ref-id", help="Video reference ID (UUID format) instead of URL")
    parser.add_argument("-u", "--username", help="HRTI username / email")
    parser.add_argument("-p", "--password", help="HRTI password")
    parser.add_argument("--save-credentials", action="store_true",
                        help="Save credentials to ~/.hrti/config.json")

    parser.add_argument("--title", help="Override output filename base")
    parser.add_argument("-o", "--output", default="output", help="Output directory (default: output)")
    parser.add_argument("-d", "--device", default=None, help="Path to .wvd CDM device file")
    parser.add_argument("-w", "--workers", type=int, default=16,
                        help="Concurrent fragment downloads (default: 16)")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=args.verbose and logging.DEBUG or logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    downloader = HRTIDownloader(
        output_dir=args.output,
        device_path=args.device,
        workers=args.workers,
    )

    if args.save_credentials:
        if not args.username or not args.password:
            print("--save-credentials requires -u and -p")
            sys.exit(1)
        downloader.auth.save_credentials(args.username, args.password)
        print("Credentials saved successfully.")

    target = args.url or args.ref_id
    if target:
        try:
            downloader.login(args.username, args.password)
            downloader.download(target, args.title)
        except Exception as e:
            logger.error(f"Download failed: {e}")
            sys.exit(1)
    else:
        if not args.save_credentials:
            parser.print_help()

if __name__ == "__main__":
    main()
