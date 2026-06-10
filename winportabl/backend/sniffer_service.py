"""Central sniffer event handling: store pairing, WS broadcast, optional auto-download."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.config import config
from backend.sniffer_download import queue_sniffer_download
from backend.sniffer_store import SnifferCapture, sniffer_store

logger = logging.getLogger(__name__)


def sniffer_auto_download_enabled() -> bool:
    return bool(config.data.get("sniffer", {}).get("auto_download", True))


async def process_sniffer_event(
    queue_manager,
    *,
    service: str,
    sniffer_type: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    title: str = "",
) -> Dict[str, Any]:
    capture = sniffer_store.update(service, sniffer_type, url, headers, title)

    await queue_manager.broadcast_sniffer(
        service=capture.service,
        sniffer_type=sniffer_type,
        url=url,
        headers=headers,
        title=title or capture.title,
    )

    result: Dict[str, Any] = {
        "success": True,
        "capture": capture.to_public_dict(),
        "ready": capture.is_ready(),
    }

    if not capture.is_ready():
        return result

    await queue_manager.broadcast_sniffer_ready(
        service=capture.service,
        capture=capture.to_public_dict(),
    )

    if sniffer_auto_download_enabled() and sniffer_store.should_auto_queue(capture):
        try:
            queued = await queue_sniffer_download(queue_manager, capture)
            sniffer_store.mark_queued(capture.service, queued["task_id"])
            result["auto_download"] = queued
            await queue_manager.broadcast_sniffer_download_queued(
                service=capture.service,
                task_id=queued["task_id"],
                title=queued["title"],
                auto=True,
            )
        except Exception as exc:
            logger.warning("Sniffer auto-download failed for %s: %s", capture.service, exc)
            result["auto_download_error"] = str(exc)

    return result
