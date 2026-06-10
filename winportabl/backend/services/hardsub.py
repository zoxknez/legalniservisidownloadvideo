import os
import re
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("Hardsub")

def run_hardsub(video_file: str, subtitle_file: str, ffmpeg_path: str = "ffmpeg") -> Optional[str]:
    """
    Burn subtitles into a video file using FFmpeg.
    CWD is set to the folder of the files to avoid Windows path escaping issues in FFmpeg's vf subtitles filter.
    Replaces the original video file with the hardsubbed version.
    """
    video_path = Path(video_file)
    sub_path = Path(subtitle_file)
    if not video_path.exists() or not sub_path.exists():
        logger.error("Hardsub failed: video or subtitle file does not exist.")
        return None

    # Temporary output path
    output_path = video_path.with_name(f"{video_path.stem}_hardsub_tmp{video_path.suffix}")

    # Use relative names to avoid backslash escaping issues in subtitles filter on Windows
    rel_video = video_path.name
    rel_sub = sub_path.name
    rel_out = output_path.name

    # FFmpeg command: copy audio, re-encode video with subtitles filter
    cmd = [
        ffmpeg_path, "-y",
        "-i", rel_video,
        "-vf", f"subtitles={rel_sub}",
        "-c:v", "libx264",
        "-crf", "22",
        "-preset", "medium",
        "-c:a", "copy",
        rel_out
    ]

    logger.info(f"Burning subtitles '{rel_sub}' into '{rel_video}'")
    try:
        res = subprocess.run(
            cmd,
            cwd=str(video_path.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 100000:
            # Replace original video with hardsubbed version
            os.remove(video_path)
            shutil.move(output_path, video_path)
            logger.info("✓ Subtitles successfully burned into video.")
            return str(video_path)
        else:
            logger.error(f"✗ FFmpeg hardsub failed: {res.stderr[:400]}")
            if output_path.exists():
                os.remove(output_path)
            return None
    except Exception as e:
        logger.error(f"Hardsub process error: {e}")
        if output_path.exists():
            try:
                os.remove(output_path)
            except Exception:
                pass
        return None

def find_and_burn_subtitles(
    title: str,
    output_dir: str,
    ffmpeg_path: str = "ffmpeg",
    on_start=None,
    on_complete=None
):
    """
    Scans the output directory for a video and subtitle file matching the title,
    then triggers the hardsub process in a background thread.
    """
    if not title or len(title) < 3:
        if on_complete:
            on_complete(None)
        return
        
    sanitized_title = re.sub(r'[\\/:*?"<>|]', '_', title).strip(' .')
    path = Path(output_dir)
    if not path.exists() or not path.is_dir():
        if on_complete:
            on_complete(None)
        return
        
    video_extensions = {".mp4", ".mkv", ".ts", ".mov", ".avi"}
    sub_extensions = {".srt", ".ass"}

    best_video = None
    best_video_time = 0
    
    # Find the completed video file
    for f in path.iterdir():
        if f.is_file() and f.suffix.lower() in video_extensions:
            if sanitized_title in f.name or any(part in f.name for part in sanitized_title.split() if len(part) > 3):
                mtime = f.stat().st_mtime
                if mtime > best_video_time:
                    best_video_time = mtime
                    best_video = f

    if not best_video:
        logger.warning(f"Could not find video file for hardsubbing title: {title}")
        if on_complete:
            on_complete(None)
        return

    # Find the matching subtitle file in the same folder
    best_sub = None
    best_sub_time = 0
    for f in path.iterdir():
        if f.is_file() and f.suffix.lower() in sub_extensions:
            if f.stem.startswith(best_video.stem):
                mtime = f.stat().st_mtime
                if mtime > best_sub_time:
                    best_sub_time = mtime
                    best_sub = f

    if not best_sub:
        logger.warning(f"Could not find subtitle file for hardsubbing video: {best_video.name}")
        if on_complete:
            on_complete(None)
        return

    if on_start:
        try:
            on_start(str(best_video), str(best_sub))
        except Exception as cb_err:
            logger.debug("Hardsub on_start callback failed: %s", cb_err)

    import threading
    def _worker():
        result = run_hardsub(str(best_video), str(best_sub), ffmpeg_path)
        
        # Clean up the subtitle file after burning
        if result and best_sub.exists():
            try:
                os.remove(best_sub)
                logger.info(f"Cleaned up subtitle file after hardsub: {best_sub.name}")
            except Exception as e:
                logger.debug(f"Could not remove subtitle file: {e}")
                
        if on_complete:
            try:
                on_complete(result)
            except Exception as cb_err:
                logger.debug("Hardsub on_complete callback failed: %s", cb_err)

    threading.Thread(target=_worker, daemon=True).start()
