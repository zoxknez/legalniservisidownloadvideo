"""Locate downloaded media files and resolve output directories from queue jobs."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from backend.jobs.inprocess import is_inprocess_job, parse_job

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".ts", ".mov", ".avi", ".webm", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".opus", ".wav", ".flac"}
SUB_EXTENSIONS = {".srt", ".ass", ".vtt", ".ttml"}
TEMP_EXTENSIONS = (".part", ".ytdl", ".temp", ".tmp", ".aria2", ".aria2__temp")


def output_dir_from_o_value(path_val: str) -> str:
    raw = path_val
    if raw.startswith("chapter:"):
        raw = raw[len("chapter:"):]
    if "%(" in raw:
        parent = os.path.dirname(raw)
        return parent if parent else "."
    p = Path(raw)
    if p.suffix.lower() in VIDEO_EXTENSIONS | AUDIO_EXTENSIONS:
        parent = str(p.parent)
        return parent if parent else "."
    if p.exists() and p.is_dir():
        return str(p)
    parent = str(p.parent)
    return parent if parent and parent != "." else raw


def get_output_dir_from_cmd(cmd: List[str], metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if metadata and metadata.get("output_dir"):
        return str(metadata["output_dir"])
    if is_inprocess_job(cmd):
        try:
            params = parse_job(cmd).get("params") or {}
            return params.get("output_dir")
        except Exception:
            return None
    for idx, part in enumerate(cmd):
        if part == "-o" and idx + 1 < len(cmd):
            return output_dir_from_o_value(cmd[idx + 1])
    return None


def file_match_hints(metadata: Optional[Dict[str, Any]], queue_title: str) -> List[str]:
    hints: List[str] = []
    if metadata:
        for key in ("file_match_title", "video_title"):
            val = metadata.get(key)
            if val and str(val).strip():
                hints.append(str(val).strip())
    if queue_title and queue_title.strip():
        hints.append(queue_title.strip())
    return hints


def _sanitize_title_fragment(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", title).strip(" .")


def name_matches_hints(name: str, hints: List[str]) -> bool:
    if not hints:
        return False
    for hint in hints:
        san = _sanitize_title_fragment(hint)
        if not san or len(san) < 3:
            continue
        if san in name:
            return True
        for part in san.split():
            if len(part) > 3 and part in name:
                return True
    return False


def _prefix_matches(name: str, prefix: str) -> bool:
    if not prefix or len(prefix) < 3:
        return False
    san_name = _sanitize_title_fragment(name)
    san_prefix = _sanitize_title_fragment(prefix)
    return san_name.startswith(san_prefix) or san_prefix in san_name


def find_all_media_files(
    output_dir: str,
    hints: List[str],
    *,
    extensions: Optional[Set[str]] = None,
    min_mtime: float = 0,
    multi_file: bool = False,
    match_prefix: Optional[str] = None,
) -> List[Path]:
    if not multi_file:
        best = find_best_media_file(
            output_dir, hints, extensions=extensions, min_mtime=min_mtime
        )
        return [best] if best else []

    exts = extensions or VIDEO_EXTENSIONS
    path = Path(output_dir)
    if not path.exists() or not path.is_dir():
        return []

    matched: List[Path] = []
    for f in path.iterdir():
        if not f.is_file() or f.suffix.lower() not in exts:
            continue
        mtime = f.stat().st_mtime
        if mtime <= min_mtime:
            continue
        if hints and name_matches_hints(f.name, hints):
            matched.append(f)
        elif match_prefix and _prefix_matches(f.name, match_prefix):
            matched.append(f)

    if not matched:
        for f in path.iterdir():
            if not f.is_file() or f.suffix.lower() not in exts:
                continue
            if f.stat().st_mtime > min_mtime:
                matched.append(f)

    return sorted(matched, key=lambda p: (p.stat().st_mtime, p.name.lower()))


def find_best_media_file(
    output_dir: str,
    hints: List[str],
    *,
    extensions: Optional[Set[str]] = None,
    min_mtime: float = 0,
) -> Optional[Path]:
    exts = extensions or VIDEO_EXTENSIONS
    path = Path(output_dir)
    if not path.exists() or not path.is_dir():
        return None

    best_file: Optional[Path] = None
    best_time = min_mtime

    for f in path.iterdir():
        if not f.is_file() or f.suffix.lower() not in exts:
            continue
        mtime = f.stat().st_mtime
        if mtime <= min_mtime:
            continue
        if hints and not name_matches_hints(f.name, hints):
            continue
        if mtime > best_time:
            best_time = mtime
            best_file = f

    if best_file:
        return best_file

    if not hints:
        return None

    # Fallback: newest matching file without mtime floor (legacy jobs)
    for f in path.iterdir():
        if not f.is_file() or f.suffix.lower() not in exts:
            continue
        if not name_matches_hints(f.name, hints):
            continue
        mtime = f.stat().st_mtime
        if best_file is None or mtime > best_file.stat().st_mtime:
            best_file = f
    return best_file


def find_subtitle_for_video(video_path: Path, output_dir: str) -> Optional[Path]:
    folder = Path(output_dir)
    if not folder.exists():
        return None
    best_sub: Optional[Path] = None
    best_time = 0.0
    for f in folder.iterdir():
        if not f.is_file() or f.suffix.lower() not in SUB_EXTENSIONS:
            continue
        if f.stem.startswith(video_path.stem) or video_path.stem.startswith(f.stem):
            mtime = f.stat().st_mtime
            if mtime > best_time:
                best_time = mtime
                best_sub = f
    return best_sub


def clean_temp_files_for_job(
    output_dir: str,
    hints: List[str],
    *,
    min_mtime: float = 0,
) -> None:
    path = Path(output_dir)
    if not path.exists() or not path.is_dir():
        return

    for f in path.iterdir():
        if not f.is_file():
            continue
        name = f.name
        is_temp = any(name.endswith(ext) for ext in TEMP_EXTENSIONS) or f.suffix == ".part"
        if not is_temp:
            continue
        if min_mtime > 0 and f.stat().st_mtime < min_mtime:
            continue
        if hints and not name_matches_hints(name, hints):
            continue
        try:
            f.unlink()
        except OSError:
            pass
