import asyncio
import re
import uuid
import time
import logging
import sqlite3
import json
from typing import Dict, Any, List, Set, Optional
from fastapi import WebSocket
from pathlib import Path
from datetime import datetime
from backend.config import config, PROJECT_ROOT

logger = logging.getLogger(__name__)

SENSITIVE_CLI_FLAGS = {"-p", "--password", "--pass", "--token", "--access-token", "--refresh-token"}

# Queue manager configuration
MAX_CONCURRENT_DOWNLOADS = 2
MAX_RETRIES = 3
DOWNLOAD_TIMEOUT = 3600  # 1 hour


def redact_command(cmd: List[str]) -> str:
    """Redact sensitive information from command."""
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


class DownloadItem:
    """Represents a single download task."""
    
    def __init__(self, service: str, title: str, cmd: List[str]):
        self.id = str(uuid.uuid4())
        self.service = service
        self.title = title
        self.cmd = cmd
        self.status = "pending"  # pending, downloading, finished, failed, cancelled
        self.progress = 0.0
        self.speed = ""
        self.eta = ""
        self.logs: List[str] = []
        self.process: asyncio.subprocess.Process = None
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
        self.lock = asyncio.Lock()
        self.running_count = 0
        self.db = DownloadDatabase()
        
        # Load persisted downloads on startup
        self._load_persisted_downloads()
    
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

    async def register_websocket(self, websocket: WebSocket):
        """Register a WebSocket connection."""
        await websocket.accept()
        self.active_websockets.add(websocket)
        await self.broadcast_state()

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

    async def add_download(self, service: str, title: str, cmd: List[str]) -> str:
        """Add a new download to the queue."""
        async with self.lock:
            item = DownloadItem(service, title, cmd)
            self.items[item.id] = item
            logger.info(f"Added download: {title} ({service})")
            self.db.save_download(item)
            
        # Start download in background
        asyncio.create_task(self._process_download(item.id))
        await self.broadcast_state()
        return item.id

    async def cancel_download(self, item_id: str):
        """Cancel a download."""
        async with self.lock:
            item = self.items.get(item_id)
            if not item:
                return
            if item.status in ("pending", "downloading"):
                item.status = "cancelled"
                item.logs.append("\n[Download cancelled by user]")
                if item.process:
                    try:
                        item.process.terminate()
                        await asyncio.sleep(0.5)
                        if item.process.returncode is None:
                            item.process.kill()
                    except Exception as e:
                        logger.error(f"Error terminating process: {e}")
                self.db.save_download(item)
        await self.broadcast_state()

    async def clear_completed(self):
        """Clear finished/failed/cancelled downloads."""
        async with self.lock:
            to_remove = [k for k, v in self.items.items() if v.status in ("finished", "cancelled")]
            for k in to_remove:
                self.db.delete_download(k)
                del self.items[k]
        await self.broadcast_state()

    def _parse_progress(self, line: str, item: DownloadItem):
        """Extract progress, speed, and ETA from output line."""
        pct_match = re.search(r"(\d+(?:\.\d+)?)%", line)
        if pct_match:
            try:
                item.progress = float(pct_match.group(1))
            except ValueError:
                pass

        speed_match = re.search(r"(?:speed=|at\s+)?(\d+(?:\.\d+)?\s*(?:[kKmMgG][iI]?[bB]/s|B/s))", line)
        if speed_match:
            item.speed = speed_match.group(1).strip()

        eta_match = re.search(r"(?:[eE][tT][aA]=?|\bETA\b\s+)(\d{2}:\d{2}(?::\d{2})?|\d+[smh])", line)
        if eta_match:
            item.eta = eta_match.group(1).strip()

    async def _wait_for_slot(self):
        """Wait until a download slot is available (rate limiting)."""
        while self.running_count >= MAX_CONCURRENT_DOWNLOADS:
            await asyncio.sleep(0.5)

    async def _process_download(self, item_id: str):
        """Process a single download with retry logic and rate limiting."""
        item = self.items.get(item_id)
        if not item:
            return

        # Wait for a free slot
        await self._wait_for_slot()

        while item.retry_count < MAX_RETRIES:
            async with self.lock:
                self.running_count += 1
                item.status = "downloading"
                item.logs.append(f"\n[Attempt {item.retry_count + 1}/{MAX_RETRIES}]")
                item.logs.append(f"[Command]: {redact_command(item.cmd)}\n")
                await self.broadcast_state()

            try:
                success = await self._run_download_process(item)
                if success:
                    break
                else:
                    item.retry_count += 1
                    if item.retry_count < MAX_RETRIES:
                        item.logs.append(f"\n[Retrying... (attempt {item.retry_count + 1}/{MAX_RETRIES})]")
                        await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Download process error: {e}")
                item.retry_count += 1

            async with self.lock:
                self.running_count -= 1

        # Final status update
        async with self.lock:
            if item.status != "cancelled":
                if item.retry_count < MAX_RETRIES and success:
                    item.status = "finished"
                    item.progress = 100.0
                    item.logs.append("\n[✓ Download completed successfully!]")
                else:
                    item.status = "failed"
                    item.logs.append(f"\n[✗ Download failed after {MAX_RETRIES} attempts]")
            self.db.save_download(item)

        await self.broadcast_state()

    async def _run_download_process(self, item: DownloadItem) -> bool:
        """Execute the download command and return success status."""
        try:
            item.process = await asyncio.create_subprocess_exec(
                *item.cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(PROJECT_ROOT)
            )

            last_broadcast = time.monotonic()
            BROADCAST_INTERVAL = 0.3

            try:
                # Read output with timeout
                async with asyncio.timeout(DOWNLOAD_TIMEOUT):
                    while True:
                        line_bytes = await item.process.stdout.readline()
                        if not line_bytes:
                            break
                        line = line_bytes.decode("utf-8", errors="ignore").rstrip()
                        item.logs.append(line)
                        self._parse_progress(line, item)
                        
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
                    except:
                        pass
                return False

            return item.process.returncode == 0

        except Exception as e:
            item.logs.append(f"\n[Error]: {str(e)}")
            logger.error(f"Error running download: {e}")
            return False


# Singleton queue manager
queue_manager = DownloadQueueManager()

