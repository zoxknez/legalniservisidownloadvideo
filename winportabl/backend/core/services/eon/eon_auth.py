import json
import time
from pathlib import Path
from string import Formatter
from typing import Any, Dict, Iterable, Mapping, Optional
from urllib.parse import urljoin

import requests


APP_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = Path.home() / ".videodownload"
DEVICE_FILE = CONFIG_DIR / "eon_device.json"
TOKEN_FILE = CONFIG_DIR / "eon_tokens.json"
FALLBACK_DEVICE_FILE = APP_ROOT / ".eon_device.json"
FALLBACK_TOKEN_FILE = APP_ROOT / ".eon_tokens.json"
API_CONFIG_FILES = [APP_ROOT / "eon_api.json", CONFIG_DIR / "eon_api.json"]

DEFAULT_API_CONFIG = {
    "base_url": "",
    "headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    },
    "auth_header": "Authorization",
    "auth_scheme": "Bearer",
    "endpoints": {
        "login": {"method": "POST", "path": "", "json": {}},
        "refresh": {"method": "POST", "path": "", "json": {}},
        "channels": {"method": "GET", "path": ""},
        "epg": {"method": "GET", "path": ""},
        "search": {"method": "GET", "path": ""},
        "vod_detail": {"method": "GET", "path": ""},
        "series": {"method": "GET", "path": ""},
        "resolve": {"method": "GET", "path": ""},
    },
}


class EonAuthError(RuntimeError):
    pass


class SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _clean(value: str) -> str:
    return (value or "").strip()


def _write_json(primary: Path, fallback: Path, data: Dict[str, Any]) -> Path:
    target = primary
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError:
        target = fallback
        with target.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return target


def _read_json(paths: Iterable[Path]) -> Dict[str, Any]:
    for path in paths:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data["_path"] = str(path)
                return data
        except (OSError, json.JSONDecodeError):
            continue
    return {}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = json.loads(json.dumps(base))
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _render(value: Any, context: Mapping[str, Any]) -> Any:
    ctx = SafeFormatDict({k: "" if v is None else v for k, v in context.items()})
    if isinstance(value, str):
        return Formatter().vformat(value, (), ctx)
    if isinstance(value, list):
        return [_render(item, context) for item in value]
    if isinstance(value, dict):
        return {key: _render(item, context) for key, item in value.items()}
    return value


def validate_device_fields(username: str, serial: str, number: str) -> None:
    missing = []
    if not _clean(username):
        missing.append("username")
    if not _clean(serial):
        missing.append("device serial")
    if not _clean(number):
        missing.append("device number")
    if missing:
        raise ValueError("Missing EON device fields: " + ", ".join(missing))


def save_device_profile(username: str, serial: str, number: str) -> Dict[str, str]:
    validate_device_fields(username, serial, number)
    data = {
        "username": _clean(username),
        "serial": _clean(serial),
        "number": _clean(number),
    }
    _write_json(DEVICE_FILE, FALLBACK_DEVICE_FILE, data)
    return data


def load_device_profile() -> Dict[str, Any]:
    return _read_json([DEVICE_FILE, FALLBACK_DEVICE_FILE])


def device_profile_status() -> Dict[str, Any]:
    data = load_device_profile()
    configured = bool(data.get("username") and data.get("serial") and data.get("number"))
    return {
        "configured": configured,
        "username": data.get("username", ""),
        "serial": data.get("serial", ""),
        "number": data.get("number", ""),
        "path": data.get("_path", str(DEVICE_FILE)),
    }


def save_token_profile(tokens: Dict[str, Any]) -> Dict[str, Any]:
    existing = load_token_profile()
    existing.update({k: v for k, v in tokens.items() if v not in ("", None)})
    if "expires_in" in existing and "expires_at" not in tokens:
        try:
            existing["expires_at"] = int(time.time()) + int(existing["expires_in"])
        except (TypeError, ValueError):
            pass
    existing["saved_at"] = int(time.time())
    _write_json(TOKEN_FILE, FALLBACK_TOKEN_FILE, existing)
    return existing


def load_token_profile() -> Dict[str, Any]:
    return _read_json([TOKEN_FILE, FALLBACK_TOKEN_FILE])


def token_status() -> Dict[str, Any]:
    data = load_token_profile()
    expires_at = data.get("expires_at")
    expired = bool(expires_at and int(expires_at) <= int(time.time()))
    return {
        "configured": bool(data.get("access_token")),
        "has_refresh_token": bool(data.get("refresh_token")),
        "expires_at": expires_at,
        "expired": expired,
        "path": data.get("_path", str(TOKEN_FILE)),
    }


def load_api_config() -> Dict[str, Any]:
    raw = _read_json(API_CONFIG_FILES)
    path = raw.pop("_path", "")
    cfg = _deep_merge(DEFAULT_API_CONFIG, raw)
    cfg["_path"] = path
    return cfg


def api_status() -> Dict[str, Any]:
    cfg = load_api_config()
    endpoints = cfg.get("endpoints", {})
    configured = {
        name: bool((endpoint or {}).get("path") if isinstance(endpoint, dict) else endpoint)
        for name, endpoint in endpoints.items()
    }
    return {
        "configured": bool(cfg.get("_path")),
        "path": cfg.get("_path", ""),
        "base_url": cfg.get("base_url", ""),
        "endpoints": configured,
        "device": device_profile_status(),
        "token": token_status(),
    }


def _find_token(payload: Any, names: Iterable[str]) -> Optional[Any]:
    wanted = {name.lower() for name in names}
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() in wanted and value:
                return value
        for value in payload.values():
            found = _find_token(value, names)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_token(item, names)
            if found:
                return found
    return None


def extract_tokens(payload: Any) -> Dict[str, Any]:
    tokens = {
        "access_token": _find_token(payload, ["access_token", "accessToken", "token", "jwt", "bearer"]),
        "refresh_token": _find_token(payload, ["refresh_token", "refreshToken"]),
        "expires_in": _find_token(payload, ["expires_in", "expiresIn"]),
        "expires_at": _find_token(payload, ["expires_at", "expiresAt"]),
    }
    return {k: v for k, v in tokens.items() if v not in ("", None)}


def build_context(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    device = load_device_profile()
    token = load_token_profile()
    context = {
        "username": device.get("username", ""),
        "device_serial": device.get("serial", ""),
        "device_number": device.get("number", ""),
        "access_token": token.get("access_token", ""),
        "refresh_token": token.get("refresh_token", ""),
    }
    if extra:
        context.update(extra)
    return context


def api_request(endpoint_name: str, extra: Optional[Dict[str, Any]] = None, require_auth: bool = False) -> Any:
    cfg = load_api_config()
    endpoint = cfg.get("endpoints", {}).get(endpoint_name)
    if not endpoint:
        raise EonAuthError(f"EON API endpoint is not configured: {endpoint_name}")
    if isinstance(endpoint, str):
        endpoint = {"method": "GET", "path": endpoint}

    path = endpoint.get("path", "")
    if not path:
        raise EonAuthError(f"EON API endpoint has no path: {endpoint_name}")

    context = build_context(extra)
    url = _render(path, context)
    if not url.lower().startswith(("http://", "https://")):
        url = urljoin(str(cfg.get("base_url", "")).rstrip("/") + "/", str(url).lstrip("/"))

    headers = {}
    headers.update(cfg.get("headers", {}))
    headers.update(endpoint.get("headers", {}))
    headers = _render(headers, context)
    if require_auth:
        access_token = context.get("access_token")
        if not access_token:
            raise EonAuthError("EON API access token is missing. Configure login/refresh first.")
        header_name = cfg.get("auth_header", "Authorization")
        scheme = cfg.get("auth_scheme", "Bearer")
        headers[header_name] = f"{scheme} {access_token}".strip()

    method = str(endpoint.get("method", "GET")).upper()
    params = _render(endpoint.get("params", {}), context)
    json_body = _render(endpoint.get("json", None), context)
    data_body = _render(endpoint.get("data", None), context)
    timeout = int(endpoint.get("timeout", cfg.get("timeout", 25)))

    # Prefer shared browser session (TLS fingerprint) over bare requests.
    try:
        from backend.services.http_client import create_browser_session

        _sess = getattr(api_request, "_session", None)
        if _sess is None:
            _sess = create_browser_session()
            setattr(api_request, "_session", _sess)
        response = _sess.request(
            method,
            url,
            headers=headers,
            params=params or None,
            json=json_body,
            data=data_body,
            timeout=timeout,
        )
    except Exception:
        response = requests.request(
            method,
            url,
            headers=headers,
            params=params or None,
            json=json_body,
            data=data_body,
            timeout=timeout,
        )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "json" in content_type:
        return response.json()
    try:
        return response.json()
    except ValueError:
        return response.text


import threading

_token_lock = threading.Lock()


def login_api(username: str, password: str, serial: str, number: str) -> Dict[str, Any]:
    with _token_lock:
        save_device_profile(username, serial, number)
        payload = api_request(
            "login",
            {
                "username": username,
                "password": password,
                "device_serial": serial,
                "device_number": number,
            },
            require_auth=False,
        )
        tokens = extract_tokens(payload)
        if tokens:
            save_token_profile(tokens)
        return {"payload": payload, "tokens_saved": bool(tokens), "token_status": token_status()}


def refresh_api_token() -> Dict[str, Any]:
    with _token_lock:
        payload = api_request("refresh", {}, require_auth=False)
        tokens = extract_tokens(payload)
        if tokens:
            save_token_profile(tokens)
        return {"payload": payload, "tokens_saved": bool(tokens), "token_status": token_status()}
