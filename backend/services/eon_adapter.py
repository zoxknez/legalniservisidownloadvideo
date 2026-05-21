import importlib.util
import json
import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from backend.config import config

logger = logging.getLogger(__name__)
CWD = Path(__file__).parent.parent.parent.resolve()


class EonAdapter:
    SCRIPT_NAME = "eon_downloader.py"
    SCRIPT_FILES = ("eon_downloader.py", "eon_auth.py")
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
    SENSITIVE_FLAGS = {"-p", "--password"}
    CHANNEL_CATALOG = CWD / "eon_channels.json"
    SERIES_CATALOG = CWD / "eon_series.json"
    VOD_CATALOG = CWD / "eon_vod.json"
    EPG_CATALOG = CWD / "eon_epg.json"
    API_CONFIG = CWD / "eon_api.json"
    CHANNEL_CATALOG_EXAMPLE = CWD / "eon_channels.example.json"
    SERIES_CATALOG_EXAMPLE = CWD / "eon_series.example.json"
    VOD_CATALOG_EXAMPLE = CWD / "eon_vod.example.json"
    EPG_CATALOG_EXAMPLE = CWD / "eon_epg.example.json"
    API_CONFIG_EXAMPLE = CWD / "eon_api.example.json"

    @classmethod
    def script_path(cls) -> Path:
        return CWD / cls.SCRIPT_NAME

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
        for script_file in cls.SCRIPT_FILES:
            if not (CWD / script_file).exists():
                missing.append(script_file)

        package_status = cls._package_status()
        for _import_name, package_name in cls.REQUIRED_PACKAGES.items():
            info = package_status.get(package_name, {})
            if not info.get("found"):
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
        if not all((CWD / script_file).exists() for script_file in cls.SCRIPT_FILES):
            return {"available": False, "download_supported": False, "message": "EON engine files are missing."}

        try:
            res = subprocess.run(
                [sys.executable, str(cls.script_path()), "--health"],
                cwd=str(CWD),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if res.returncode != 0:
                return {
                    "available": True,
                    "download_supported": False,
                    "message": cls._redact_text(res.stderr or res.stdout or "EON engine health check failed."),
                }
            payload = json.loads(res.stdout or "{}")
            return {
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
            return {
                "available": True,
                "download_supported": False,
                "message": cls._redact_text(str(exc)),
            }

    @classmethod
    def get_health(cls) -> Dict[str, Any]:
        creds = config.get_credentials("eon")
        username = creds.get("username", "").strip()
        serial = creds.get("serial", "").strip()
        number = creds.get("number", "").strip()
        authenticated = bool(username and serial and number)
        missing = cls._missing_environment()
        optional_missing = cls._optional_environment()
        engine_installed = all((CWD / script_file).exists() for script_file in cls.SCRIPT_FILES)
        engine_status = cls._engine_status()
        engine_download_supported = bool(engine_status.get("download_supported"))
        package_status = cls._package_status()
        dependency_ready = not any(
            not package_status.get(package_name, {}).get("found")
            for package_name in cls.REQUIRED_PACKAGES.values()
        )

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
            "dependency_ready": dependency_ready,
            "username": username,
            "serial": serial,
            "number": number,
            "script_path": str(cls.script_path()),
            "packages": cls._package_status(),
            "missing": missing,
            "optional_missing": optional_missing,
            "error": error,
        }

    @classmethod
    def get_auth_status(cls) -> Dict[str, Any]:
        """Return EON readiness/auth status for the UI."""
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
    def _require_script(cls):
        if not cls.script_path().exists():
            raise FileNotFoundError(
                f"{cls.SCRIPT_NAME} is missing. Add the EON downloader engine to {CWD}."
            )
        auth_path = CWD / "eon_auth.py"
        if not auth_path.exists():
            raise FileNotFoundError(
                f"eon_auth.py is missing. Add the EON auth module to {CWD}."
            )

    @classmethod
    def _require_ready(cls):
        health = cls.get_health()
        if not health["engine_installed"]:
            missing_scripts = [name for name in cls.SCRIPT_FILES if not (CWD / name).exists()]
            raise FileNotFoundError(
                "Missing EON engine files: " + ", ".join(missing_scripts)
            )
        if not health.get("engine_download_supported"):
            raise RuntimeError(health.get("error") or "EON engine does not support downloads yet.")
        if not health["authenticated"]:
            raise RuntimeError("EON account/device is not configured.")
        if health["missing"]:
            raise RuntimeError(
                "EON environment is incomplete. Missing: " + ", ".join(health["missing"])
            )

    @classmethod
    def _require_engine_supported(cls):
        health = cls.get_health()
        if not health["engine_installed"]:
            missing_scripts = [name for name in cls.SCRIPT_FILES if not (CWD / name).exists()]
            raise FileNotFoundError(
                "Missing EON engine files: " + ", ".join(missing_scripts)
            )
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
    def _run_engine(cls, args: List[str], timeout: int = 120) -> subprocess.CompletedProcess:
        cls._require_script()
        cmd = [sys.executable, str(cls.script_path()), *args]
        return subprocess.run(
            cmd,
            cwd=str(CWD),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    @classmethod
    def save_device(cls, username: str, password: str, serial: str, number: str) -> Dict[str, Any]:
        """Validate and save EON account/device through the external engine."""
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
            res = cls._run_engine(
                [
                    "-u",
                    username,
                    "-p",
                    password,
                    "--device-serial",
                    serial,
                    "--device-number",
                    number,
                    "--save-device",
                ]
            )
        except Exception as exc:
            return {
                "success": True,
                "validated": False,
                "warning": cls._redact_text(str(exc)),
                "status": cls.get_health(),
            }

        if res.returncode != 0:
            return {
                "success": True,
                "validated": False,
                "warning": cls._redact_text(res.stderr or res.stdout or "EON device was saved locally, but engine validation failed."),
                "status": cls.get_health(),
            }

        return {"success": True, "validated": True, "status": cls.get_health()}

    @classmethod
    def list_channels(cls) -> List[str]:
        """List channels via the external EON downloader engine."""
        cls._require_engine_supported()
        res = cls._run_engine(["--list-channels", "--json"])
        if res.returncode != 0:
            raise RuntimeError(cls._redact_text(res.stderr or res.stdout or "Failed to list EON channels."))

        payload = json.loads(res.stdout or "[]")
        if not isinstance(payload, list):
            return []
        return [
            str(item.get("name") or item.get("title") or item.get("channel") or item)
            for item in payload
            if item
        ]

    @classmethod
    def list_episodes(cls, series_id: str) -> List[str]:
        """List series episodes via the external EON downloader engine."""
        series_id = series_id.strip()
        if not series_id:
            raise ValueError("Series ID is required.")

        cls._require_ready()
        res = cls._run_engine(["--series", series_id, "--list-episodes", "--json"])
        if res.returncode != 0:
            raise RuntimeError(cls._redact_text(res.stderr or res.stdout or "Failed to list EON episodes."))

        payload = json.loads(res.stdout or "[]")
        if not isinstance(payload, list):
            return []
        return [
            str(item.get("title") or item.get("name") or item.get("id") or item)
            for item in payload
            if item
        ]

    @classmethod
    def api_status(cls) -> Dict[str, Any]:
        cls._require_engine_supported()
        res = cls._run_engine(["--api-status"])
        if res.returncode != 0:
            raise RuntimeError(cls._redact_text(res.stderr or res.stdout or "Failed to read EON API status."))
        return json.loads(res.stdout or "{}")

    @classmethod
    def api_login(cls, username: str, password: str, serial: str, number: str) -> Dict[str, Any]:
        username = username.strip()
        serial = serial.strip()
        number = number.strip()
        if not username or not password or not serial or not number:
            raise ValueError("Username, password, serial and number are required.")
        cls._require_engine_supported()
        res = cls._run_engine(
            [
                "-u",
                username,
                "-p",
                password,
                "--device-serial",
                serial,
                "--device-number",
                number,
                "--login-api",
            ],
            timeout=60,
        )
        if res.returncode != 0:
            raise RuntimeError(cls._redact_text(res.stderr or res.stdout or "Failed to run EON API login."))
        return json.loads(res.stdout or "{}")

    @classmethod
    def refresh_api_token(cls) -> Dict[str, Any]:
        cls._require_engine_supported()
        res = cls._run_engine(["--refresh-token"], timeout=60)
        if res.returncode != 0:
            raise RuntimeError(cls._redact_text(res.stderr or res.stdout or "Failed to refresh EON API token."))
        return json.loads(res.stdout or "{}")

    @classmethod
    def search_vod(cls, query: str) -> List[Dict[str, Any]]:
        query = query.strip()
        if not query:
            return []
        cls._require_engine_supported()
        res = cls._run_engine(["--search", query, "--json"])
        if res.returncode != 0:
            raise RuntimeError(cls._redact_text(res.stderr or res.stdout or "Failed to search EON VOD."))
        payload = json.loads(res.stdout or "[]")
        return payload if isinstance(payload, list) else []

    @classmethod
    def get_epg(cls, channel: str) -> List[Dict[str, Any]]:
        channel = channel.strip()
        if not channel:
            return []
        cls._require_engine_supported()
        res = cls._run_engine(["--epg", channel, "--json"])
        if res.returncode != 0:
            raise RuntimeError(cls._redact_text(res.stderr or res.stdout or "Failed to fetch EON EPG."))
        payload = json.loads(res.stdout or "[]")
        return payload if isinstance(payload, list) else []

    @classmethod
    def get_vod_info(cls, target: str) -> Dict[str, Any]:
        target = target.strip()
        if not target:
            raise ValueError("VOD target is required.")
        cls._require_engine_supported()
        res = cls._run_engine(["--vod-info", target])
        if res.returncode != 0:
            raise RuntimeError(cls._redact_text(res.stderr or res.stdout or "Failed to fetch EON VOD info."))
        payload = json.loads(res.stdout or "{}")
        return payload if isinstance(payload, dict) else {"payload": payload}

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
        """Build a validated command for the external EON downloader engine."""
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

        cmd = [sys.executable, str(cls.script_path())]
        if mode == "vod":
            cmd += ["--vod", cls._normalize_vod_target(target), "-v", "-o", config.get_output_dir()]
        elif mode == "series":
            cmd += ["--series", target, "-o", config.get_output_dir()]
            if episodes:
                cmd += ["--episodes", episodes]
        elif mode == "live":
            cmd += ["--live", "-c", target, "--duration", str(duration), "-o", config.get_output_dir()]
            if play:
                cmd.append("--play")
                if player_path.strip():
                    cmd += ["--player", player_path.strip()]

        return cmd
