from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Optional

from backend.utils.cancellable_subprocess import run as run_subprocess

logger = logging.getLogger(__name__)

DEFAULT_MIN_MEDIA_BYTES = 100_000


def temporary_media_path(final_path: Path) -> Path:
    """Return a sibling temp path that keeps the final media suffix."""
    final_path = Path(final_path)
    return final_path.with_name(
        f"{final_path.stem}.{uuid.uuid4().hex}.tmp{final_path.suffix}"
    )


def _resolve_tool(name: str, configured: Optional[str] = None) -> Optional[str]:
    candidate = configured or name
    found = shutil.which(candidate)
    if found:
        return found
    path = Path(candidate)
    if path.exists():
        return str(path)
    return None


def is_complete_media_file(
    path: Path,
    *,
    min_bytes: int = DEFAULT_MIN_MEDIA_BYTES,
    ffprobe_path: Optional[str] = None,
    mkvmerge_path: Optional[str] = None,
    probe: bool = True,
) -> bool:
    path = Path(path)
    try:
        if not path.is_file():
            return False
        size = path.stat().st_size
    except OSError as exc:
        logger.warning("Cannot inspect media output %s: %s", path.name, exc)
        return False

    if size < min_bytes:
        logger.warning("Media output looks incomplete (%d bytes): %s", size, path.name)
        return False

    if not probe:
        return True

    ffprobe = _resolve_tool("ffprobe", ffprobe_path)
    if ffprobe:
        cmd = [
            ffprobe,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        try:
            result = run_subprocess(cmd, capture_output=True, text=True, timeout=20)
        except Exception as exc:
            logger.warning("ffprobe failed for %s: %s", path.name, exc)
            return False
        lines = (result.stdout or "").strip().splitlines()
        try:
            duration = float(lines[0]) if lines else 0.0
        except ValueError:
            duration = 0.0
        if result.returncode != 0 or duration <= 1.0:
            logger.warning("Media output failed ffprobe validation: %s", path.name)
            return False
        return True

    mkvmerge = _resolve_tool("mkvmerge", mkvmerge_path)
    if mkvmerge and path.suffix.lower() == ".mkv":
        try:
            result = run_subprocess(
                [mkvmerge, "--identify", str(path)],
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception as exc:
            logger.warning("mkvmerge identify failed for %s: %s", path.name, exc)
            return False
        if result.returncode != 0 or "Track ID" not in (result.stdout or ""):
            logger.warning("Media output failed MKV validation: %s", path.name)
            return False

    return True


def promote_validated_media(
    temp_path: Path,
    final_path: Path,
    *,
    min_bytes: int = DEFAULT_MIN_MEDIA_BYTES,
    ffprobe_path: Optional[str] = None,
    mkvmerge_path: Optional[str] = None,
    probe: bool = True,
) -> Path:
    temp_path = Path(temp_path)
    final_path = Path(final_path)
    if not is_complete_media_file(
        temp_path,
        min_bytes=min_bytes,
        ffprobe_path=ffprobe_path,
        mkvmerge_path=mkvmerge_path,
        probe=probe,
    ):
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Output validation failed: {final_path.name}")
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.replace(final_path)
    return final_path
