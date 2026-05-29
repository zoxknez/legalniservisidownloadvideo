"""
Session / token import helpers (browser bookmarklet, console paste, batch JSON).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SERVICE_ALIASES = {
    "rts": "rtsplaneta",
    "hbo": "hbomax",
    "max": "hbomax",
}


def _extract_token_string(service: str, data: str) -> str:
    text = (data or "").strip()
    if not text.startswith("{"):
        return text
    try:
        js = json.loads(text)
    except json.JSONDecodeError:
        return text

    if service == "hbomax":
        return json.dumps(js, ensure_ascii=False)

    for key in ("token", "secure_streaming_token", "access_token", "authToken"):
        val = js.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    if service == "voyo":
        for key in ("secure_streaming_token", "authToken"):
            val = js.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

    return text


def import_session_for_service(service: str, session_data: str) -> Dict[str, Any]:
    """Import token/session for one service. Raises ValueError on bad input."""
    from backend.credentials_store import set_secret

    service = SERVICE_ALIASES.get(service.strip().lower(), service.strip().lower())
    data = (session_data or "").strip()
    if not data:
        raise ValueError("Podaci o sesiji ne smeju biti prazni.")

    if service == "voyo":
        token = _extract_token_string("voyo", data)
        set_secret("voyo", "token", token)
        try:
            from backend.services.voyo_adapter import _VOYO_CACHE
            import time

            _VOYO_CACHE["token"] = token
            _VOYO_CACHE["last_check"] = time.time()
        except Exception:
            pass
        return {"service": service, "message": "Voyo token uvezen (OS keyring)."}

    if service == "hrti":
        token = _extract_token_string("hrti", data)
        set_secret("hrti", "token", token)
        return {"service": service, "message": "HRTi token uvezen (OS keyring)."}

    if service == "rtsplaneta":
        token = _extract_token_string("rtsplaneta", data)
        set_secret("rtsplaneta", "token", token)
        set_secret("rtsplaneta", "secure_streaming_token", token)
        return {"service": service, "message": "RTS Planeta token uvezen (OS keyring)."}

    if service == "hbomax":
        token_path = Path.home() / ".hbomax" / "token.json"
        token_path.parent.mkdir(parents=True, exist_ok=True)
        if data.startswith("{"):
            try:
                js = json.loads(data)
                if "access_token" not in js and "token" in js:
                    js["access_token"] = js["token"]
                if "access_token" in js and isinstance(js["access_token"], str):
                    js["access_token"] = js["access_token"].replace("Bearer ", "").strip()
                with open(token_path, "w", encoding="utf-8") as f:
                    json.dump(js, f, indent=2)
            except json.JSONDecodeError:
                clean = data.replace("Bearer ", "").strip()
                with open(token_path, "w", encoding="utf-8") as f:
                    json.dump({"access_token": clean}, f, indent=2)
        else:
            clean = data.replace("Bearer ", "").strip()
            with open(token_path, "w", encoding="utf-8") as f:
                json.dump({"access_token": clean}, f, indent=2)
        try:
            token_path.chmod(0o600)
        except OSError:
            pass
        access = ""
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                access = json.load(f).get("access_token", "")
        except Exception:
            pass
        if access:
            set_secret("hbomax", "access_token", access)
        return {"service": service, "message": "HBO Max token uvezen."}

    raise ValueError(f"Uvoz sesije nije podržan za servis: {service}")


def try_import_batch(session_data: str) -> Optional[Dict[str, Any]]:
    """
    Detect bookmarklet JSON: {voyo, hrti, hbomax, ...} and import all present keys.
    Returns None if payload is not a batch object.
    """
    text = (session_data or "").strip()
    if not text.startswith("{"):
        return None
    try:
        blob = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(blob, dict):
        return None

    batch_keys = {"voyo", "hrti", "rtsplaneta", "rts", "hbomax", "hbo", "max"}
    if not batch_keys.intersection(k.lower() for k in blob.keys()):
        return None

    imported: List[Dict[str, str]] = []
    errors: List[str] = []

    mapping = [
        ("voyo", "voyo"),
        ("hrti", "hrti"),
        ("rtsplaneta", "rtsplaneta"),
        ("rts", "rtsplaneta"),
        ("hbomax", "hbomax"),
        ("hbo", "hbomax"),
        ("max", "hbomax"),
    ]
    done: set[str] = set()
    for src_key, svc in mapping:
        if svc in done:
            continue
        val = blob.get(src_key)
        if val is None:
            for k, v in blob.items():
                if k.lower() == src_key and v:
                    val = v
                    break
        if not val:
            continue
        payload = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
        if len(payload) < 8 and svc != "hbomax":
            continue
        try:
            res = import_session_for_service(svc, payload)
            imported.append({"service": svc, "message": res["message"]})
            done.add(svc)
        except Exception as exc:
            errors.append(f"{svc}: {exc}")

    if not imported:
        return None

    return {
        "success": True,
        "batch": True,
        "imported": imported,
        "errors": errors,
        "message": f"Uvezeno {len(imported)} servisa"
        + (f" ({len(errors)} grešaka)" if errors else ""),
    }
