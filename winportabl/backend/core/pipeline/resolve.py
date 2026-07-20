"""
Multi-path stream resolution ladder.

Tries strategies in order until one returns a usable stream descriptor.
Used by services when API playback fails or sniffer provides a fallback.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("pipeline.resolve")


@dataclass
class StreamResolve:
    """Normalized playback package for download engines."""

    mpd_url: str = ""
    license_url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    title: str = ""
    source: str = ""  # api | refresh | sniffer | degrade
    meta: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        return bool(self.mpd_url and self.mpd_url.strip())


ResolveFn = Callable[[], Optional[StreamResolve]]


@dataclass
class ResolveAttempt:
    name: str
    ok: bool
    error: str = ""
    resolve: Optional[StreamResolve] = None


def resolve_stream_ladder(
    steps: List[tuple[str, ResolveFn]],
    *,
    require_license: bool = False,
) -> StreamResolve:
    """
    Run named resolve strategies in order.

    steps: [(name, callable), ...] e.g. ("api", fn), ("refresh", fn), ("sniffer", fn)
    require_license: if True, mpd-only results are treated as incomplete.
    """
    attempts: List[ResolveAttempt] = []
    last_err = ""

    for name, fn in steps:
        try:
            logger.info("[resolve] trying path=%s", name)
            result = fn()
            if result is None or not result.is_valid():
                attempts.append(ResolveAttempt(name=name, ok=False, error="empty result"))
                last_err = f"{name}: empty"
                continue
            if require_license and not (result.license_url or "").strip():
                # HLS without license is OK for require_license=False only
                url = result.mpd_url.lower()
                if ".m3u8" not in url:
                    attempts.append(
                        ResolveAttempt(name=name, ok=False, error="missing license_url")
                    )
                    last_err = f"{name}: missing license"
                    continue
            result.source = result.source or name
            attempts.append(ResolveAttempt(name=name, ok=True, resolve=result))
            logger.info(
                "[resolve] OK path=%s mpd=%s…",
                name,
                result.mpd_url[:64],
            )
            # Notify UI when non-primary path wins (sniffer / refresh / catalog)
            failed_before = [a.name for a in attempts if not a.ok]
            if name not in ("api", "direct") or failed_before:
                _notify_resolve_fallback(
                    service=str((result.meta or {}).get("service") or ""),
                    path=name,
                    title=result.title or "",
                    failed_paths=failed_before,
                )
            return result
        except Exception as exc:
            msg = str(exc)
            logger.warning("[resolve] path=%s failed: %s", name, msg)
            attempts.append(ResolveAttempt(name=name, ok=False, error=msg))
            last_err = f"{name}: {msg}"

    tried = ", ".join(a.name for a in attempts) or "(none)"
    raise RuntimeError(
        f"Nijedan resolve path nije uspeo ({tried}). Poslednja greška: {last_err}"
    )


def _notify_resolve_fallback(
    *,
    service: str,
    path: str,
    title: str = "",
    failed_paths: Optional[List[str]] = None,
) -> None:
    """Log + optional WS toast when resolve used a fallback path."""
    if path in ("api", "direct") and not failed_paths:
        return
    msg = f"Resolve fallback: {path}"
    if service:
        msg = f"[{service}] {msg}"
    if failed_paths:
        msg += f" (pokušano: {', '.join(failed_paths)})"
    logger.info("[resolve] %s title=%s", msg, (title or "")[:60])
    try:
        from backend.queue_manager import queue_manager

        queue_manager.notify_resolve_fallback(
            service=service or "unknown",
            path=path,
            title=title or "",
            failed_paths=failed_paths or [],
        )
    except Exception as exc:
        logger.debug("[resolve] UI notify skipped: %s", exc)


def sniffer_resolve(service: str) -> Optional[StreamResolve]:
    """Build StreamResolve from in-memory sniffer capture, if ready."""
    try:
        from backend.sniffer_store import sniffer_store
        from backend.sniffer_download import build_sniffer_drm_headers
    except Exception:
        return None

    cap = sniffer_store.get(service)
    if not cap or not cap.is_ready():
        return None
    return StreamResolve(
        mpd_url=cap.manifest_url,
        license_url=cap.license_url or "",
        headers=build_sniffer_drm_headers(cap),
        title=cap.title or "",
        source="sniffer",
        meta={"service": service},
    )


def with_api_refresh_sniffer(
    service: str,
    *,
    api: ResolveFn,
    refresh: Optional[ResolveFn] = None,
    require_license: bool = True,
) -> StreamResolve:
    """
    Standard ladder: api → (optional token refresh) → sniffer capture.

    Use at service download entry points when playback/API is flaky.
    """
    def _tag(fn: ResolveFn, source_hint: str) -> ResolveFn:
        def wrapped():
            r = fn()
            if r is not None and r.is_valid():
                r.source = r.source or source_hint
                meta = dict(r.meta or {})
                meta.setdefault("service", service)
                r.meta = meta
            return r
        return wrapped

    steps: List[tuple[str, ResolveFn]] = [("api", _tag(api, "api"))]
    if refresh is not None:
        steps.append(("refresh", _tag(refresh, "refresh")))
    steps.append(("sniffer", _tag(lambda: sniffer_resolve(service), "sniffer")))
    return resolve_stream_ladder(steps, require_license=require_license)
