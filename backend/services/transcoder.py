import os
import re
import subprocess
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any

logger = logging.getLogger("Transcoder")

# Global hardware encoders cache
_encoders_cache: Optional[List[str]] = None

def _get_supported_encoders() -> List[str]:
    """Query FFmpeg to see which video encoders are supported on this machine."""
    global _encoders_cache
    if _encoders_cache is not None:
        return _encoders_cache
        
    from backend.config import config
    binaries = config.check_binaries_status()
    ffmpeg_path = binaries.get("ffmpeg", {}).get("path") or "ffmpeg"
    
    try:
        res = subprocess.run(
            [ffmpeg_path, "-encoders"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=10
        )
        if res.returncode == 0:
            # Parse output for encoder names (usually starts with V..... for video)
            encoders = []
            for line in res.stdout.splitlines():
                if "V" in line[:10]: # Video encoder line
                    parts = line.split()
                    if len(parts) >= 2:
                        encoders.append(parts[1])
            _encoders_cache = encoders
            logger.info(f"Detected FFmpeg encoders: {len(encoders)} found.")
            return encoders
    except Exception as e:
        logger.error(f"Failed to query FFmpeg encoders: {e}")
        
    _encoders_cache = []
    return []

def select_best_encoder(codec: str) -> str:
    """
    Select the optimal hardware encoder for a target codec (HEVC/H.265 or AV1).
    Falls back to high-quality software encoding if no GPU is detected.
    """
    supported = _get_supported_encoders()
    
    if codec.lower() == "av1":
        # 1. NVIDIA NVENC (Fastest, excellent quality)
        if "av1_nvenc" in supported:
            logger.info("Using hardware-accelerated AV1 encoder: NVIDIA NVENC (av1_nvenc)")
            return "av1_nvenc"
        # 2. Intel QuickSync (QSV)
        if "av1_qsv" in supported:
            logger.info("Using hardware-accelerated AV1 encoder: Intel QSV (av1_qsv)")
            return "av1_qsv"
        # 3. Software AV1 (High efficiency, very slow but amazing compression)
        logger.info("No AV1 GPU encoder detected. Falling back to high-fidelity software AV1 (libsvtav1)")
        return "libsvtav1"
        
    else: # Default: HEVC / H.265 (Widely supported)
        # 1. NVIDIA NVENC
        if "hevc_nvenc" in supported:
            logger.info("Using hardware-accelerated HEVC encoder: NVIDIA NVENC (hevc_nvenc)")
            return "hevc_nvenc"
        # 2. Intel QSV
        if "hevc_qsv" in supported:
            logger.info("Using hardware-accelerated HEVC encoder: Intel QSV (hevc_qsv)")
            return "hevc_qsv"
        # 3. AMD AMF
        if "hevc_amf" in supported:
            logger.info("Using hardware-accelerated HEVC encoder: AMD AMF (hevc_amf)")
            return "hevc_amf"
        # 4. Apple Silicon
        if "hevc_videotoolbox" in supported:
            logger.info("Using hardware-accelerated HEVC encoder: Apple Silicon (hevc_videotoolbox)")
            return "hevc_videotoolbox"
            
        logger.info("No HEVC GPU encoder detected. Falling back to software HEVC (libx265)")
        return "libx265"

def run_transcode(input_file: str, codec: str = "hevc") -> Optional[str]:
    """
    Transcode completed video file to HEVC/AV1 for storage saving.
    Replaces original file with compressed file if successful.
    """
    input_path = Path(input_file)
    if not input_path.exists():
        logger.error(f"Transcoding failed: input file {input_file} does not exist.")
        return None
        
    from backend.config import config
    binaries = config.check_binaries_status()
    ffmpeg_path = binaries.get("ffmpeg", {}).get("path") or "ffmpeg"
    
    encoder = select_best_encoder(codec)
    
    # Generate temporary output path
    output_path = input_path.with_name(f"{input_path.stem}_tmp_transcoded.mkv")
    
    # Configure command
    # Copy audio streams directly to avoid quality loss, transcode video stream only.
    cmd = [
        ffmpeg_path, "-hwaccel", "auto", "-y",
        "-i", str(input_path),
        "-c:v", encoder
    ]
    
    # Configure codec parameters
    if codec.lower() == "av1":
        if "nvenc" in encoder or "qsv" in encoder:
            cmd += ["-preset", "slow", "-cq", "26"] # High quality GPU GCM
        else: # Software AV1
            cmd += ["-preset", "6", "-crf", "26"]
    else: # HEVC
        if "nvenc" in encoder or "qsv" in encoder or "amf" in encoder:
            cmd += ["-preset", "slow", "-cq", "24"]
        else: # Software x265
            cmd += ["-preset", "medium", "-crf", "22"]
            
    cmd += [
        "-c:a", "copy",
        "-c:s", "copy",
        str(output_path)
    ]
    
    logger.info(f"Starting background transcode pipeline for: {input_path.name}")
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 100000:
            # Transcode succeeded! Replace original with transcoded file
            original_size = input_path.stat().st_size
            compressed_size = output_path.stat().st_size
            saving_pct = round(((original_size - compressed_size) / original_size) * 100, 1)
            
            # Replace
            os.remove(input_path)
            shutil.move(output_path, input_path)
            
            logger.info(f"✓ Transcode successful! Compression saved {saving_pct}% storage space.")
            return str(input_path)
        else:
            logger.error(f"✗ Transcode failed: {res.stderr[:400]}")
            if output_path.exists():
                os.remove(output_path)
            return None
    except Exception as e:
        logger.error(f"Transcoder process error: {e}")
        if output_path.exists():
            try:
                os.remove(output_path)
            except Exception:
                pass
        return None

def find_and_transcode_completed(
    title: str,
    output_dir: str,
    codec: str = "hevc",
    on_start=None,
    on_complete=None,
):
    """
    Scans the output directory for a file matching the downloaded title
    and initiates the transcoding pipeline in the background.
    """
    if not title or len(title) < 3:
        return
        
    sanitized_title = re.sub(r'[\\/:*?"<>|]', '_', title).strip(' .')
    path = Path(output_dir)
    if not path.exists() or not path.is_dir():
        return
        
    # Find most recently modified file that matches the title
    best_file = None
    best_time = 0
    
    # Standard extensions for completed files
    extensions = {".mp4", ".mkv", ".ts", ".mov", ".avi"}
    
    try:
        import shutil
        import threading
        for f in path.iterdir():
            if f.is_file() and f.suffix.lower() in extensions:
                if sanitized_title in f.name or any(part in f.name for part in sanitized_title.split() if len(part) > 3):
                    mtime = f.stat().st_mtime
                    if mtime > best_time:
                        best_time = mtime
                        best_file = f
                        
        if best_file:
            # We found the completed file! Start the transcode in a background thread
            logger.info(f"Triggering background compression ({codec}) for: {best_file.name}")
            if on_start:
                try:
                    on_start(str(best_file))
                except Exception as cb_err:
                    logger.debug("Transcode on_start callback failed: %s", cb_err)

            def _worker():
                result = run_transcode(str(best_file), codec)
                if on_complete:
                    try:
                        on_complete(result)
                    except Exception as cb_err:
                        logger.debug("Transcode on_complete callback failed: %s", cb_err)

            threading.Thread(target=_worker, daemon=True).start()
    except Exception as e:
        logger.error(f"Error searching for transcode target for title '{title}': {e}")

def get_transcode_diagnostics() -> Dict[str, Any]:
    """
    Get diagnostic information about the system's GPU and supported hardware encoders.
    """
    import platform
    supported = _get_supported_encoders()
    
    # Detect GPU name on Windows
    gpu_name = "Generički Video Procesor"
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output("wmic path win32_VideoController get name", shell=True, text=True)
            lines = [line.strip() for line in out.splitlines() if line.strip() and "Name" not in line]
            if lines:
                gpu_name = lines[0]
        elif platform.system() == "Darwin":
            out = subprocess.check_output("sysctl -n machdep.cpu.brand_string", shell=True, text=True)
            gpu_name = out.strip()
        elif platform.system() == "Linux":
            try:
                out = subprocess.check_output("lspci | grep -i vga", shell=True, text=True)
                gpu_name = out.split(":")[-1].strip()
            except Exception:
                gpu_name = "Linux Video Controller"
    except Exception:
        pass
        
    # Check for specific hardware acceleration support
    nvenc_support = any("nvenc" in enc for enc in supported)
    qsv_support = any("qsv" in enc for enc in supported)
    amf_support = any("amf" in enc for enc in supported)
    videotoolbox_support = any("videotoolbox" in enc for enc in supported)
    
    return {
        "gpu_name": gpu_name,
        "supported_encoders": supported,
        "accelerations": {
            "nvidia_nvenc": {
                "supported": nvenc_support,
                "label": "NVIDIA NVENC (Hardverski)",
                "description": "Ekstremno brzo HEVC/AV1 kodiranje preko NVIDIA grafičkih kartica."
            },
            "intel_qsv": {
                "supported": qsv_support,
                "label": "Intel QuickSync (QSV)",
                "description": "Efikasno kodiranje preko integrisanih Intel procesora."
            },
            "amd_amf": {
                "supported": amf_support,
                "label": "AMD AMF (Hardverski)",
                "description": "Hardverska akceleracija za AMD Radeon grafičke kartice."
            },
            "apple_videotoolbox": {
                "supported": videotoolbox_support,
                "label": "Apple VideoToolbox",
                "description": "Hardversko ubrzanje za Apple Silicon M1/M2/M3 čipove."
            },
            "software": {
                "supported": True,
                "label": "Softversko kodiranje (CPU)",
                "description": "Visok kvalitet kompresije (libx265/libsvtav1), ali visoko opterećenje procesora."
            }
        },
        "available_codecs": {
            "hevc": {
                "supported": any(c in supported for c in ["hevc_nvenc", "hevc_qsv", "hevc_amf", "hevc_videotoolbox", "libx265"]),
                "encoder_used": select_best_encoder("hevc")
            },
            "av1": {
                "supported": any(c in supported for c in ["av1_nvenc", "av1_qsv", "libsvtav1"]),
                "encoder_used": select_best_encoder("av1")
            }
        }
    }


