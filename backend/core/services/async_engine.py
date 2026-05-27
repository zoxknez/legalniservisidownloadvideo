import os
import sys
import time
import random
import asyncio
import logging
from typing import List, Dict, Callable, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import aiohttp, fallback gracefully if not installed
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_AIOHTTP = False
    logger.warning("aiohttp not found; falling back to thread-pool-based urllib downloader.")


class AsyncDownloadEngine:
    """
    Enterprise-grade asynchronous download engine for high-performance segment and file fetching.
    Supports:
      - Connection pooling (via aiohttp when available).
      - Graceful fallback to thread-pool-driven standard urllib.
      - Asynchronous multi-worker parallel chunk/segment download.
      - Robust exponential backoff with jitter.
      - Real-time progress, speed, and ETA tracking.
      - Resilience to transient network failures.
    """

    def __init__(
        self,
        max_workers: int = 8,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        timeout: float = 20.0
    ):
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self._lock = asyncio.Lock()

    def _get_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with random jitter."""
        delay = min(self.max_delay, self.base_delay * (2 ** attempt))
        jitter = random.uniform(0.0, 1.0)
        return delay + jitter

    # ── aiohttp Engine Implementation ──────────────────────────────────────────

    async def _download_segment_aiohttp(
        self,
        session: "aiohttp.ClientSession",
        url: str,
        dest_path: Path,
        headers: Dict[str, str],
        semaphore: asyncio.Semaphore,
        stats: dict,
        progress_callback: Optional[Callable[[int, int], None]]
    ) -> bool:
        """Download a single segment asynchronously using aiohttp with retry logic."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with semaphore:
            for attempt in range(self.max_retries):
                try:
                    async with session.get(url, headers=headers, timeout=self.timeout) as resp:
                        if resp.status != 200:
                            raise RuntimeError(f"HTTP status {resp.status}")
                        
                        # Fetch segment chunk by chunk
                        total_bytes = 0
                        with open(dest_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(1024 * 64):
                                f.write(chunk)
                                total_bytes += len(chunk)
                                
                                # Track global stats and trigger progress callback
                                async with self._lock:
                                    stats["downloaded_bytes"] += len(chunk)
                                    if progress_callback:
                                        progress_callback(stats["downloaded_bytes"], stats["total_estimated_bytes"])

                        return True
                except Exception as e:
                    delay = self._get_backoff_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed for {url}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(delay)
            
            logger.error(f"Failed to download segment after {self.max_retries} attempts: {url}")
            return False

    # ── urllib Fallback Engine Implementation ──────────────────────────────────

    def _download_segment_urllib_sync(
        self,
        url: str,
        dest_path: Path,
        headers: Dict[str, str]
    ) -> bool:
        """Download a single segment synchronously using urllib (run inside thread pool)."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        req = urllib.request.Request(url, headers=headers or {})
        
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    if response.status != 200:
                        raise RuntimeError(f"HTTP status {response.status}")
                    
                    with open(dest_path, "wb") as f:
                        shutil_block_size = 1024 * 64
                        while True:
                            chunk = response.read(shutil_block_size)
                            if not chunk:
                                break
                            f.write(chunk)
                return True
            except Exception as e:
                delay = self._get_backoff_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed (urllib) for {url}: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                if attempt < self.max_retries - 1:
                    time.sleep(delay)
        return False

    async def _download_segment_urllib(
        self,
        url: str,
        dest_path: Path,
        headers: Dict[str, str],
        semaphore: asyncio.Semaphore,
        stats: dict,
        progress_callback: Optional[Callable[[int, int], None]]
    ) -> bool:
        """Wrap the synchronous urllib worker inside a thread pool executor."""
        loop = asyncio.get_running_loop()
        async with semaphore:
            success = False
            # Execute in default ThreadPoolExecutor
            success = await loop.run_in_executor(
                None,
                self._download_segment_urllib_sync,
                url,
                dest_path,
                headers
            )
            
            if success:
                # Estimate segment size for progress tracking (average segment is ~1.5MB if unknown)
                file_size = dest_path.stat().st_size if dest_path.exists() else 1024 * 1024
                async with self._lock:
                    stats["downloaded_bytes"] += file_size
                    if progress_callback:
                        progress_callback(stats["downloaded_bytes"], stats["total_estimated_bytes"])
            return success

    # ── Public APIs ────────────────────────────────────────────────────────────

    async def download_segments(
        self,
        urls: List[str],
        dest_paths: List[Path],
        headers: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        Download multiple segment URLs in parallel.
        
        Args:
            urls:              List of URLs to download.
            dest_paths:        Corresponding file paths where segments will be saved.
            headers:           HTTP headers to send with the requests.
            progress_callback: Optional callback receiving (downloaded_bytes, total_estimated_bytes).
            
        Returns:
            True if all segments downloaded successfully, False otherwise.
        """
        if not urls or not dest_paths or len(urls) != len(dest_paths):
            logger.error("Invalid arguments: empty list or length mismatch.")
            return False

        stats = {
            "downloaded_bytes": 0,
            "total_estimated_bytes": len(urls) * 1024 * 1024 * 1.5  # Estimate 1.5MB per HLS segment
        }
        
        semaphore = asyncio.Semaphore(self.max_workers)
        
        start_time = time.monotonic()
        logger.info(f"Starting parallel download of {len(urls)} segments using max {self.max_workers} workers.")

        if HAS_AIOHTTP:
            connector = aiohttp.TCPConnector(limit=self.max_workers, force_close=False, enable_cleanup_closed=True)
            async with aiohttp.ClientSession(connector=connector) as session:
                tasks = [
                    self._download_segment_aiohttp(
                        session, url, dest_paths[i], headers or {}, semaphore, stats, progress_callback
                    )
                    for i, url in enumerate(urls)
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            tasks = [
                self._download_segment_urllib(
                    url, dest_paths[i], headers or {}, semaphore, stats, progress_callback
                )
                for i, url in enumerate(urls)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        success = all(isinstance(r, bool) and r for r in results)
        duration = time.monotonic() - start_time
        
        if success:
            logger.info(f"Successfully downloaded {len(urls)} segments in {duration:.2f} seconds.")
        else:
            logger.error(f"Parallel download failed. Not all segments were fetched successfully.")
            
        return success

    async def download_file(
        self,
        url: str,
        dest_path: Path,
        headers: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """Download a single large file asynchronously."""
        return await self.download_segments([url], [dest_path], headers, progress_callback)
