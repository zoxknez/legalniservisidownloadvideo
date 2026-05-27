import json
import logging
import shutil
import platform
from pathlib import Path
from typing import Dict, Any
import keyring

# Bug 4 Fix: Dynamic project root instead of hardcoded absolute paths
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_DIR = Path.home() / ".videodownload"
CONFIG_FILE = CONFIG_DIR / "config.json"
FALLBACK_CONFIG_DIR = PROJECT_ROOT / ".videodownload"
FALLBACK_CONFIG_FILE = FALLBACK_CONFIG_DIR / "config.json"
DEFAULT_OUTPUT_DIR = str(PROJECT_ROOT / "output")

DEFAULT_CONFIG = {
    "output_dir": DEFAULT_OUTPUT_DIR,
    "binaries": {
        "ffmpeg": "ffmpeg",
        "mkvmerge": "mkvmerge",
        "mp4decrypt": "mp4decrypt",
        "aria2c": "aria2c",
        "device_wvd": "device.wvd"
    },
    "credentials": {
        "voyo": {"email": "", "password": ""},
        "eon": {"username": "", "password": "", "serial": "", "number": ""},
        "hbomax": {"market": "emea", "token": ""},
        "rtsplaneta": {"email": "", "password": ""},
        "hrti": {"email": "", "password": ""}
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
        merged = json.loads(json.dumps(DEFAULT_CONFIG))
        for k, v in loaded.items():
            if isinstance(v, dict) and k in merged:
                merged[k].update(v)
            else:
                merged[k] = v
        return merged

    def _load(self) -> Dict[str, Any]:
        for path in (self.config_file, FALLBACK_CONFIG_FILE):
            if not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self.config_file = path
                return self._merge_defaults(loaded)
            except Exception:
                pass
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
        if service in self.data["credentials"]:
            self.data["credentials"][service].update(creds)
            self.save()

    def get_credentials(self, service: str) -> Dict[str, str]:
        return self.data["credentials"].get(service, {})

    def update_binary_path(self, binary_name: str, path: str):
        if binary_name in self.data["binaries"]:
            self.data["binaries"][binary_name] = path
            self.save()

    def get_binary_path(self, binary_name: str) -> str:
        return self.data["binaries"].get(binary_name, binary_name)

    def get_output_dir(self) -> str:
        d = self.data.get("output_dir")
        if not d:
            d = DEFAULT_OUTPUT_DIR
        Path(d).mkdir(parents=True, exist_ok=True)
        return d

    def set_output_dir(self, path: str):
        self.data["output_dir"] = path
        self.save()

    def set_credential(self, service: str, key: str, value: str):
        """Store a single credential securely using keyring and update JSON cache."""
        try:
            keyring.set_password(f"{service}_{key}", "videodownloadservisi", value)
            # also keep a copy in the json config for fallback/display
            self.update_credentials(service, {key: value})
        except Exception as e:
            logger.error(f"Failed to store credential for {service}:{key}: {e}")

    def get_credential(self, service: str, key: str) -> str:
        """Retrieve a credential from keyring; fallback to JSON if missing."""
        try:
            val = keyring.get_password(f"{service}_{key}", "videodownloadservisi")
            if val:
                return val
        except Exception as e:
            logger.error(f"Failed to get credential for {service}:{key}: {e}")
        # fallback to JSON config cache
        return self.data.get("credentials", {}).get(service, {}).get(key, "")

    def check_binaries_status(self) -> Dict[str, Any]:
        status = {}
        for name, path in self.data["binaries"].items():
            found = False
            resolved_path = path

            # Special checks for device.wvd (just a file, not executable)
            if name == "device_wvd":
                p = Path(path)
                if p.exists():
                    found = True
                    resolved_path = str(p.resolve())
                else:
                    # check in root and binaries folder
                    for check_dir in [PROJECT_ROOT, PROJECT_ROOT / "binaries"]:
                        check_path = check_dir / "device.wvd"
                        if check_path.exists():
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
                # Common Windows directories
                windows_hints = []
                if name == "mkvmerge":
                    windows_hints = [
                        r"C:\Program Files\MKVToolNix\mkvmerge.exe",
                        r"C:\Program Files (x86)\MKVToolNix\mkvmerge.exe"
                    ]
                elif name == "mp4decrypt":
                    windows_hints = [
                        str(PROJECT_ROOT / "binaries" / "mp4decrypt.exe"),
                        str(PROJECT_ROOT / "mp4decrypt.exe")
                    ]

                for hint in windows_hints:
                    if Path(hint).exists():
                        found = True
                        resolved_path = hint
                        break
            
            status[name] = {"found": found, "path": resolved_path}
        
        return status

# Singleton instance
config = AppConfig()
