"""Per-service rate limiter to prevent aggressive upstream scraping."""
import threading
import time
from typing import Dict


class ServiceRateLimiter:
    """Token-bucket rate limiter per service name.

    Args:
        requests_per_minute: Max sustained requests per minute per service.
    """

    def __init__(self, requests_per_minute: int = 30):
        self._interval = 60.0 / requests_per_minute
        self._last_call: Dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, service: str) -> None:
        """Block until the next request is allowed for *service*."""
        with self._lock:
            now = time.monotonic()
            last = self._last_call.get(service, 0.0)
            wait_time = self._interval - (now - last)
            if wait_time > 0:
                time.sleep(wait_time)
            self._last_call[service] = time.monotonic()

    def try_acquire(self, service: str) -> bool:
        """Non-blocking: return True if allowed, False if throttled."""
        with self._lock:
            now = time.monotonic()
            last = self._last_call.get(service, 0.0)
            if now - last >= self._interval:
                self._last_call[service] = now
                return True
            return False


upstream_limiter = ServiceRateLimiter(requests_per_minute=30)
