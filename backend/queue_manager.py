import asyncio
import re
import uuid
import time
import logging
from typing import Dict, Any, List, Set
from fastapi import WebSocket
from pathlib import Path
from backend.config import config

# Bug 4 Fix: Dynamic project root instead of hardcoded path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

logger = logging.getLogger(__name__)

SENSITIVE_CLI_FLAGS = {"-p", "--password", "--pass", "--token", "--access-token", "--refresh-token"}


def redact_command(cmd: List[str]) -> str:
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


class DownloadItem:
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "service": self.service,
            "title": self.title,
            "status": self.status,
            "progress": self.progress,
            "speed": self.speed,
            "eta": self.eta,
            "logs": self.logs[-200:]  # Keep last 200 lines to avoid high memory usage
        }

class DownloadQueueManager:
    def __init__(self):
        self.items: Dict[str, DownloadItem] = {}
        self.active_websockets: Set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def register_websocket(self, websocket: WebSocket):
        await websocket.accept()
        self.active_websockets.add(websocket)
        # Send current state immediately
        await self.broadcast_state()

    def unregister_websocket(self, websocket: WebSocket):
        # Bug 3 Fix: Use discard() instead of remove() to avoid KeyError on double-unregister
        self.active_websockets.discard(websocket)

    async def broadcast_state(self):
        if not self.active_websockets:
            return
        state = [item.to_dict() for item in self.items.values()]
        payload = {"type": "queue_update", "data": state}
        
        # Broadcast to all active clients
        disconnected = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.append(ws)
        
        for ws in disconnected:
            self.unregister_websocket(ws)

    async def add_download(self, service: str, title: str, cmd: List[str]) -> str:
        async with self.lock:
            item = DownloadItem(service, title, cmd)
            self.items[item.id] = item
            logger.info(f"Added download: {title} ({service})")
            
        # Start download in background
        asyncio.create_task(self._run_download(item.id))
        await self.broadcast_state()
        return item.id

    async def cancel_download(self, item_id: str):
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
                        # Allow process to terminate gracefully, otherwise kill it
                        await asyncio.sleep(0.5)
                        if item.process.returncode is None:
                            item.process.kill()
                    except Exception as e:
                        logger.error(f"Error terminating process: {e}")
        await self.broadcast_state()

    async def clear_completed(self):
        async with self.lock:
            to_remove = [k for k, v in self.items.items() if v.status in ("finished", "failed", "cancelled")]
            for k in to_remove:
                del self.items[k]
        await self.broadcast_state()

    def _parse_progress(self, line: str, item: DownloadItem):
        # Patterns for yt-dlp & custom scripts
        # 1. Percentage check: e.g. "62.3%"
        pct_match = re.search(r"(\d+(\.\d+)?)%", line)
        if pct_match:
            try:
                item.progress = float(pct_match.group(1))
            except ValueError:
                pass

        # 2. Speed check: e.g. "12.4MB/s" or "speed=12.4MB/s" or "at 5.2MiB/s"
        speed_match = re.search(r"(?:speed=|at\s+)?(\d+(?:\.\d+)?\s*(?:[kKmMgG][iI]?[bB]/s|B/s))", line)
        if speed_match:
            item.speed = speed_match.group(1).strip()

        # 3. ETA check: e.g. "ETA 54s" or "eta=00:54" or "ETA 01:23"
        eta_match = re.search(r"(?:[eE][tT][aA]=?|\bETA\b\s+)(\d{2}:\d{2}(?::\d{2})?|\d+[smh])", line)
        if eta_match:
            item.eta = eta_match.group(1).strip()

    async def _run_download(self, item_id: str):
        item = self.items.get(item_id)
        if not item:
            return

        item.status = "downloading"
        item.logs.append(f"[Running command]: {redact_command(item.cmd)}\n")
        await self.broadcast_state()

        # Bug 4 Fix: Use dynamic PROJECT_ROOT instead of hardcoded path
        try:
            # We run python scripts using the system python interpreter
            # On Windows, python is usually "python"
            # We will use asyncio to capture stdout line-by-line
            item.process = await asyncio.create_subprocess_exec(
                *item.cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(PROJECT_ROOT)
            )

            # Bug 6 Fix: Throttle broadcasts — collect lines and broadcast at most every 300ms
            last_broadcast = time.monotonic()
            BROADCAST_INTERVAL = 0.3  # seconds

            # Read stdout line-by-line asynchronously
            while True:
                line_bytes = await item.process.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="ignore").rstrip()
                
                # Append to logs
                item.logs.append(line)
                
                # Parse progress, speed, ETA
                self._parse_progress(line, item)
                
                # Bug 6 Fix: Only broadcast every 300ms to avoid overloading the frontend
                now = time.monotonic()
                if now - last_broadcast >= BROADCAST_INTERVAL:
                    await self.broadcast_state()
                    last_broadcast = now

            # Wait for process exit code
            await item.process.wait()
            
            async with self.lock:
                if item.status == "cancelled":
                    pass
                elif item.process.returncode == 0:
                    item.status = "finished"
                    item.progress = 100.0
                    item.speed = ""
                    item.eta = ""
                    item.logs.append("\n[Download completed successfully!]")
                else:
                    item.status = "failed"
                    item.logs.append(f"\n[Download failed with exit code: {item.process.returncode}]")
        
        except Exception as e:
            async with self.lock:
                item.status = "failed"
                item.logs.append(f"\n[Internal Error]: {str(e)}")
            logger.error(f"Error running download task {item.title}: {e}")

        await self.broadcast_state()

# Singleton queue manager
queue_manager = DownloadQueueManager()
