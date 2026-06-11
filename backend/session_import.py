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
    "sky": "skyshowtime",
    "skyott": "skyshowtime",
}


def _write_skyshowtime_cookies_txt(cookie_path: Path, cookies: Dict[str, str]) -> None:
    lines = [
        "# Netscape HTTP Cookie File",
        "# Imported by Video Download Servisi",
        "",
    ]
    for name, value in cookies.items():
        if not value:
            continue
        lines.append(f".skyshowtime.com\tTRUE\t/\tTRUE\t0\t{name}\t{value}")
    cookie_path.write_text("\n".join(lines), encoding="utf-8")


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


def _detect_voyo_variant_from_token(token: str) -> str:
    import base64
    import json
    try:
        parts = token.split('.')
        if len(parts) == 3:
            payload_b64 = parts[1]
            padding = '=' * (4 - len(payload_b64) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
            payload = json.loads(payload_bytes)
            
            # Check siteId
            site_id = payload.get("siteId") or payload.get("site_id")
            if site_id:
                if int(site_id) == 30057:
                    return "hr"
                if int(site_id) == 30005:
                    return "rs"
                    
            # Check iss claim
            iss = payload.get("iss", "")
            if "rtl.hr" in iss or "voyo.hr" in iss:
                return "hr"
            if "rtlrs" in iss or "voyo.rs" in iss:
                return "rs"
    except Exception:
        pass
    return "rs"


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
        
        # Detect variant
        voyo_variant = "rs"
        if data.startswith("{"):
            try:
                js = json.loads(data)
                if isinstance(js, dict) and "variant" in js:
                    voyo_variant = js["variant"]
            except Exception:
                pass
        
        if voyo_variant == "rs":
            voyo_variant = _detect_voyo_variant_from_token(token)
            
        from backend.config import config
        config.update_credentials("voyo", {"variant": voyo_variant})
        
        try:
            from backend.core.services.voyo.auth import VoyoConfig as _VoyoConfig
            vc = _VoyoConfig()
            email, _, _ = vc.get_credentials()
            vc.set_credentials(email, "", variant=voyo_variant)
        except Exception:
            pass

        try:
            from backend.services.voyo_adapter import _VOYO_CACHE
            import time

            _VOYO_CACHE["token"] = token
            _VOYO_CACHE["variant"] = voyo_variant
            _VOYO_CACHE["last_check"] = time.time()
            _VOYO_CACHE["authenticated"] = True
        except Exception:
            pass
        return {"service": service, "message": f"Voyo {voyo_variant.upper()} token uvezen (OS keyring)."}

    if service == "hrti":
        token = _extract_token_string("hrti", data)
        set_secret("hrti", "token", token)
        return {"service": service, "message": "HRTi token uvezen (OS keyring)."}

    if service == "rtsplaneta":
        token = _extract_token_string("rtsplaneta", data)
        set_secret("rtsplaneta", "token", token)
        set_secret("rtsplaneta", "secure_streaming_token", token)
        return {"service": service, "message": "RTS Planeta token uvezen (OS keyring)."}

    if service == "eon":
        if not data.startswith("{"):
            raise ValueError("EON uvoz: nalepite JSON (kolačići ili config iz ~/.eon/config.json).")
        try:
            js = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError("EON uvoz: neispravan JSON.") from exc
        eon_dir = Path.home() / ".eon"
        eon_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = eon_dir / "config.json"
        existing: Dict[str, Any] = {}
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = {}
        if isinstance(js.get("cookies"), dict):
            existing["cookies"] = js["cookies"]
        elif "cookies" in js:
            existing["cookies"] = js.get("cookies") or {}
        elif isinstance(js, dict) and js and all(isinstance(v, str) for v in js.values()):
            existing["cookies"] = js
        else:
            for key, val in js.items():
                if key != "cookies":
                    existing[key] = val
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
        try:
            cfg_path.chmod(0o600)
        except OSError:
            pass
        try:
            from backend.services.eon_adapter import _invalidate_health_cache

            _invalidate_health_cache()
        except Exception:
            pass
        return {"service": service, "message": "EON kolačići uvezeni u ~/.eon/config.json."}

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

    if service == "skyshowtime":
        sky_dir = Path.home() / ".skyshowtime"
        sky_dir.mkdir(parents=True, exist_ok=True)
        cookie_path = sky_dir / "cookies.txt"

        if data.startswith("#") or ("\t" in data and "skyshowtime" in data.lower()):
            cookie_path.write_text(data, encoding="utf-8")
        elif data.startswith("{"):
            try:
                js = json.loads(data)
            except json.JSONDecodeError as exc:
                raise ValueError("SkyShowtime uvoz: neispravan JSON.") from exc
            if isinstance(js.get("cookies"), dict):
                _write_skyshowtime_cookies_txt(cookie_path, js["cookies"])
            elif isinstance(js, dict) and js and all(isinstance(v, str) for v in js.values()):
                _write_skyshowtime_cookies_txt(cookie_path, js)
            else:
                raise ValueError(
                    "SkyShowtime uvoz: očekivan Netscape cookies.txt ili JSON sa poljem cookies."
                )
        else:
            raise ValueError(
                "SkyShowtime uvoz: nalepite Netscape cookies.txt ili JSON sa kolačićima."
            )

        try:
            cookie_path.chmod(0o600)
        except OSError:
            pass

        try:
            from backend.core.services.skyshowtime.skyshowtime_auth import SkyShowtimeAuth

            auth = SkyShowtimeAuth()
            auth.login_with_cookies(str(cookie_path))
            return {"service": service, "message": "SkyShowtime kolačići uvezeni i token osvežen."}
        except Exception as exc:
            logger.warning("SkyShowtime token refresh after import failed: %s", exc)
            return {
                "service": service,
                "message": f"SkyShowtime kolačići sačuvani u {cookie_path} (token nije osvežen: {exc})",
            }

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

    batch_keys = {
        "voyo", "hrti", "rtsplaneta", "rts", "hbomax", "hbo", "max", "eon",
        "skyshowtime", "sky", "skyott",
    }
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
        ("eon", "eon"),
        ("skyshowtime", "skyshowtime"),
        ("sky", "skyshowtime"),
        ("skyott", "skyshowtime"),
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
