"""Browser bridge: Tampermonkey session push + sniffer relay."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

USERSCRIPT_PATH = PROJECT_ROOT / "userscripts" / "videodownload-bridge.user.js"
DEFAULT_BACKEND = "http://127.0.0.1:8000"


def get_backend_url() -> str:
    import os

    return os.environ.get("VIDEODOWNLOAD_BACKEND_URL", DEFAULT_BACKEND).rstrip("/")


def load_userscript() -> str:
    if not USERSCRIPT_PATH.exists():
        raise FileNotFoundError(f"Userscript not found: {USERSCRIPT_PATH}")
    text = USERSCRIPT_PATH.read_text(encoding="utf-8")
    return text.replace("__BACKEND_URL__", get_backend_url())


def import_session_payload(
    *,
    service: Optional[str] = None,
    session_data: Optional[str] = None,
    batch: Optional[Dict[str, Any]] = None,
    source: str = "api",
) -> Dict[str, Any]:
    from backend.session_import import import_session_for_service, try_import_batch

    if batch:
        data = json.dumps(batch, ensure_ascii=False)
        result = try_import_batch(data)
        if result:
            result["source"] = source
            return result
        raise ValueError("Batch JSON ne sadrži prepoznatljive sesije.")

    if not session_data or not session_data.strip():
        raise ValueError("Podaci o sesiji ne smeju biti prazni.")

    data = session_data.strip()
    batch_result = try_import_batch(data)
    if batch_result:
        batch_result["source"] = source
        return batch_result

    if not service:
        raise ValueError("Servis je obavezan za pojedinačni uvoz.")
    result = import_session_for_service(service.strip().lower(), data)
    return {"success": True, "source": source, **result}


def imported_service_names(result: Dict[str, Any]) -> List[str]:
    if result.get("batch") and result.get("imported"):
        return [x.get("service", "") for x in result["imported"] if x.get("service")]
    if result.get("service"):
        return [result["service"]]
    return []
