import json
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Bug 4 Fix: Dynamic project root instead of hardcoded absolute paths
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_DIR = Path.home() / ".videodownload"
CONFIG_FILE = CONFIG_DIR / "config.json"
FALLBACK_CONFIG_DIR = PROJECT_ROOT / ".videodownload"
FALLBACK_CONFIG_FILE = FALLBACK_CONFIG_DIR / "config.json"
DEFAULT_OUTPUT_DIR = str(PROJECT_ROOT / "output")

DEFAULT_CONFIG = {
    "output_dir": DEFAULT_OUTPUT_DIR,
    "transcode_mode": "off",
    "ytdlp_name_template": "%(title)s.%(ext)s",
    "max_concurrent_downloads": 2,
    "server": {
        "api_key": ""
    },
    "binaries": {
        "ffmpeg": "ffmpeg",
        "mkvmerge": "mkvmerge",
        "mp4decrypt": "mp4decrypt",
        "aria2c": "aria2c",
        "device_wvd": "device.wvd"
    },
    "credentials": {
        "voyo": {"email": "", "password": "", "variant": "rs"},
        "eon": {"username": "", "password": "", "serial": "", "number": ""},
        "hbomax": {"market": "emea", "token": ""},
        "rtsplaneta": {"email": "", "password": ""},
        "hrti": {"email": "", "password": ""},
        "skyshowtime": {"token": "", "expiry": "", "territory": "RS"}
    },
    "sniffer": {
        "auto_download": True
    }
}

class AppConfig:
    def __init__(self):
        self.config_file = CONFIG_FILE
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.config_file = FALLBACK_CONFIG_FILE
        self.data = self._load()

    def _merge_defaults(self, loaded: Dict[str, Any]) -> Dict[str, Any]:
        def deep_merge(dict1: dict, dict2: dict) -> dict:
            for key, value in dict2.items():
                if isinstance(value, dict) and key in dict1 and isinstance(dict1[key], dict):
                    deep_merge(dict1[key], value)
                else:
                    dict1[key] = json.loads(json.dumps(value))
            return dict1
        merged = json.loads(json.dumps(DEFAULT_CONFIG))
        return deep_merge(merged, loaded)

    def _load(self) -> Dict[str, Any]:
        for path in (self.config_file, FALLBACK_CONFIG_FILE):
            if not path.exists():
                continue
            try:
                raw = path.read_text(encoding="utf-8")
                loaded = json.loads(raw)
                if not isinstance(loaded, dict):
                    logger.warning("Config at %s is not a JSON object, using defaults.", path)
                    continue
                self.config_file = path
                return self._merge_defaults(loaded)
            except json.JSONDecodeError as e:
                logger.error(
                    "Corrupt config at %s (line %d, col %d): %s — using defaults.",
                    path, e.lineno, e.colno, e.msg,
                )
                backup = path.with_suffix(".json.bak")
                try:
                    import shutil as _shutil
                    _shutil.copy2(path, backup)
                    logger.info("Backed up corrupt config to %s", backup)
                except OSError:
                    pass
            except Exception as e:
                logger.error("Failed to load config from %s: %s", path, e)
        return json.loads(json.dumps(DEFAULT_CONFIG))

    def _write(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def save(self):
        try:
            self._write(self.config_file)
        except Exception as e:
            if self.config_file != FALLBACK_CONFIG_FILE:
                try:
                    self._write(FALLBACK_CONFIG_FILE)
                    self.config_file = FALLBACK_CONFIG_FILE
                    return
                except Exception as fallback_error:
                    print(f"Failed to save config: {fallback_error}")
                    return
            print(f"Failed to save config: {e}")

    def update_credentials(self, service: str, creds: Dict[str, str]):
        from backend.credentials_store import save_service_credentials
        save_service_credentials(service, creds, config_module=self)

    def get_credentials(self, service: str) -> Dict[str, str]:
        from backend.credentials_store import get_service_credentials
        return get_service_credentials(service, config_module=self)

    def update_binary_path(self, binary_name: str, path: str):
        if binary_name in self.data["binaries"]:
            self.data["binaries"][binary_name] = path
            self.save()

    def get_binary_path(self, binary_name: str) -> str:
        configured = self.data["binaries"].get(binary_name, binary_name)
        if shutil.which(configured):
            return configured
        ext = ".exe" if os.name == "nt" else ""
        local_path = PROJECT_ROOT / "binaries" / f"{binary_name}{ext}"
        if local_path.exists():
            return str(local_path.resolve())
        local_configured = PROJECT_ROOT / "binaries" / f"{configured}{ext}"
        if local_configured.exists():
            return str(local_configured.resolve())
        return configured

    def get_output_dir(self) -> str:
        d = self.data.get("output_dir")
        if not d:
            d = DEFAULT_OUTPUT_DIR
        Path(d).mkdir(parents=True, exist_ok=True)
        return d

    def set_output_dir(self, path: str):
        self.data["output_dir"] = path
        self.save()

    def get_transcode_mode(self) -> str:
        return self.data.get("transcode_mode", "off")

    def set_transcode_mode(self, mode: str):
        self.data["transcode_mode"] = mode
        self.save()

    def get_ytdlp_name_template(self) -> str:
        return self.data.get("ytdlp_name_template", "%(title)s.%(ext)s")

    def set_ytdlp_name_template(self, tmpl: str):
        self.data["ytdlp_name_template"] = tmpl
        self.save()

    def get_max_concurrent_downloads(self) -> int:
        try:
            return int(self.data.get("max_concurrent_downloads", 2))
        except (ValueError, TypeError):
            return 2

    def set_max_concurrent_downloads(self, limit: int):
        self.data["max_concurrent_downloads"] = int(limit)
        self.save()

    def set_credential(self, service: str, key: str, value: str):
        """Store a single credential field (secrets go to OS keyring)."""
        self.update_credentials(service, {key: value})

    def get_credential(self, service: str, key: str) -> str:
        return self.get_credentials(service).get(key, "")

    def check_binaries_status(self) -> Dict[str, Any]:
        status = {}
        for name, path in self.data["binaries"].items():
            found = False
            resolved_path = path

            # Special checks for device.wvd (just a file, not executable)
            if name == "device_wvd":
                p = Path(path)
                
                def verify_wvd(file_path: Path) -> bool:
                    try:
                        if not file_path.exists():
                            return False
                        sz = file_path.stat().st_size
                        if sz < 100 or sz > 102400:  # Valid WVD binary blobs are usually 1KB-10KB
                            return False
                        # Confirm readable
                        with open(file_path, "rb") as f:
                            f.read(10)
                        return True
                    except Exception:
                        return False
                
                if verify_wvd(p):
                    found = True
                    resolved_path = str(p.resolve())
                else:
                    # check in common search directories (root, binaries, rtsplaneta, cdm, home dirs)
                    search_dirs = [
                        PROJECT_ROOT,
                        PROJECT_ROOT / "binaries",
                        PROJECT_ROOT / "rtsplaneta",
                        PROJECT_ROOT / "cdm",
                        PROJECT_ROOT / "hrti",
                        PROJECT_ROOT / "eon",
                        Path.home() / ".wvd",
                        Path.home() / ".videodownload",
                        Path.home() / ".hrti"
                    ]
                    for check_dir in search_dirs:
                        check_path = check_dir / "device.wvd"
                        if verify_wvd(check_path):
                            found = True
                            resolved_path = str(check_path.resolve())
                            break
                status[name] = {"found": found, "path": resolved_path}
                continue

            # Standard binary check
            if shutil.which(path):
                found = True
                resolved_path = shutil.which(path)
            else:
                # Local binaries fallback
                ext = ".exe" if os.name == "nt" else ""
                windows_hints = [
                    str(PROJECT_ROOT / "binaries" / f"{name}{ext}"),
                    str(PROJECT_ROOT / "binaries" / f"{path}{ext}"),
                ]
                
                # Common Windows directories
                if name == "mkvmerge":
                    windows_hints.extend([
                        r"C:\Program Files\MKVToolNix\mkvmerge.exe",
                        r"C:\Program Files (x86)\MKVToolNix\mkvmerge.exe"
                    ])
                elif name == "mp4decrypt":
                    windows_hints.append(str(PROJECT_ROOT / "mp4decrypt.exe"))

                for hint in windows_hints:
                    if Path(hint).exists():
                        found = True
                        resolved_path = str(Path(hint).resolve())
                        break
            
            status[name] = {"found": found, "path": resolved_path}
        
        return status

# Singleton instance
config = AppConfig()
