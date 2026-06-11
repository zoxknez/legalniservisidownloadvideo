import os
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from backend.utils.cancellable_subprocess import run as run_subprocess

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
        res = run_subprocess(
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
    on_complete=None,
    metadata: Optional[Dict[str, Any]] = None,
    min_mtime: float = 0,
):
    """
    Scans the output directory for a video and subtitle file matching the title,
    then triggers the hardsub process in a background thread.
    """
    from backend.services.output_files import (
        file_match_hints,
        find_all_media_files,
        find_subtitle_for_video,
    )

    hints = file_match_hints(metadata, title)
    if not hints and not (metadata or {}).get("multi_file"):
        if on_complete:
            on_complete(None)
        return

    path = Path(output_dir)
    if not path.exists() or not path.is_dir():
        if on_complete:
            on_complete(None)
        return

    multi_file = bool((metadata or {}).get("multi_file"))
    match_prefix = (metadata or {}).get("file_match_prefix")
    videos = find_all_media_files(
        output_dir,
        hints,
        min_mtime=min_mtime,
        multi_file=multi_file,
        match_prefix=str(match_prefix) if match_prefix else None,
    )
    if not videos:
        logger.warning("Could not find video file(s) for hardsubbing (hints=%s)", hints[:2])
        if on_complete:
            on_complete(None)
        return

    pairs: list[tuple[Path, Path]] = []
    for video in videos:
        sub = find_subtitle_for_video(video, output_dir)
        if sub:
            pairs.append((video, sub))

    if not pairs:
        logger.warning("Could not find subtitle files for hardsubbing (%d videos)", len(videos))
        if on_complete:
            on_complete(None)
        return

    import threading

    def _worker():
        last_result: Optional[str] = None
        for video, sub in pairs:
            if on_start:
                try:
                    on_start(str(video), str(sub))
                except Exception as cb_err:
                    logger.debug("Hardsub on_start callback failed: %s", cb_err)
            last_result = run_hardsub(str(video), str(sub), ffmpeg_path)
            if last_result and sub.exists():
                try:
                    os.remove(sub)
                    logger.info("Cleaned up subtitle file after hardsub: %s", sub.name)
                except Exception as e:
                    logger.debug("Could not remove subtitle file: %s", e)
        if on_complete:
            try:
                on_complete(last_result)
            except Exception as cb_err:
                logger.debug("Hardsub on_complete callback failed: %s", cb_err)

    threading.Thread(target=_worker, daemon=True).start()
