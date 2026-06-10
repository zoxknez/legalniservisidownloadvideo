"""In-memory pairing of sniffed manifest + license URLs per streaming service."""
from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


def _norm_service(service: str) -> str:
    s = (service or "").strip().lower()
    if s in ("hbo", "max"):
        return "hbomax"
    if s == "rts":
        return "rtsplaneta"
    return s


@dataclass
class SnifferCapture:
    service: str
    manifest_url: str = ""
    license_url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    title: str = ""
    updated_at: float = field(default_factory=time.time)
    last_queued_at: float = 0.0
    last_queued_task_id: str = ""

    def is_hls(self) -> bool:
        u = (self.manifest_url or "").lower()
        return u.endswith(".m3u8") or "m3u8" in u

    def is_ready(self) -> bool:
        if not self.manifest_url:
            return False
        if self.license_url:
            return True
        return self.is_hls()

    def fingerprint(self) -> str:
        raw = f"{self.service}|{self.manifest_url}|{self.license_url}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_public_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["ready"] = self.is_ready()
        d["fingerprint"] = self.fingerprint()
        return d


class SnifferStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._captures: Dict[str, SnifferCapture] = {}

    def update(
        self,
        service: str,
        sniffer_type: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        title: str = "",
    ) -> SnifferCapture:
        svc = _norm_service(service)
        url = (url or "").strip()
        if not svc or not url:
            raise ValueError("service i url su obavezni")

        with self._lock:
            cap = self._captures.get(svc) or SnifferCapture(service=svc)
            stype = (sniffer_type or "").lower()

            if stype == "manifest":
                cap.manifest_url = url
            elif stype == "license":
                cap.license_url = url
                if headers:
                    cap.headers.update(headers)
            else:
                low = url.lower()
                if ".mpd" in low or ".m3u8" in low or "/manifest" in low:
                    cap.manifest_url = url
                elif "widevine" in low or "license" in low or "/drm" in low:
                    cap.license_url = url
                    if headers:
                        cap.headers.update(headers)

            if title and title.strip():
                cap.title = title.strip()
            cap.updated_at = time.time()
            self._captures[svc] = cap
            return SnifferCapture(**asdict(cap))

    def get(self, service: str) -> Optional[SnifferCapture]:
        svc = _norm_service(service)
        with self._lock:
            cap = self._captures.get(svc)
            if not cap:
                return None
            return SnifferCapture(**asdict(cap))

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [c.to_public_dict() for c in self._captures.values()]

    def mark_queued(self, service: str, task_id: str) -> None:
        svc = _norm_service(service)
        with self._lock:
            cap = self._captures.get(svc)
            if cap:
                cap.last_queued_at = time.time()
                cap.last_queued_task_id = task_id

    def should_auto_queue(self, capture: SnifferCapture, cooldown_sec: int = 300) -> bool:
        if capture.last_queued_at and (time.time() - capture.last_queued_at) < cooldown_sec:
            if capture.last_queued_task_id:
                return False
        return True


sniffer_store = SnifferStore()
