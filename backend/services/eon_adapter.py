import importlib.util
import logging
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List

from backend.config import CONFIG_DIR, PROJECT_ROOT, config
from backend.core.services.eon import EONEngine
from backend.jobs.inprocess import build_job

logger = logging.getLogger(__name__)
CWD = PROJECT_ROOT

_EON_CATALOG_NAMES = (
    "eon_channels.json",
    "eon_series.json",
    "eon_vod.json",
    "eon_epg.json",
    "eon_api.json",
)


def _migrate_eon_catalog_files() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    for name in _EON_CATALOG_NAMES:
        src = CWD / name
        dst = CONFIG_DIR / name
        if src.exists() and not dst.exists():
            try:
                shutil.copy2(src, dst)
                logger.info("EON katalog migriran: %s -> %s", name, dst)
            except OSError as exc:
                logger.warning("EON migracija %s nije uspela: %s", name, exc)


_migrate_eon_catalog_files()

_eon_health_cache: Dict[str, Any] = {}
_eon_health_cache_ts: float = 0.0
_EON_HEALTH_TTL = 60.0


def _invalidate_health_cache() -> None:
    global _eon_health_cache, _eon_health_cache_ts
    _eon_health_cache = {}
    _eon_health_cache_ts = 0.0


class EonAdapter:
    ENGINE_MODULE = "backend.core.services.eon.eon_downloader"
    SUPPORTED_MODES = {"vod", "series", "live"}
    REQUIRED_PACKAGES = {
        "requests": "requests",
        "yt_dlp": "yt-dlp",
    }
    OPTIONAL_PACKAGES = {
        "Crypto": "pycryptodome",
        "xmltodict": "xmltodict",
        "pywidevine": "pywidevine",
    }
    CHANNEL_CATALOG = CONFIG_DIR / "eon_channels.json"
    SERIES_CATALOG = CONFIG_DIR / "eon_series.json"
    VOD_CATALOG = CONFIG_DIR / "eon_vod.json"
    EPG_CATALOG = CONFIG_DIR / "eon_epg.json"
    API_CONFIG = CONFIG_DIR / "eon_api.json"
    CHANNEL_CATALOG_EXAMPLE = CWD / "eon_channels.example.json"
    SERIES_CATALOG_EXAMPLE = CWD / "eon_series.example.json"
    VOD_CATALOG_EXAMPLE = CWD / "eon_vod.example.json"
    EPG_CATALOG_EXAMPLE = CWD / "eon_epg.example.json"
    API_CONFIG_EXAMPLE = CWD / "eon_api.example.json"

    @classmethod
    def _engine_importable(cls) -> bool:
        return importlib.util.find_spec(cls.ENGINE_MODULE) is not None

    @classmethod
    def _package_status(cls) -> Dict[str, Dict[str, Any]]:
        status = {}
        for import_name, package_name in {**cls.REQUIRED_PACKAGES, **cls.OPTIONAL_PACKAGES}.items():
            found = importlib.util.find_spec(import_name) is not None
            status[package_name] = {"found": found, "import": import_name}
        return status

    @classmethod
    def _missing_environment(cls) -> List[str]:
        missing = []
        if not cls._engine_importable():
            missing.append(cls.ENGINE_MODULE)
        package_status = cls._package_status()
        for _import_name, package_name in cls.REQUIRED_PACKAGES.items():
            if not package_status.get(package_name, {}).get("found"):
                missing.append(package_name)
        binaries = config.check_binaries_status()
        if not binaries.get("ffmpeg", {}).get("found"):
            missing.append("ffmpeg")
        return missing

    @classmethod
    def _optional_environment(cls) -> List[str]:
        optional_missing = []
        package_status = cls._package_status()
        for _import_name, package_name in cls.OPTIONAL_PACKAGES.items():
            if not package_status.get(package_name, {}).get("found"):
                optional_missing.append(package_name)
        binaries = config.check_binaries_status()
        for name in ("mkvmerge", "mp4decrypt", "aria2c", "device_wvd"):
            if not binaries.get(name, {}).get("found"):
                optional_missing.append(name)
        return optional_missing

    @classmethod
    def _engine_status(cls) -> Dict[str, Any]:
        global _eon_health_cache, _eon_health_cache_ts
        now = time.monotonic()
        if _eon_health_cache and (now - _eon_health_cache_ts) < _EON_HEALTH_TTL:
            return _eon_health_cache

        if not cls._engine_importable():
            result = {"available": False, "download_supported": False, "message": "EON engine module is missing."}
        else:
            try:
                payload = EONEngine.health()
                result = {
                    "available": True,
                    "download_supported": bool(payload.get("download_supported")),
                    "message": payload.get("message", ""),
                    "capabilities": payload.get("capabilities", {}),
                    "api": payload.get("api", {}),
                    "catalog": payload.get("catalog", {}),
                    "device": payload.get("device", {}),
                    "token": payload.get("token", {}),
                }
            except Exception as exc:
                result = {
                    "available": True,
                    "download_supported": False,
                    "message": cls._redact_text(str(exc)),
                }

        _eon_health_cache = result
        _eon_health_cache_ts = now
        return result

    @classmethod
    def get_health(cls) -> Dict[str, Any]:
        creds = config.get_credentials("eon")
        username = creds.get("username", "").strip()
        serial = creds.get("serial", "").strip()
        number = creds.get("number", "").strip()
        authenticated = bool(username and serial and number)
        missing = cls._missing_environment()
        optional_missing = cls._optional_environment()
        engine_installed = cls._engine_importable()
        engine_status = cls._engine_status()
        engine_download_supported = bool(engine_status.get("download_supported"))

        if not engine_installed:
            error = "EON downloader engine is not installed."
        elif not engine_download_supported:
            error = engine_status.get("message") or "EON engine does not support downloads yet."
        elif not authenticated:
            error = "EON account/device is not configured."
        elif missing:
            error = "EON environment is missing required dependencies."
        else:
            error = ""

        return {
            "authenticated": authenticated,
            "ready": engine_installed and engine_download_supported and authenticated and not missing,
            "engine_installed": engine_installed,
            "engine_download_supported": engine_download_supported,
            "engine_status": engine_status,
            "dependency_ready": not any(
                not cls._package_status().get(p, {}).get("found")
                for p in cls.REQUIRED_PACKAGES.values()
            ),
            "username": username,
            "serial": serial,
            "number": number,
            "engine_module": cls.ENGINE_MODULE,
            "packages": cls._package_status(),
            "missing": missing,
            "optional_missing": optional_missing,
            "error": error,
        }

    @classmethod
    def get_auth_status(cls) -> Dict[str, Any]:
        return cls.get_health()

    @classmethod
    def ensure_catalog_templates(cls) -> Dict[str, Any]:
        created = []
        existing = []
        pairs = [
            (cls.CHANNEL_CATALOG_EXAMPLE, cls.CHANNEL_CATALOG),
            (cls.SERIES_CATALOG_EXAMPLE, cls.SERIES_CATALOG),
            (cls.VOD_CATALOG_EXAMPLE, cls.VOD_CATALOG),
            (cls.EPG_CATALOG_EXAMPLE, cls.EPG_CATALOG),
            (cls.API_CONFIG_EXAMPLE, cls.API_CONFIG),
        ]
        for source, target in pairs:
            if target.exists():
                existing.append(str(target))
                continue
            if source.exists():
                shutil.copyfile(source, target)
            else:
                target.write_text("{}\n", encoding="utf-8")
            created.append(str(target))
        return {
            "success": True,
            "created": created,
            "existing": existing,
            "channels_path": str(cls.CHANNEL_CATALOG),
            "series_path": str(cls.SERIES_CATALOG),
            "vod_path": str(cls.VOD_CATALOG),
            "epg_path": str(cls.EPG_CATALOG),
            "api_config_path": str(cls.API_CONFIG),
        }

    @classmethod
    def _require_engine(cls) -> None:
        if not cls._engine_importable():
            raise FileNotFoundError(f"EON engine module '{cls.ENGINE_MODULE}' is not importable.")

    @classmethod
    def _require_ready(cls) -> None:
        health = cls.get_health()
        if not health["engine_installed"]:
            raise FileNotFoundError(f"EON engine module '{cls.ENGINE_MODULE}' is not available.")
        if not health.get("engine_download_supported"):
            raise RuntimeError(health.get("error") or "EON engine does not support downloads yet.")
        if not health["authenticated"]:
            raise RuntimeError("EON account/device is not configured.")
        if health["missing"]:
            raise RuntimeError("EON environment is incomplete. Missing: " + ", ".join(health["missing"]))

    @classmethod
    def _require_engine_supported(cls) -> None:
        health = cls.get_health()
        if not health["engine_installed"]:
            raise FileNotFoundError(f"EON engine module '{cls.ENGINE_MODULE}' is not available.")
        if not health.get("engine_download_supported"):
            raise RuntimeError(health.get("error") or "EON engine does not support downloads yet.")

    @classmethod
    def _redact_text(cls, text: str) -> str:
        if not text:
            return ""
        creds = config.get_credentials("eon")
        password = creds.get("password", "")
        if password:
            text = text.replace(password, "***")
        return re.sub(r"(?i)(--password|-p)\s+\S+", r"\1 ***", text)

    @classmethod
    def save_device(cls, username: str, password: str, serial: str, number: str) -> Dict[str, Any]:
        username = username.strip()
        serial = serial.strip()
        number = number.strip()
        if not username or not password or not serial or not number:
            return {"success": False, "error": "Username, password, serial and number are required."}

        config.update_credentials(
            "eon",
            {"username": username, "password": password, "serial": serial, "number": number},
        )

        try:
            cls._require_engine()
            EONEngine.save_device(username, serial, number)
            validated = True
            warning = ""
            if password:
                try:
                    res = EONEngine.api_login(username, password, serial, number)
                    if not res.get("tokens_saved"):
                        validated = False
                        warning = "Device saved, but API login did not persist tokens."
                except Exception as exc:
                    validated = False
                    warning = cls._redact_text(str(exc))
            _invalidate_health_cache()
            return {
                "success": True,
                "validated": validated,
                "warning": warning or None,
                "status": cls.get_health(),
            }
        except Exception as exc:
            _invalidate_health_cache()
            return {
                "success": True,
                "validated": False,
                "warning": cls._redact_text(str(exc)),
                "status": cls.get_health(),
            }

    @classmethod
    def list_channels(cls) -> List[str]:
        cls._require_engine_supported()
        channels = EONEngine.list_channels()
        return [
            str(item.get("name") or item.get("title") or item.get("channel") or item)
            for item in channels
            if item
        ]

    @classmethod
    def list_episodes(cls, series_id: str) -> List[str]:
        series_id = series_id.strip()
        if not series_id:
            raise ValueError("Series ID is required.")
        cls._require_ready()
        episodes = EONEngine.list_episodes(series_id)
        return [
            str(item.get("title") or item.get("name") or item.get("id") or item)
            for item in episodes
            if item
        ]

    @classmethod
    def api_status(cls) -> Dict[str, Any]:
        cls._require_engine_supported()
        return EONEngine.api_status()

    @classmethod
    def api_login(cls, username: str, password: str, serial: str, number: str) -> Dict[str, Any]:
        username = username.strip()
        serial = serial.strip()
        number = number.strip()
        if not username or not password or not serial or not number:
            raise ValueError("Username, password, serial and number are required.")
        cls._require_engine_supported()
        result = EONEngine.api_login(username, password, serial, number)
        _invalidate_health_cache()
        return result

    @classmethod
    def refresh_api_token(cls) -> Dict[str, Any]:
        cls._require_engine_supported()
        result = EONEngine.refresh_token()
        _invalidate_health_cache()
        return result

    @classmethod
    def search_vod(cls, query: str) -> List[Dict[str, Any]]:
        query = query.strip()
        if not query:
            return []
        cls._require_engine_supported()
        return EONEngine.search(query)

    @classmethod
    def get_epg(cls, channel: str) -> List[Dict[str, Any]]:
        channel = channel.strip()
        if not channel:
            return []
        cls._require_engine_supported()
        return EONEngine.epg(channel)

    @classmethod
    def get_vod_info(cls, target: str) -> Dict[str, Any]:
        target = target.strip()
        if not target:
            raise ValueError("VOD target is required.")
        cls._require_engine_supported()
        return EONEngine.vod_info(target)

    @staticmethod
    def _normalize_vod_target(target: str) -> str:
        target = target.strip()
        match = re.search(r"/(?:ondemand|series)/detail/([^/?#]+)", target)
        if match:
            return match.group(1)
        return target

    @classmethod
    def make_download_cmd(
        cls,
        mode: str,
        target: str,
        duration: int = 60,
        episodes: str = "",
        play: bool = False,
        player_path: str = "",
    ) -> List[str]:
        mode = mode.strip().lower()
        target = target.strip()
        episodes = episodes.strip()

        if mode not in cls.SUPPORTED_MODES:
            raise ValueError(f"Unsupported EON mode: {mode}")
        if not target:
            raise ValueError("EON target is required.")
        if duration < 0:
            raise ValueError("Duration cannot be negative.")
        if episodes and not re.fullmatch(r"[0-9,\-\s]+", episodes):
            raise ValueError("Episode range may contain only numbers, commas, spaces and hyphens.")

        cls._require_ready()

        params: Dict[str, Any] = {
            "target": cls._normalize_vod_target(target) if mode == "vod" else target,
            "output_dir": config.get_output_dir(),
        }
        if episodes:
            params["episodes"] = episodes
        if mode == "live":
            params["duration"] = duration
            params["play"] = play
            if player_path.strip():
                params["player_path"] = player_path.strip()
        return build_job("eon", mode, params)

    @classmethod
    def resolve_stream(cls, target: str, kind: str = "live") -> Dict[str, Any]:
        cls._require_engine_supported()
        return EONEngine.resolve_stream(target, kind)
