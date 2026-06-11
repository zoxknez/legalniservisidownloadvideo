"""
Secure credential storage for paid subscription accounts.

Sensitive values (passwords, tokens) → OS keyring (Windows Credential Manager).
Non-sensitive metadata (email, username, market, serial) → config.json with chmod 600.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

KEYRING_ACCOUNT = "videodownloadservisi"

# Fields never written in plain text to config.json
SENSITIVE_FIELDS: Dict[str, List[str]] = {
    "voyo": ["password", "token", "secure_streaming_token"],
    "eon": ["password"],
    "hrti": ["password", "token"],
    "rtsplaneta": ["password", "token", "secure_streaming_token"],
    "hbomax": ["token", "access_token"],
    "skyshowtime": ["token", "user_token"],
}

# Optional per-service native config files to migrate
_NATIVE_CONFIG_PATHS = {
    "voyo": Path.home() / ".voyo" / "config.json",
    "hrti": Path.home() / ".hrti" / "config.json",
    "rtsplaneta": Path.home() / ".rtsplaneta" / "config.json",
    "skyshowtime": Path.home() / ".skyshowtime" / "tokens.json",
}

# Token fields stored in native JSON files (migrated to keyring, cleared from disk)
_NATIVE_TOKEN_FIELDS = ("token", "secure_streaming_token", "access_token")


def _keyring_id(service: str, field: str) -> str:
    return f"{service}/{field}"


def _keyring_available() -> bool:
    try:
        import keyring  # noqa: F401
        return True
    except ImportError:
        return False


def set_secret(service: str, field: str, value: str) -> bool:
    if not value:
        delete_secret(service, field)
        return True
    try:
        import keyring
        keyring.set_password(_keyring_id(service, field), KEYRING_ACCOUNT, value)
        return True
    except Exception as exc:
        logger.error("Keyring write failed for %s.%s: %s", service, field, exc)
        return False


def get_secret(service: str, field: str) -> str:
    try:
        import keyring
        val = keyring.get_password(_keyring_id(service, field), KEYRING_ACCOUNT)
        return val or ""
    except Exception as exc:
        logger.debug("Keyring read failed for %s.%s: %s", service, field, exc)
        return ""


def delete_secret(service: str, field: str) -> None:
    try:
        import keyring
        keyring.delete_password(_keyring_id(service, field), KEYRING_ACCOUNT)
    except Exception:
        pass


def has_secret(service: str, field: str) -> bool:
    return bool(get_secret(service, field))


def split_credentials(service: str, creds: Dict[str, Any]) -> tuple[Dict[str, str], Dict[str, str]]:
    sensitive_keys = set(SENSITIVE_FIELDS.get(service, []))
    public: Dict[str, str] = {}
    secrets: Dict[str, str] = {}
    for key, value in creds.items():
        if value is None:
            continue
        text = str(value).strip() if not isinstance(value, (dict, list)) else ""
        if key in sensitive_keys:
            if text:
                secrets[key] = text
        else:
            if isinstance(value, (dict, list)):
                public[key] = value  # rare; hbomax should not store token dict here
            else:
                public[key] = str(value)
    return public, secrets


def save_service_credentials(service: str, creds: Dict[str, Any], *, config_module) -> None:
    """Persist credentials: secrets in keyring, metadata in config JSON."""
    public, secrets = split_credentials(service, creds)
    for field, value in secrets.items():
        set_secret(service, field, value)
        public[field] = ""  # never keep secrets in JSON

    if service not in config_module.data.get("credentials", {}):
        config_module.data.setdefault("credentials", {})[service] = {}
    config_module.data["credentials"][service].update(public)
    config_module.save()


def get_service_credentials(service: str, config_module) -> Dict[str, str]:
    """Merge public config with keyring secrets."""
    base = dict(config_module.data.get("credentials", {}).get(service, {}))
    for field in SENSITIVE_FIELDS.get(service, []):
        secret = get_secret(service, field)
        if secret:
            base[field] = secret
    return base


def credential_security_status(service: str, config_module) -> Dict[str, Any]:
    creds = config_module.data.get("credentials", {}).get(service, {})
    fields = SENSITIVE_FIELDS.get(service, [])
    return {
        "keyring_available": _keyring_available(),
        "fields": {
            field: {
                "configured": bool(get_secret(service, field) or creds.get(field)),
                "stored_in_keyring": has_secret(service, field),
                "in_config_json": bool(creds.get(field)),
            }
            for field in fields
        },
    }


def migrate_plaintext_config(config_module) -> Dict[str, Any]:
    """
    Move secrets from config.json (and native service configs) into keyring.
    Clears plaintext passwords from disk.
    """
    report: Dict[str, Any] = {"migrated": [], "cleared_json": [], "native": []}

    for service, fields in SENSITIVE_FIELDS.items():
        creds = config_module.data.get("credentials", {}).get(service, {})
        if not isinstance(creds, dict):
            continue
        changed = False
        for field in fields:
            plain = (creds.get(field) or "").strip()
            if plain:
                if set_secret(service, field, plain):
                    creds[field] = ""
                    report["migrated"].append(f"{service}.{field}")
                    changed = True
        if changed:
            config_module.data["credentials"][service] = creds
            report["cleared_json"].append(service)

    # Native per-service config files
    for service, path in _NATIVE_CONFIG_PATHS.items():
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                native = json.load(f)
        except Exception:
            continue
        native_changed = False
        for field in SENSITIVE_FIELDS.get(service, []):
            alt_fields = [field]
            if field == "password":
                alt_fields.append("pass")
            for fkey in alt_fields:
                plain = (native.get(fkey) or "").strip()
                if plain:
                    if set_secret(service, field, plain):
                        native[fkey] = ""
                        native_changed = True
                        report["native"].append(f"{path.name}:{fkey}")
        for tfield in _NATIVE_TOKEN_FIELDS:
            plain = (native.get(tfield) or "").strip()
            if plain:
                if set_secret(service, tfield, plain):
                    native[tfield] = ""
                    native_changed = True
                    report["native"].append(f"{path.name}:{tfield}")

        if native_changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(native, f, indent=2)
            try:
                path.chmod(0o600)
            except OSError:
                pass

    if report["cleared_json"]:
        config_module.save()

    return report


def migrate_legacy_keyring() -> List[str]:
    """Move secrets from old keyring IDs (voyo_password) to service/field format."""
    moved: List[str] = []
    try:
        import keyring
    except ImportError:
        return moved

    for service, fields in SENSITIVE_FIELDS.items():
        for field in fields:
            legacy_id = f"{service}_{field}"
            try:
                val = keyring.get_password(legacy_id, KEYRING_ACCOUNT)
            except Exception:
                val = None
            if not val:
                continue
            if set_secret(service, field, val):
                moved.append(legacy_id)
                try:
                    keyring.delete_password(legacy_id, KEYRING_ACCOUNT)
                except Exception:
                    pass
    return moved


def all_credential_security_status(config_module) -> Dict[str, Any]:
    return {
        service: credential_security_status(service, config_module)
        for service in SENSITIVE_FIELDS
    }


SERVICE_ALIASES = {
    "rts": "rtsplaneta",
    "hbo": "hbomax",
    "max": "hbomax",
    "sky": "skyshowtime",
    "skyott": "skyshowtime",
}

_PUBLIC_METADATA_CLEAR = {
    "voyo": ("email", "variant"),
    "hrti": ("email",),
    "rtsplaneta": ("email", "username"),
    "eon": ("username", "serial", "number"),
    "hbomax": ("market",),
    "skyshowtime": ("territory", "expiry", "token"),
}


def _normalize_service(service: str) -> str:
    key = (service or "").strip().lower()
    return SERVICE_ALIASES.get(key, key)


def clear_service_credentials(service: str, config_module) -> Dict[str, Any]:
    """
    Remove secrets from OS keyring, clear public metadata in config.json,
    and reset native service files / adapter caches where applicable.
    """
    service = _normalize_service(service)
    if service not in SENSITIVE_FIELDS:
        raise ValueError(f"Nepoznat servis: {service}")

    cleared_secrets: List[str] = []
    for field in SENSITIVE_FIELDS.get(service, []):
        if has_secret(service, field):
            cleared_secrets.append(field)
        delete_secret(service, field)

    creds = config_module.data.setdefault("credentials", {}).setdefault(service, {})
    if not isinstance(creds, dict):
        creds = {}
        config_module.data["credentials"][service] = creds
    for key in _PUBLIC_METADATA_CLEAR.get(service, ()):
        creds[key] = ""
    config_module.save()

    native_cleared: List[str] = []
    native_path = _NATIVE_CONFIG_PATHS.get(service)
    if native_path and native_path.exists():
        try:
            with open(native_path, "r", encoding="utf-8") as f:
                native = json.load(f)
        except Exception:
            native = {}
        changed = False
        for field in SENSITIVE_FIELDS.get(service, []):
            for fkey in (field, "pass" if field == "password" else field):
                if native.get(fkey):
                    native[fkey] = ""
                    changed = True
        for tfield in _NATIVE_TOKEN_FIELDS:
            if native.get(tfield):
                native[tfield] = ""
                changed = True
        if service == "hrti":
            for public_key in ("email", "username", "customer_id", "CustomerId"):
                if native.get(public_key):
                    native[public_key] = ""
                    changed = True
        if service == "eon" and native.get("cookies"):
            native["cookies"] = {}
            changed = True
        if changed:
            with open(native_path, "w", encoding="utf-8") as f:
                json.dump(native, f, indent=2)
            try:
                native_path.chmod(0o600)
            except OSError:
                pass
            native_cleared.append(str(native_path))

    if service == "hbomax":
        token_path = Path.home() / ".hbomax" / "token.json"
        if token_path.exists():
            try:
                token_path.unlink()
                native_cleared.append(str(token_path))
            except OSError as exc:
                logger.warning("Could not remove HBO token file: %s", exc)

    if service == "skyshowtime":
        sky_dir = Path.home() / ".skyshowtime"
        for name in ("tokens.json", "cookies.txt"):
            path = sky_dir / name
            if path.exists():
                try:
                    path.unlink()
                    native_cleared.append(str(path))
                except OSError as exc:
                    logger.warning("Could not remove SkyShowtime file %s: %s", path, exc)

    if service == "eon":
        eon_cfg = Path.home() / ".eon" / "config.json"
        if eon_cfg.exists():
            try:
                with open(eon_cfg, "r", encoding="utf-8") as f:
                    eon_native = json.load(f)
            except Exception:
                eon_native = {}
            if eon_native.get("cookies"):
                eon_native["cookies"] = {}
                with open(eon_cfg, "w", encoding="utf-8") as f:
                    json.dump(eon_native, f, indent=2)
                native_cleared.append(str(eon_cfg))

    if service == "voyo":
        try:
            from backend.services import voyo_adapter

            voyo_adapter._VOYO_CACHE.clear()
        except Exception:
            pass

    if service == "eon":
        try:
            from backend.services.eon_adapter import _invalidate_health_cache

            _invalidate_health_cache()
        except Exception:
            pass

    return {
        "service": service,
        "cleared_secrets": cleared_secrets,
        "native_cleared": native_cleared,
        "message": f"Kredencijali za {service} su obrisani.",
    }
