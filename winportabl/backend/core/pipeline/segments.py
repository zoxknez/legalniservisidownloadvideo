"""
Resumable native segment download (URL list → files on disk).

Used by future native DASH/HLS paths; stage pipeline for yt-dlp is separate.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Optional

import requests

from .checkpoint import JobCheckpoint

logger = logging.getLogger("pipeline.segments")

ProgressFn = Optional[Callable[[int, int], None]]


def merge_segment_files(paths: List[Path], output: Path) -> Path:
    """Byte-concat segments in order into *output*."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "wb") as out:
        for p in paths:
            p = Path(p)
            if not p.is_file():
                raise FileNotFoundError(f"Missing segment: {p}")
            with open(p, "rb") as f:
                while True:
                    chunk = f.read(1024 * 256)
                    if not chunk:
                        break
                    out.write(chunk)
    return output


def download_segments_resumable(
    urls: List[str],
    *,
    track: str,
    checkpoint: JobCheckpoint,
    headers: Optional[Dict[str, str]] = None,
    workers: int = 8,
    min_bytes: int = 64,
    progress: ProgressFn = None,
    session: Optional[requests.Session] = None,
) -> List[Path]:
    """
    Download *urls* into checkpoint.segments_dir/<track>/seg_NNNNN.bin
    Skip indices already marked done with a valid file.
    """
    if not urls:
        return []

    track_dir = checkpoint.segments_dir / track
    track_dir.mkdir(parents=True, exist_ok=True)
    done = checkpoint.segment_done_set(track)
    headers = headers or {}
    owns_session = session is None
    sess = session or requests.Session()

    dest_paths = [track_dir / f"seg_{i:05d}.bin" for i in range(len(urls))]
    pending = []
    for i, (url, dest) in enumerate(zip(urls, dest_paths)):
        if i in done and dest.is_file() and dest.stat().st_size >= min_bytes:
            continue
        pending.append((i, url, dest))

    total = len(urls)
    finished = total - len(pending)
    if progress:
        progress(finished, total)

    def _one(item):
        i, url, dest = item
        tmp = dest.with_suffix(".part")
        last_err = None
        for attempt in range(4):
            try:
                resp = sess.get(url, headers=headers, timeout=30, stream=True)
                resp.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in resp.iter_content(64 * 1024):
                        if chunk:
                            f.write(chunk)
                if tmp.stat().st_size < min_bytes:
                    raise RuntimeError(f"segment too small ({tmp.stat().st_size}B)")
                tmp.replace(dest)
                return i, True, None
            except Exception as e:
                last_err = e
                tmp.unlink(missing_ok=True)
        return i, False, last_err

    try:
        if pending:
            logger.info(
                "[segments] track=%s download %s/%s (resume skip %s)",
                track,
                len(pending),
                total,
                finished,
            )
            with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                futures = [pool.submit(_one, item) for item in pending]
                for fut in as_completed(futures):
                    i, ok, err = fut.result()
                    if not ok:
                        raise RuntimeError(f"Segment {i} failed: {err}")
                    checkpoint.mark_segment_done(track, i)
                    finished += 1
                    if progress:
                        progress(finished, total)
    finally:
        if owns_session:
            try:
                sess.close()
            except Exception:
                pass

    # Validate all present
    missing = [i for i, p in enumerate(dest_paths) if not p.is_file()]
    if missing:
        raise RuntimeError(f"Missing segments on track {track}: {missing[:10]}…")
    return dest_paths
