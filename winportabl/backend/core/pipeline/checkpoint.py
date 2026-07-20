"""
Job checkpoint store for resumable downloads.

Layout:
  ~/.videodownload/jobs/<job_id>/checkpoint.json
  ~/.videodownload/jobs/<job_id>/segments/…   (native segment resume)
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Stage

logger = logging.getLogger("pipeline.checkpoint")

CHECKPOINT_VERSION = 1


def jobs_root() -> Path:
    try:
        from backend.config import CONFIG_DIR

        root = Path(CONFIG_DIR) / "jobs"
    except Exception:
        root = Path.home() / ".videodownload" / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def make_job_id(
    service: str,
    mpd_url: str,
    title: str = "",
    extra: str = "",
) -> str:
    """Stable job id from service + stream identity (not random)."""
    raw = f"{(service or '').strip().lower()}|{mpd_url.strip()}|{title.strip()}|{extra}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


class JobCheckpoint:
    """Load/save pipeline progress for a single download job."""

    def __init__(self, job_id: str, data: Optional[Dict[str, Any]] = None):
        self.job_id = job_id
        self.dir = jobs_root() / job_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "checkpoint.json"
        self.data: Dict[str, Any] = data or {
            "version": CHECKPOINT_VERSION,
            "job_id": job_id,
            "service": "",
            "mpd_url": "",
            "license_url": "",
            "title": "",
            "stage": Stage.INIT.value,
            "keys": [],
            "enc_video": "",
            "enc_audio": "",
            "dec_video": "",
            "dec_audio": "",
            "output_path": "",
            "segments": {},  # track_name -> list of completed indices
            "meta": {},
            "created_at": time.time(),
            "updated_at": time.time(),
        }

    # ── factory ──────────────────────────────────────────────────────────────

    @classmethod
    def open(
        cls,
        *,
        service: str,
        mpd_url: str,
        title: str = "",
        license_url: str = "",
        extra: str = "",
        job_id: Optional[str] = None,
    ) -> "JobCheckpoint":
        jid = job_id or make_job_id(service, mpd_url, title, extra)
        cp = cls(jid)
        if cp.path.exists():
            loaded = cls.load(jid)
            # Reuse only if same stream identity
            if (
                loaded.data.get("mpd_url") == mpd_url.strip()
                and loaded.data.get("service", "").lower() == (service or "").lower()
            ):
                logger.info(
                    "[checkpoint] resume job=%s stage=%s",
                    jid,
                    loaded.stage.value,
                )
                return loaded
        cp.data["service"] = (service or "").strip().lower()
        cp.data["mpd_url"] = mpd_url.strip()
        cp.data["license_url"] = (license_url or "").strip()
        cp.data["title"] = title or ""
        cp.save()
        logger.info("[checkpoint] new job=%s", jid)
        return cp

    @classmethod
    def load(cls, job_id: str) -> "JobCheckpoint":
        path = jobs_root() / job_id / "checkpoint.json"
        if not path.exists():
            return cls(job_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("[checkpoint] corrupt %s: %s", path, e)
            data = {}
        data.setdefault("job_id", job_id)
        return cls(job_id, data)

    # ── properties ───────────────────────────────────────────────────────────

    @property
    def stage(self) -> Stage:
        raw = str(self.data.get("stage") or Stage.INIT.value)
        try:
            return Stage(raw)
        except ValueError:
            return Stage.INIT

    @property
    def keys(self) -> List[str]:
        keys = self.data.get("keys") or []
        return [str(k) for k in keys if k]

    @property
    def segments_dir(self) -> Path:
        d = self.dir / "segments"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ── mutations ────────────────────────────────────────────────────────────

    def save(self) -> None:
        self.data["version"] = CHECKPOINT_VERSION
        self.data["job_id"] = self.job_id
        self.data["updated_at"] = time.time()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def set_stage(self, stage: Stage) -> None:
        self.data["stage"] = stage.value
        self.save()

    def _advance_stage(self, stage: Stage) -> None:
        """Set stage only forward (never regress after keys_after_fragments etc.)."""
        if not self.stage.reached(stage):
            self.data["stage"] = stage.value

    def set_keys(self, keys: List[str]) -> None:
        self.data["keys"] = list(keys)
        self._advance_stage(Stage.KEYS)
        self.save()

    def set_fragments(
        self,
        enc_video: Path | str,
        enc_audio: Path | str,
    ) -> None:
        self.data["enc_video"] = str(enc_video)
        self.data["enc_audio"] = str(enc_audio)
        self._advance_stage(Stage.FRAGMENTS)
        self.save()

    def set_decrypted(
        self,
        dec_video: Path | str,
        dec_audio: Path | str,
    ) -> None:
        self.data["dec_video"] = str(dec_video)
        self.data["dec_audio"] = str(dec_audio)
        self._advance_stage(Stage.DECRYPT)
        self.save()

    def set_output(self, output_path: Path | str) -> None:
        self.data["output_path"] = str(output_path)
        self.data["stage"] = Stage.DONE.value
        self.save()

    def mark_segment_done(self, track: str, index: int) -> None:
        segs = self.data.setdefault("segments", {})
        done = list(segs.get(track) or [])
        if index not in done:
            done.append(index)
            done.sort()
            segs[track] = done
            self.save()

    def segment_done_set(self, track: str) -> set:
        return set(self.data.get("segments", {}).get(track) or [])

    def file_ok(self, key: str, min_bytes: int = 1024) -> bool:
        path_str = self.data.get(key) or ""
        if not path_str:
            return False
        p = Path(path_str)
        try:
            return p.is_file() and p.stat().st_size >= min_bytes
        except OSError:
            return False

    def can_resume_fragments(self) -> bool:
        # File presence is authoritative (stage may lag if keys_after_fragments).
        return self.file_ok("enc_video")

    def can_resume_decrypt(self) -> bool:
        # Decrypt may be skip_decrypt (clear content) — allow empty keys if files exist
        return self.file_ok("dec_video")

    def clear(self) -> None:
        """Delete checkpoint file (keep dir optional)."""
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError:
            pass

    def purge_dir(self) -> None:
        """Remove entire job directory (checkpoint + segments)."""
        import shutil

        try:
            if self.dir.exists():
                shutil.rmtree(self.dir, ignore_errors=True)
        except OSError as e:
            logger.warning("[checkpoint] purge failed %s: %s", self.job_id, e)


# Default: remove jobs not updated for 7 days; DONE jobs after 3 days
DEFAULT_STALE_SECONDS = 7 * 24 * 3600
DEFAULT_DONE_SECONDS = 3 * 24 * 3600


def purge_job_segments(job_id: str) -> bool:
    """
    Remove only the segments/ subdirectory for a job (keep checkpoint.json).
    Call after successful mux when resume of that job is no longer needed.
    """
    import shutil

    seg_dir = jobs_root() / job_id / "segments"
    if not seg_dir.exists():
        return False
    try:
        shutil.rmtree(seg_dir, ignore_errors=True)
        logger.info("[checkpoint] purged segments for job=%s", job_id)
        return True
    except OSError as e:
        logger.warning("[checkpoint] segment purge failed %s: %s", job_id, e)
        return False


def cleanup_old_jobs(
    *,
    stale_seconds: int = DEFAULT_STALE_SECONDS,
    done_seconds: int = DEFAULT_DONE_SECONDS,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Delete old job checkpoint directories under ~/.videodownload/jobs/.

    - stage=done and older than done_seconds → purge
    - any stage older than stale_seconds (by updated_at) → purge
    """
    root = jobs_root()
    now = time.time()
    removed: List[str] = []
    kept = 0
    errors: List[str] = []

    try:
        entries = [p for p in root.iterdir() if p.is_dir()]
    except OSError as e:
        return {"removed": 0, "kept": 0, "errors": [str(e)], "ids": []}

    for job_dir in entries:
        cp_path = job_dir / "checkpoint.json"
        stage = Stage.INIT.value
        updated = 0.0
        if cp_path.exists():
            try:
                data = json.loads(cp_path.read_text(encoding="utf-8"))
                stage = str(data.get("stage") or Stage.INIT.value)
                updated = float(data.get("updated_at") or data.get("created_at") or 0)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                # Corrupt / unreadable → treat as stale if mtime is old
                try:
                    updated = cp_path.stat().st_mtime
                except OSError:
                    updated = 0.0
        else:
            try:
                updated = job_dir.stat().st_mtime
            except OSError:
                updated = 0.0

        age = now - updated if updated > 0 else stale_seconds + 1
        is_done = stage == Stage.DONE.value
        expire = done_seconds if is_done else stale_seconds
        if age < expire:
            kept += 1
            continue

        jid = job_dir.name
        if dry_run:
            removed.append(jid)
            continue
        try:
            import shutil

            shutil.rmtree(job_dir, ignore_errors=True)
            removed.append(jid)
            logger.info("[checkpoint] purged job=%s stage=%s age=%.0fh", jid, stage, age / 3600)
        except Exception as e:
            errors.append(f"{jid}: {e}")

    return {
        "removed": len(removed),
        "kept": kept,
        "errors": errors,
        "ids": removed,
        "dry_run": dry_run,
    }
