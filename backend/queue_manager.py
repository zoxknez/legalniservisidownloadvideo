import asyncio
import os
import re
import uuid
import time
import sys
import logging
import sqlite3
import json
import threading
from enum import Enum
from typing import Dict, Any, List, Set, Optional
from fastapi import WebSocket
from pathlib import Path
from datetime import datetime
from backend.config import config, PROJECT_ROOT

logger = logging.getLogger(__name__)

SENSITIVE_CLI_FLAGS = {"-p", "--password", "--pass", "--token", "--access-token", "--refresh-token"}


class DownloadStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @staticmethod
    def can_transition(current: "DownloadStatus", target: "DownloadStatus") -> bool:
        return target in _VALID_TRANSITIONS.get(current, set())


_VALID_TRANSITIONS: Dict[DownloadStatus, Set[DownloadStatus]] = {
    DownloadStatus.PENDING: {DownloadStatus.DOWNLOADING, DownloadStatus.CANCELLED},
    DownloadStatus.DOWNLOADING: {DownloadStatus.FINISHED, DownloadStatus.FAILED, DownloadStatus.CANCELLED},
    DownloadStatus.FAILED: {DownloadStatus.PENDING},
    DownloadStatus.FINISHED: {DownloadStatus.PENDING},
    DownloadStatus.CANCELLED: {DownloadStatus.PENDING},
}

# Queue manager configuration
MAX_CONCURRENT_DOWNLOADS = 2
MAX_RETRIES = 3
DOWNLOAD_TIMEOUT = 3600  # 1 hour


def redact_command(cmd: List[str]) -> str:
    """Redact sensitive information from command."""
    if cmd and cmd[0] == "@inprocess":
        try:
            import json
            payload = json.loads(cmd[1])
            params = payload.get("params") or {}
            safe = dict(params)
            for key in ("password", "token", "access_token"):
                if key in safe:
                    safe[key] = "***"
            return f"@inprocess {payload.get('service')}:{payload.get('action')} {safe}"
        except Exception:
            return "@inprocess [job]"
    redacted = []
    mask_next = False
    for part in cmd:
        if mask_next:
            redacted.append("***")
            mask_next = False
            continue

        if part in SENSITIVE_CLI_FLAGS:
            redacted.append(part)
            mask_next = True
            continue

        lowered = part.lower()
        if any(lowered.startswith(f"{flag}=") for flag in SENSITIVE_CLI_FLAGS):
            flag, _, _value = part.partition("=")
            redacted.append(f"{flag}=***")
            continue

        redacted.append(part)

    return " ".join(redacted)


def redact_log_line(line: str) -> str:
    """Scrub sensitive information such as JWTs, emails, and query-string tokens from logs."""
    if not line:
        return line

    # 1. Redact JWT tokens (e.g. eyJhbGciOi...)
    line = re.sub(r'\bey[a-zA-Z0-9_-]+\.ey[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b', '[JWT_TOKEN_REDACTED]', line)

    # 2. Redact Email addresses
    line = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]', line)

    # 3. Redact query parameters or config assignments (e.g., token=xxx, pass=xxx)
    line = re.sub(r'(?i)(token|password|pass|access_token|secure_streaming_token|s)=[^&\s\)]+', r'\1=***', line)

    return line


def clean_temp_files(title: str, output_dir: str):
    """Purge orphaned temporary files (.part, .ytdl, etc.) for a given title."""
    if not title or len(title) < 3:
        return

    # Sanitize title to match filename pattern
    sanitized_title = re.sub(r'[\\/:*?"<>|]', '_', title).strip(' .')
    
    path = Path(output_dir)
    if not path.exists() or not path.is_dir():
        return

    # Common temporary extensions used by yt-dlp, aria2, and ffmpeg
    temp_extensions = [".part", ".ytdl", ".temp", ".tmp", ".aria2", ".aria2__temp"]
    
    try:
        for f in path.iterdir():
            if f.is_file():
                # Check if filename contains the sanitized title and has a temporary extension
                if sanitized_title in f.name:
                    if any(f.name.endswith(ext) for ext in temp_extensions) or f.suffix == ".part":
                        try:
                            f.unlink()
                            logger.info(f"Cleaned up temporary file: {f.name}")
                        except OSError as e:
                            logger.warning(f"Could not delete temp file {f.name}: {e}")
    except Exception as e:
        logger.error(f"Error while cleaning temp files for title '{title}': {e}")


class DownloadDatabase:
    """SQLite database for persistent download queue."""
    
    def __init__(self, db_path: str = None):
        if not db_path:
            db_path = str(PROJECT_ROOT / ".videodownload" / "downloads.db")
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id TEXT PRIMARY KEY,
                    service TEXT NOT NULL,
                    title TEXT NOT NULL,
                    cmd TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    progress REAL DEFAULT 0.0,
                    speed TEXT DEFAULT '',
                    eta TEXT DEFAULT '',
                    logs TEXT DEFAULT '[]',
                    retry_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_recordings (
                    id TEXT PRIMARY KEY,
                    channel_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    duration INTEGER NOT NULL,
                    status TEXT DEFAULT 'scheduled'
                )
            """)
            conn.commit()
    
    def save_download(self, item: 'DownloadItem'):
        """Save download item to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO downloads 
                    (id, service, title, cmd, status, progress, speed, eta, logs, retry_count, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.id, item.service, item.title, json.dumps(item.cmd),
                    item.status, item.progress, item.speed, item.eta,
                    json.dumps(item.logs), item.retry_count, datetime.now().isoformat()
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save download to database: {e}")
    
    def load_downloads(self) -> List[Dict[str, Any]]:
        """Load all downloads from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM downloads WHERE status NOT IN ('finished', 'cancelled')")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to load downloads from database: {e}")
            return []
    
    def delete_download(self, item_id: str):
        """Delete download from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM downloads WHERE id = ?", (item_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to delete download from database: {e}")

    def save_scheduled(self, item: Dict[str, Any]):
        """Save a scheduled recording to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO scheduled_recordings 
                    (id, channel_name, title, start_time, duration, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    item["id"], item["channel_name"], item["title"],
                    item["start_time"], item["duration"], item["status"]
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save scheduled recording to database: {e}")

    def load_scheduled(self) -> List[Dict[str, Any]]:
        """Load all scheduled recordings from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM scheduled_recordings")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to load scheduled recordings from database: {e}")
            return []

    def delete_scheduled(self, item_id: str):
        """Delete a scheduled recording from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM scheduled_recordings WHERE id = ?", (item_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to delete scheduled recording from database: {e}")
 

class DownloadItem:
    """Represents a single download task."""
    
    def __init__(self, service: str, title: str, cmd: List[str]):
        self.id = str(uuid.uuid4())
        self.service = service
        self.title = title
        self.cmd = cmd
        self.status: str = DownloadStatus.PENDING
        self.progress = 0.0
        self.speed = ""
        self.eta = ""
        self.logs: List[str] = []
        self.process: asyncio.subprocess.Process = None
        self.cancel_event = threading.Event()
        self.retry_count = 0
        self.created_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "service": self.service,
            "title": self.title,
            "status": self.status,
            "progress": self.progress,
            "speed": self.speed,
            "eta": self.eta,
            "logs": self.logs[-200:],  # Keep last 200 lines
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat()
        }


class DownloadQueueManager:
    """Manages download queue with rate limiting, persistence, and retries."""
    
    def __init__(self):
        self.items: Dict[str, DownloadItem] = {}
        self.active_websockets: Set[WebSocket] = set()
        self._lock = None
        self.running_count = 0
        self.db = DownloadDatabase()
        
        # Load persisted downloads on startup
        self._load_persisted_downloads()

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock
    
    def _load_persisted_downloads(self):
        """Load previous downloads from database."""
        try:
            downloads = self.db.load_downloads()
            for dl in downloads:
                item = DownloadItem(dl['service'], dl['title'], json.loads(dl['cmd']))
                item.id = dl['id']
                item.status = dl['status']
                item.progress = dl['progress']
                item.retry_count = dl['retry_count']
                item.logs = json.loads(dl['logs']) if dl['logs'] else []
                self.items[item.id] = item
                logger.info(f"Loaded persisted download: {item.title}")
        except Exception as e:
            logger.warning(f"Could not load persisted downloads: {e}")

    async def resume_pending_downloads(self):
        """Re-queue downloads that were pending or interrupted before restart."""
        to_resume: List[DownloadItem] = []
        async with self.lock:
            for item in self.items.values():
                if item.status not in ("pending", "downloading"):
                    continue
                if item.status == DownloadStatus.DOWNLOADING:
                    item.status = DownloadStatus.PENDING
                    item.progress = 0.0
                    item.speed = ""
                    item.eta = ""
                    item.logs.append("\n[Resuming after server restart]")
                    self.db.save_download(item)
                to_resume.append(item)

        for item in to_resume:
            logger.info("Resuming download: %s (%s)", item.title, item.id)
            asyncio.create_task(self._process_download(item.id))

        if to_resume:
            await self.broadcast_state()

    async def register_websocket(self, websocket: WebSocket):
        """Register a WebSocket connection."""
        await websocket.accept()
        self.active_websockets.add(websocket)
        await self.broadcast_state()
        await self.broadcast_scheduled()

    def unregister_websocket(self, websocket: WebSocket):
        """Unregister a WebSocket connection."""
        self.active_websockets.discard(websocket)

    async def broadcast_state(self):
        """Broadcast current state to all connected clients."""
        if not self.active_websockets:
            return
        state = [item.to_dict() for item in self.items.values()]
        payload = {"type": "queue_update", "data": state}
        
        disconnected = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.append(ws)
        
        for ws in disconnected:
            self.unregister_websocket(ws)

    async def broadcast_sniffer(self, service: str, sniffer_type: str, url: str, headers: Dict[str, str] = None, title: str = ""):
        """Broadcast a dynamic sniffed URL to all connected frontend clients."""
        if not self.active_websockets:
            return
        payload = {
            "type": "sniffer_update",
            "data": {
                "service": service,
                "type": sniffer_type,
                "url": url,
                "headers": headers or {},
                "title": title
            }
        }
        
        disconnected = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.append(ws)
        
        for ws in disconnected:
            self.unregister_websocket(ws)

    async def broadcast_transcode_update(
        self,
        item_id: str,
        title: str,
        status: str,
        detail: str = "",
    ):
        if not self.active_websockets:
            return
        payload = {
            "type": "transcode_update",
            "data": {
                "item_id": item_id,
                "title": title,
                "status": status,
                "detail": detail,
            },
        }
        disconnected = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.unregister_websocket(ws)

    async def broadcast_sniffer_ready(self, service: str, capture: Dict):
        if not self.active_websockets:
            return
        payload = {"type": "sniffer_ready", "data": {"service": service, "capture": capture}}
        disconnected = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.unregister_websocket(ws)

    async def broadcast_sniffer_download_queued(
        self,
        service: str,
        task_id: str,
        title: str,
        *,
        auto: bool = False,
    ):
        if not self.active_websockets:
            return
        payload = {
            "type": "sniffer_download_queued",
            "data": {"service": service, "task_id": task_id, "title": title, "auto": auto},
        }
        disconnected = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.unregister_websocket(ws)

    async def broadcast_session_import(
        self,
        services: List[str],
        message: str = "",
        source: str = "bridge",
    ):
        """Notify UI that browser/Tampermonkey imported session tokens."""
        if not self.active_websockets:
            return
        payload = {
            "type": "session_imported",
            "data": {
                "services": services,
                "message": message,
                "source": source,
            },
        }
        disconnected = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.unregister_websocket(ws)

    async def broadcast_scheduled(self):
        """Broadcast all scheduled recordings to all connected clients."""
        if not self.active_websockets:
            return
        scheduled_list = self.db.load_scheduled()
        payload = {"type": "scheduled_update", "data": scheduled_list}
        
        disconnected = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.append(ws)
        
        for ws in disconnected:
            self.unregister_websocket(ws)

    async def add_scheduled_recording(self, channel_name: str, title: str, start_time: str, duration: int) -> str:
        """Add a new scheduled recording task."""
        item_id = str(uuid.uuid4())
        item = {
            "id": item_id,
            "channel_name": channel_name,
            "title": title,
            "start_time": start_time,
            "duration": duration,
            "status": "scheduled"
        }
        self.db.save_scheduled(item)
        logger.info(f"Scheduled EON recording: {title} on {channel_name} at {start_time}")
        await self.broadcast_scheduled()
        return item_id

    async def cancel_scheduled_recording(self, item_id: str):
        """Cancel/delete a scheduled recording task."""
        self.db.delete_scheduled(item_id)
        logger.info(f"Cancelled EON scheduled recording: {item_id}")
        await self.broadcast_scheduled()

    def list_scheduled_recordings(self) -> List[Dict[str, Any]]:
        """List all EON scheduled recordings."""
        return self.db.load_scheduled()

    async def scheduler_daemon_loop(self):
        """Continuously polls the scheduled recordings and triggers tasks when start time is reached."""
        logger.info("IPTV scheduled recording daemon started!")
        while True:
            try:
                # Load all scheduled items
                scheduled_items = self.db.load_scheduled()
                current_time_str = datetime.now().isoformat()
                
                # Check for scheduled items that need to start
                for item in scheduled_items:
                    if item["status"] == "scheduled" and current_time_str >= item["start_time"]:
                        logger.info(f"Triggering scheduled recording: {item['title']} on {item['channel_name']}")

                        item["status"] = "triggering"
                        self.db.save_scheduled(item)

                        from backend.services.eon_adapter import EonAdapter
                        try:
                            cmd = EonAdapter.make_download_cmd(
                                mode="live",
                                target=item["channel_name"],
                                duration=item["duration"],
                                play=False
                            )
                            task_id = await self.add_download(
                                service="eon",
                                title=f"DVR Snimanje: {item['title']}",
                                cmd=cmd
                            )
                            item["status"] = "completed"
                            item["task_id"] = task_id
                            self.db.save_scheduled(item)
                        except Exception as cmd_err:
                            logger.error(f"Failed to build DVR command: {cmd_err}")
                            item["status"] = "failed"
                            self.db.save_scheduled(item)
                        
                        # Broadcast updated scheduler list to clients
                        await self.broadcast_scheduled()
            except Exception as loop_err:
                logger.error(f"Error in DVR scheduler daemon: {loop_err}")
            
            await asyncio.sleep(10)


    def _job_fingerprint(self, service: str, cmd: List[str]) -> str:
        """Stable hash of (service, normalized_cmd) for dedup."""
        import hashlib
        normalized = json.dumps([service] + [a for a in cmd if a not in SENSITIVE_CLI_FLAGS], sort_keys=False)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    async def add_download(self, service: str, title: str, cmd: List[str]) -> str:
        """Add a new download to the queue. Rejects duplicates that are already active."""
        fingerprint = self._job_fingerprint(service, cmd)
        async with self.lock:
            for existing in self.items.values():
                if existing.status in (DownloadStatus.PENDING, DownloadStatus.DOWNLOADING):
                    if self._job_fingerprint(existing.service, existing.cmd) == fingerprint:
                        logger.info("Duplicate download rejected: %s (%s)", title, service)
                        return existing.id

            item = DownloadItem(service, title, cmd)
            self.items[item.id] = item
            logger.info("Added download: %s (%s)", title, service)
            self.db.save_download(item)
            
        asyncio.create_task(self._process_download(item.id))
        await self.broadcast_state()
        return item.id

    async def cancel_download(self, item_id: str):
        """Cancel a download."""
        async with self.lock:
            item = self.items.get(item_id)
            if not item:
                return
            if item.status in (DownloadStatus.PENDING, DownloadStatus.DOWNLOADING):
                item.status = DownloadStatus.CANCELLED
                item.logs.append("\n[Download cancelled by user]")
                item.cancel_event.set()
                if item.process:
                    try:
                        item.process.terminate()
                        await asyncio.sleep(0.5)
                        if item.process.returncode is None:
                            item.process.kill()
                    except Exception as e:
                        logger.error(f"Error terminating process: {e}")
                
                # Retrieve output folder for cleanup
                from backend.jobs.inprocess import get_output_dir_from_cmd
                output_dir = get_output_dir_from_cmd(item.cmd) or config.get_output_dir()
                
                # Perform cleanup of temporary fragments
                clean_temp_files(item.title, output_dir)
                self.db.save_download(item)
        await self.broadcast_state()

    async def retry_download(self, item_id: str) -> bool:
        """Retry a failed, finished, or cancelled download."""
        async with self.lock:
            item = self.items.get(item_id)
            if not item:
                return False
            if item.status in (DownloadStatus.FAILED, DownloadStatus.CANCELLED, DownloadStatus.FINISHED):
                item.status = DownloadStatus.PENDING
                item.progress = 0.0
                item.speed = ""
                item.eta = ""
                item.retry_count = 0
                item.logs.append("\n[Re-submitting task to queue by user...]")
                self.db.save_download(item)
            else:
                return False
        
        # Re-trigger background execution
        asyncio.create_task(self._process_download(item.id))
        await self.broadcast_state()
        return True

    async def clear_completed(self):
        """Clear finished/failed/cancelled downloads."""
        async with self.lock:
            to_remove = [k for k, v in self.items.items() if v.status in (DownloadStatus.FINISHED, DownloadStatus.FAILED, DownloadStatus.CANCELLED)]
            for k in to_remove:
                self.db.delete_download(k)
                del self.items[k]
        await self.broadcast_state()

    def _parse_progress(self, line: str, item: DownloadItem):
        """Extract progress, speed, and ETA from output lines (yt-dlp, aria2, ffmpeg)."""
        pct_match = re.search(r"(\d+(?:\.\d+)?)%", line)
        if pct_match:
            try:
                item.progress = float(pct_match.group(1))
            except ValueError:
                pass

        speed_match = re.search(r"(?:speed=|at\s+)?(\d+(?:\.\d+)?\s*(?:[kKmMgG][iI]?[bB]/s|B/s))", line)
        if speed_match:
            item.speed = speed_match.group(1).strip()

        ffmpeg_speed = re.search(r"speed=\s*([\d.]+)x", line)
        if ffmpeg_speed:
            item.speed = f"{ffmpeg_speed.group(1)}x"

        eta_match = re.search(r"(?:[eE][tT][aA]=?|\bETA\b\s+)(\d{2}:\d{2}(?::\d{2})?|\d+[smh])", line)
        if eta_match:
            item.eta = eta_match.group(1).strip()

        ffmpeg_time = re.search(r"time=(\d{2}:\d{2}:\d{2}(?:\.\d+)?)", line)
        ffmpeg_dur = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2}(?:\.\d+)?)", line)
        if ffmpeg_dur:
            item._ffmpeg_duration = ffmpeg_dur.group(1)
        if ffmpeg_time and hasattr(item, "_ffmpeg_duration") and item._ffmpeg_duration:
            try:
                def _ts_seconds(ts: str) -> float:
                    parts = ts.split(":")
                    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                cur = _ts_seconds(ffmpeg_time.group(1))
                total = _ts_seconds(item._ffmpeg_duration)
                if total > 0:
                    item.progress = min(round((cur / total) * 100, 1), 99.9)
            except (ValueError, IndexError):
                pass

    async def _wait_for_slot(self, item: DownloadItem) -> bool:
        """Wait until a download slot is available. Returns False if cancelled while waiting."""
        while self.running_count >= MAX_CONCURRENT_DOWNLOADS:
            if item.status == DownloadStatus.CANCELLED or item.cancel_event.is_set():
                return False
            await asyncio.sleep(0.5)
        return True

    def _is_cancelled(self, item: DownloadItem) -> bool:
        return item.status == DownloadStatus.CANCELLED or item.cancel_event.is_set()

    async def _process_download(self, item_id: str):
        """Process a single download with retry logic and rate limiting."""
        item = self.items.get(item_id)
        if not item:
            return
        if self._is_cancelled(item):
            async with self.lock:
                item.status = DownloadStatus.CANCELLED
                self.db.save_download(item)
            await self.broadcast_state()
            return

        if not await self._wait_for_slot(item):
            async with self.lock:
                item.status = DownloadStatus.CANCELLED
                self.db.save_download(item)
            await self.broadcast_state()
            return

        async with self.lock:
            self.running_count += 1

        success = False
        try:
            while item.retry_count < MAX_RETRIES:
                if self._is_cancelled(item):
                    break
                async with self.lock:
                    item.status = DownloadStatus.DOWNLOADING
                    item.logs.append(f"\n[Attempt {item.retry_count + 1}/{MAX_RETRIES}]")
                    item.logs.append(f"[Command]: {redact_command(item.cmd)}\n")
                    await self.broadcast_state()

                try:
                    from backend.utils.rate_limiter import upstream_limiter
                    await asyncio.get_event_loop().run_in_executor(
                        None, upstream_limiter.wait, item.service
                    )
                    success = await self._run_download_process(item)
                    if self._is_cancelled(item):
                        break
                    if success:
                        break
                    item.retry_count += 1
                    if item.retry_count < MAX_RETRIES and not self._is_cancelled(item):
                        item.logs.append(f"\n[Retrying... (attempt {item.retry_count + 1}/{MAX_RETRIES})]")
                        await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Download process error: {e}")
                    if self._is_cancelled(item):
                        break
                    item.retry_count += 1
        finally:
            async with self.lock:
                self.running_count -= 1

        # Final status update
        async with self.lock:
            if self._is_cancelled(item):
                item.status = DownloadStatus.CANCELLED
                self.db.save_download(item)
                await self.broadcast_state()
                return
            if item.retry_count < MAX_RETRIES and success:
                item.status = DownloadStatus.FINISHED
                item.progress = 100.0
                item.logs.append("\n[✓ Download completed successfully!]")

                try:
                    trans_mode = config.get_transcode_mode()
                    if trans_mode and trans_mode != "off":
                        from backend.services.transcoder import find_and_transcode_completed
                        from backend.jobs.inprocess import get_output_dir_from_cmd
                        output_dir_val = get_output_dir_from_cmd(item.cmd) or config.get_output_dir()
                        loop = asyncio.get_running_loop()

                        def on_start(path: str) -> None:
                            item.logs.append(f"\n[Transcode started: {path}]")
                            asyncio.run_coroutine_threadsafe(
                                self.broadcast_transcode_update(
                                    item.id, item.title, "started", path
                                ),
                                loop,
                            )
                            asyncio.run_coroutine_threadsafe(self.broadcast_state(), loop)

                        def on_complete(result: Optional[str]) -> None:
                            status = "finished" if result else "failed"
                            detail = result or "Transcode failed"
                            item.logs.append(f"\n[Transcode {status}: {detail}]")
                            asyncio.run_coroutine_threadsafe(
                                self.broadcast_transcode_update(
                                    item.id, item.title, status, detail
                                ),
                                loop,
                            )
                            asyncio.run_coroutine_threadsafe(self.broadcast_state(), loop)

                        find_and_transcode_completed(
                            item.title,
                            output_dir_val,
                            trans_mode,
                            on_start=on_start,
                            on_complete=on_complete,
                        )
                except Exception as trans_err:
                    logger.error(f"Failed to initiate automatic transcode: {trans_err}")
            else:
                item.status = DownloadStatus.FAILED
                item.logs.append(f"\n[✗ Download failed after {MAX_RETRIES} attempts]")

                from backend.jobs.inprocess import get_output_dir_from_cmd
                output_dir = get_output_dir_from_cmd(item.cmd) or config.get_output_dir()
                clean_temp_files(item.title, output_dir)

            self.db.save_download(item)

        await self.broadcast_state()

    async def _run_inprocess_job(self, item: DownloadItem) -> bool:
        """Run a Python in-process download job (Voyo, HBO Max, …)."""
        from backend.jobs.inprocess import execute_job, parse_job

        loop = asyncio.get_running_loop()
        payload = parse_job(item.cmd)
        last_broadcast = time.monotonic()
        broadcast_interval = 0.3

        def log_line(line: str) -> None:
            nonlocal last_broadcast
            if item.cancel_event.is_set():
                from backend.jobs.exceptions import JobCancelled
                raise JobCancelled("Download cancelled by user")
            scrubbed = redact_log_line(line)
            item.logs.append(scrubbed)
            self._parse_progress(scrubbed, item)
            now = time.monotonic()
            if now - last_broadcast >= broadcast_interval:
                asyncio.run_coroutine_threadsafe(self.broadcast_state(), loop)
                last_broadcast = now

        def run_sync() -> bool:
            try:
                return execute_job(payload, log_line, item.cancel_event)
            except Exception as exc:
                from backend.jobs.exceptions import JobCancelled
                if isinstance(exc, JobCancelled):
                    log_line("INFO Preuzimanje otkazano od strane korisnika.")
                    return False
                log_line(f"ERROR {exc}")
                logger.exception("In-process job failed")
                return False

        return await loop.run_in_executor(None, run_sync)

    async def _run_download_process(self, item: DownloadItem) -> bool:
        """Execute the download command and return success status."""
        try:
            from backend.jobs.inprocess import is_inprocess_job, get_output_dir_from_cmd

            if is_inprocess_job(item.cmd):
                return await self._run_inprocess_job(item)

            cmd = list(item.cmd)
            if cmd and cmd[0] == "python":
                cmd[0] = sys.executable

            env = os.environ.copy()
            root = str(PROJECT_ROOT)
            env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")

            item.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=root,
                env=env,
            )

            last_broadcast = time.monotonic()
            BROADCAST_INTERVAL = 0.3

            try:
                # Read output with timeout
                async with asyncio.timeout(DOWNLOAD_TIMEOUT):
                    while True:
                        if item.cancel_event.is_set():
                            if item.process and item.process.returncode is None:
                                try:
                                    item.process.terminate()
                                    await asyncio.sleep(0.5)
                                    if item.process.returncode is None:
                                        item.process.kill()
                                except OSError as kill_err:
                                    logger.debug(f"Process kill after cancel: {kill_err}")
                            from backend.jobs.exceptions import JobCancelled
                            raise JobCancelled("Download cancelled by user")
                        line_bytes = await item.process.stdout.readline()
                        if not line_bytes:
                            break
                        line = line_bytes.decode("utf-8", errors="ignore").rstrip()
                        
                        # Apply regex log scrub filter before saving or sending logs to database/client
                        scrubbed_line = redact_log_line(line)
                        item.logs.append(scrubbed_line)
                        
                        self._parse_progress(scrubbed_line, item)
                        
                        now = time.monotonic()
                        if now - last_broadcast >= BROADCAST_INTERVAL:
                            await self.broadcast_state()
                            last_broadcast = now

                    await item.process.wait()
            except asyncio.TimeoutError:
                item.logs.append(f"\n[Timeout: Download exceeded {DOWNLOAD_TIMEOUT}s limit]")
                if item.process:
                    try:
                        item.process.terminate()
                        await asyncio.sleep(0.5)
                        if item.process.returncode is None:
                            item.process.kill()
                    except OSError as kill_err:
                        logger.debug(f"Process kill on timeout: {kill_err}")
                return False

            return item.process.returncode == 0

        except Exception as e:
            from backend.jobs.exceptions import JobCancelled
            if isinstance(e, JobCancelled):
                return False
            item.logs.append(f"\n[Error]: {str(e)}")
            logger.error(f"Error running download: {e}")
            return False


# Singleton queue manager
queue_manager = DownloadQueueManager()

