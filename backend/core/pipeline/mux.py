"""Mux video + audio into final container."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from backend.utils.cancellable_subprocess import run as run_subprocess
from backend.utils.media_validation import promote_validated_media, temporary_media_path

logger = logging.getLogger("pipeline.mux")


def _tool_exists(path: Optional[str]) -> bool:
    if not path:
        return False
    return bool(shutil.which(path) or Path(path).exists())


def fix_container(input_path: Path, ffmpeg: Optional[str]) -> Path:
    """Remux with ffmpeg -c copy to fix timing/boxes; non-fatal on failure."""
    input_path = Path(input_path)
    if not ffmpeg or not _tool_exists(ffmpeg):
        return input_path
    fixed = input_path.with_name(input_path.stem + "_fixed" + input_path.suffix)
    if fixed.exists() and fixed.stat().st_size > 1024:
        return fixed
    cmd = [ffmpeg, "-y", "-i", str(input_path), "-c", "copy", str(fixed)]
    result = run_subprocess(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("[mux] ffmpeg fix failed (non-fatal): %s", (result.stderr or "")[-200:])
        return input_path
    return fixed


def mux_av(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    *,
    mkvmerge: Optional[str] = None,
    ffmpeg: Optional[str] = None,
) -> Path:
    """
    Mux video + audio. Prefer mkvmerge → .mkv, else ffmpeg → .mp4.
    """
    video_path = Path(video_path)
    audio_path = Path(audio_path)
    output_path = Path(output_path)

    same = video_path.resolve() == audio_path.resolve()

    if mkvmerge and _tool_exists(mkvmerge):
        out = output_path if output_path.suffix.lower() == ".mkv" else output_path.with_suffix(".mkv")
        temp = temporary_media_path(out)
        cmd = [mkvmerge, "-o", str(temp), str(video_path)]
        if not same:
            cmd.append(str(audio_path))
        logger.info("[mux] mkvmerge → %s", out.name)
        result = run_subprocess(cmd, capture_output=True, text=True)
        if result.returncode in (0, 1):
            promote_validated_media(temp, out, mkvmerge_path=mkvmerge)
            return out
        temp.unlink(missing_ok=True)
        logger.warning("[mux] mkvmerge failed (code %s), trying ffmpeg", result.returncode)

    if ffmpeg and _tool_exists(ffmpeg):
        out = output_path if output_path.suffix.lower() == ".mp4" else output_path.with_suffix(".mp4")
        temp = temporary_media_path(out)
        if same:
            cmd = [
                ffmpeg, "-y", "-i", str(video_path),
                "-c", "copy", "-movflags", "+faststart", str(temp),
            ]
        else:
            cmd = [
                ffmpeg, "-y",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-c", "copy",
                "-async", "1",
                "-vsync", "-1",
                "-fflags", "+genpts+igndts",
                "-movflags", "+faststart",
                str(temp),
            ]
        logger.info("[mux] ffmpeg → %s", out.name)
        result = run_subprocess(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            promote_validated_media(temp, out)
            return out
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg mux failed: {(result.stderr or '')[-500:]}")

    raise RuntimeError("Neither mkvmerge nor ffmpeg available for muxing")
