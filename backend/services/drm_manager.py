"""
Centralizovani Widevine DRM Manager
====================================
Singleton koji upravlja svim CDM operacijama u sistemu:

  - Jedan CDM instanc dijele EON, HRTi, Voyo downloaderji
  - Keširanje ključeva po PSSH-u (izbjegava duplikatne license requeste)
  - Deep WVD diagnostics: security level (L1/L3), sistem ID, CDM version
  - Provider certificate prefetch za optimizovano license handshake
  - Multi-PSSH fallback (probava sve PSSH-ove iz MPD-a)
  - Detaljno logovanje svakog license exchange-a
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import requests

logger = logging.getLogger("DRMManager")

# ─── Widevine System UUID ───────────────────────────────────────────────────
WIDEVINE_SYSTEM_ID = "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"

# Vendor CDM security level names
_SECURITY_LEVEL_MAP = {
    1: "L1 (TEE – Hardware Protected)",
    2: "L2 (TEE – Partial)",
    3: "L3 (Software – No Hardware)",
}

# ─── Key Cache ───────────────────────────────────────────────────────────────

class _KeyCache:
    """
    In-memory cache for Widevine content keys.
    Key: SHA-256 of (pssh_b64 + license_url)
    Value: list of "kid:key" strings, TTL timestamp
    """

    DEFAULT_TTL = 12 * 3600  # 12 hours

    def __init__(self):
        self._store: Dict[str, Tuple[List[str], float]] = {}
        self._lock = threading.Lock()

    def _make_key(self, pssh_b64: str, license_url: str) -> str:
        raw = f"{pssh_b64.strip()}|{license_url.strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, pssh_b64: str, license_url: str) -> Optional[List[str]]:
        k = self._make_key(pssh_b64, license_url)
        with self._lock:
            entry = self._store.get(k)
            if entry:
                keys, ts = entry
                if time.time() - ts < self.DEFAULT_TTL:
                    logger.info(f"[KeyCache] Cache HIT for PSSH {pssh_b64[:24]}…")
                    return keys
                else:
                    del self._store[k]
        return None

    def put(self, pssh_b64: str, license_url: str, keys: List[str]):
        k = self._make_key(pssh_b64, license_url)
        with self._lock:
            self._store[k] = (keys, time.time())
        logger.info(f"[KeyCache] Cached {len(keys)} key(s) for PSSH {pssh_b64[:24]}…")

    def invalidate_all(self):
        with self._lock:
            self._store.clear()
        logger.info("[KeyCache] All keys invalidated.")

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._store)
            now = time.time()
            alive = sum(1 for _, (_, ts) in self._store.items()
                        if now - ts < self.DEFAULT_TTL)
        return {"total_entries": total, "alive_entries": alive}


# ─── WVD Diagnostics ─────────────────────────────────────────────────────────

def _read_wvd_metadata(wvd_path: Path) -> Dict[str, Any]:
    """
    Deep-read a .wvd file and extract all available metadata.
    Returns a dict with: security_level, system_id, client_id_size,
    private_key_size, wvd_version, is_valid, error.

    The .wvd format (pywidevine):
      - magic: b'WVD' (3 bytes)
      - version: 1 byte (currently 2)
      - type: 1 byte (0=CHROME, 1=ANDROID)
      - security_level: 1 byte (1=L1, 2=L2, 3=L3)
      - flags: 1 byte
      - private_key: length-prefixed bytes
      - client_id: length-prefixed bytes
    """
    result: Dict[str, Any] = {
        "is_valid": False,
        "wvd_version": None,
        "device_type": None,
        "security_level": None,
        "security_level_name": "Unknown",
        "private_key_size": 0,
        "client_id_size": 0,
        "system_id": WIDEVINE_SYSTEM_ID,
        "file_size": 0,
        "error": None,
    }

    try:
        if not wvd_path.exists():
            result["error"] = "File not found"
            return result

        result["file_size"] = wvd_path.stat().st_size

        # Try pywidevine Device.load() for rich metadata
        try:
            from pywidevine.device import Device
            device = Device.load(str(wvd_path))
            sl = getattr(device, "security_level", None)
            if sl is None:
                # pywidevine >= 1.8: security_level might be on the CDM
                from pywidevine.cdm import Cdm
                cdm = Cdm.from_device(device)
                sl = getattr(cdm, "security_level", None)
            result["security_level"] = int(sl) if sl is not None else 3
            result["security_level_name"] = _SECURITY_LEVEL_MAP.get(
                result["security_level"], f"Unknown (level {sl})"
            )
            result["device_type"] = getattr(device, "type", {}).name if hasattr(
                getattr(device, "type", None), "name") else str(getattr(device, "type", "UNKNOWN"))
            result["wvd_version"] = getattr(device, "wvd_version", None)

            # Estimate private key size from RSA key object
            pk = getattr(device, "private_key", None)
            if pk:
                try:
                    result["private_key_size"] = pk.key_size // 8
                except Exception:
                    result["private_key_size"] = -1

            # Client ID (protobuf blob)
            cid = getattr(device, "client_id", None)
            if cid:
                try:
                    result["client_id_size"] = len(cid.SerializeToString())
                except Exception:
                    result["client_id_size"] = -1

            result["is_valid"] = True
            return result

        except Exception as pywidevine_err:
            logger.debug(f"pywidevine Device.load failed: {pywidevine_err}, falling back to manual parse")

        # Manual binary parse fallback
        with open(wvd_path, "rb") as f:
            header = f.read(4)

        if len(header) < 4:
            result["error"] = "File too small"
            return result

        if header[:3] == b"WVD":
            result["wvd_version"] = header[3]

        # Try to read the full struct
        with open(wvd_path, "rb") as f:
            data = f.read()

        if len(data) >= 8:
            magic = data[0:3]
            version = data[3]
            dev_type = data[4]
            sec_level = data[5]

            if magic == b"WVD":
                result["wvd_version"] = version
                result["device_type"] = {0: "CHROME", 1: "ANDROID"}.get(dev_type, f"TYPE_{dev_type}")
                result["security_level"] = sec_level
                result["security_level_name"] = _SECURITY_LEVEL_MAP.get(sec_level, f"Unknown ({sec_level})")
                result["is_valid"] = True
            else:
                result["error"] = f"Invalid magic bytes: {magic.hex()}"
        else:
            result["error"] = "File too small for WVD format"

    except Exception as e:
        result["error"] = str(e)

    return result


# ─── DRM Manager Singleton ───────────────────────────────────────────────────

class DRMManager:
    """
    Thread-safe singleton. One CDM instance shared across all downloaders.
    Manages key caching, provider certificates, and diagnostics.
    """

    _instance: Optional[DRMManager] = None
    _lock = threading.Lock()

    def __new__(cls) -> DRMManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.cdm = None
        self.device = None
        self.PSSH = None
        self.legacy_mode = False
        self.wvd_path: Optional[Path] = None
        self.wvd_metadata: Dict[str, Any] = {}

        # Per-service provider certificates (fetched lazily)
        self._provider_certs: Dict[str, bytes] = {}
        self._cert_lock = threading.Lock()

        self.key_cache = _KeyCache()
        self._init_lock = threading.Lock()

        self._init_cdm()

    # ── CDM Initialization ────────────────────────────────────────────────────

    def _search_wvd(self) -> Optional[Path]:
        """Search for .wvd device file in all known locations."""
        from pathlib import Path as _P
        try:
            from backend.config import PROJECT_ROOT, config
            search_dirs = [
                _P(config.get_binary_path("device_wvd")).parent
                if config.get_binary_path("device_wvd") != "device.wvd" else None,
                PROJECT_ROOT,
                PROJECT_ROOT / "binaries",
                PROJECT_ROOT / "cdm",
                PROJECT_ROOT / "rtsplaneta",
                PROJECT_ROOT / "hrti",
                PROJECT_ROOT / "eon",
                _P.cwd(),
                _P.cwd() / "cdm",
                _P.home() / ".wvd",
                _P.home() / ".videodownload",
                _P.home() / ".hrti",
            ]
        except Exception:
            import os
            search_dirs = [_P.cwd(), _P.cwd() / "cdm", _P.home() / ".wvd"]

        for d in search_dirs:
            if d is None:
                continue
            candidate = d / "device.wvd" if d.is_dir() else d
            if candidate.is_file() and candidate.suffix == ".wvd":
                sz = candidate.stat().st_size
                if 100 < sz < 102400:
                    return candidate
            # Also glob for any *.wvd inside the dir
            if d.is_dir():
                for wvd in d.glob("*.wvd"):
                    sz = wvd.stat().st_size
                    if 100 < sz < 102400:
                        return wvd
        return None

    def _init_cdm(self):
        with self._init_lock:
            try:
                from pywidevine.cdm import Cdm
                from pywidevine.device import Device
                from pywidevine.pssh import PSSH

                self.PSSH = PSSH
                found = self._search_wvd()
                if found:
                    self.wvd_path = found
                    self.device = Device.load(str(found))
                    self.cdm = Cdm.from_device(self.device)
                    self.wvd_metadata = _read_wvd_metadata(found)
                    sl = self.wvd_metadata.get("security_level_name", "Unknown")
                    logger.info(f"[DRMManager] CDM loaded: {found}  [{sl}]")
                else:
                    logger.warning("[DRMManager] No .wvd device file found.")
                    self.wvd_metadata = {"is_valid": False, "error": "No .wvd file found"}
            except ImportError:
                logger.warning("[DRMManager] pywidevine not installed. Trying legacy mode.")
                self._init_legacy()
            except Exception as e:
                logger.error(f"[DRMManager] CDM init error: {e}")
                self.wvd_metadata = {"is_valid": False, "error": str(e)}

    def _init_legacy(self):
        try:
            from pywidevine.decrypt.wvdecryptcustom import WvDecrypt  # noqa
            self.legacy_mode = True
            logger.info("[DRMManager] Legacy CDM mode active.")
        except ImportError as e:
            logger.error(f"[DRMManager] No CDM available: {e}")

    def reload(self):
        """Force reload the CDM (useful after user updates the .wvd file)."""
        self.cdm = None
        self.device = None
        self.PSSH = None
        self.legacy_mode = False
        self.wvd_path = None
        self.wvd_metadata = {}
        self.key_cache.invalidate_all()
        with self._cert_lock:
            self._provider_certs.clear()
        self._init_cdm()
        logger.info("[DRMManager] CDM reloaded.")

    def is_ready(self) -> bool:
        return self.cdm is not None or self.legacy_mode

    # ── Provider Certificate ──────────────────────────────────────────────────

    def prefetch_provider_cert(self, service_name: str, license_url: str,
                                headers: Optional[Dict[str, str]] = None) -> bool:
        """
        Fetch the provider's Widevine service certificate.
        This certificate is used to encrypt the client ID in license requests,
        improving privacy and sometimes required by certain license servers.
        Returns True on success.
        """
        if not self.cdm:
            return False
        with self._cert_lock:
            if service_name in self._provider_certs:
                return True  # Already fetched

        try:
            session_id = self.cdm.open()
            try:
                # Get a "service certificate" challenge (empty PSSH-like request)
                challenge = self.cdm.get_service_certificate_challenge(session_id)
                resp = requests.post(license_url, data=challenge,
                                     headers=headers or {"Content-Type": "application/octet-stream"},
                                     timeout=15)
                if resp.status_code == 200 and resp.content:
                    self.cdm.set_service_certificate(session_id, resp.content)
                    cert_data = resp.content
                    with self._cert_lock:
                        self._provider_certs[service_name] = cert_data
                    logger.info(f"[DRMManager] Provider cert fetched for '{service_name}' "
                                f"({len(cert_data)} bytes)")
                    return True
            finally:
                self.cdm.close(session_id)
        except Exception as e:
            logger.debug(f"[DRMManager] Provider cert prefetch failed for '{service_name}': {e}")
        return False

    # ── License Exchange ──────────────────────────────────────────────────────

    def _unwrap_license(self, resp: requests.Response) -> bytes:
        """
        Handle all known license response formats:
          - DRMtoday: {"status":"OK","license":"<base64>"}
          - Raw protobuf
          - Various JSON wrappers
        """
        try:
            j = resp.json()
            if j.get("status") == "OK" and "license" in j:
                return base64.b64decode(j["license"])
            for field in ("license", "ckc", "message", "licenseData",
                          "license_data", "widevine_license", "LicenseMessage"):
                if field in j:
                    try:
                        return base64.b64decode(j[field])
                    except Exception:
                        continue
        except Exception:
            pass
        return resp.content

    def _get_keys_modern(self, pssh_b64: str, license_url: str,
                         headers: dict, service_name: str = "") -> List[str]:
        if not self.cdm:
            raise RuntimeError("CDM not initialized. Check device.wvd file.")

        pssh = self.PSSH(pssh_b64)
        session_id = self.cdm.open()

        # Apply provider cert if available
        with self._cert_lock:
            cert = self._provider_certs.get(service_name)
        if cert:
            try:
                self.cdm.set_service_certificate(session_id, cert)
            except Exception:
                pass

        try:
            challenge = self.cdm.get_license_challenge(session_id, pssh)
            logger.debug(f"[DRMManager] Challenge size: {len(challenge)}B → {license_url}")

            resp = requests.post(license_url, data=challenge, headers=headers, timeout=20)
            resp.raise_for_status()

            logger.debug(
                f"[DRMManager] License response: HTTP {resp.status_code}  "
                f"CT={resp.headers.get('Content-Type', '?')}  "
                f"size={len(resp.content)}B  "
                f"first8={resp.content[:8].hex()}"
            )

            license_bytes = self._unwrap_license(resp)
            logger.debug(
                f"[DRMManager] Unwrapped: size={len(license_bytes)}B  "
                f"first8={license_bytes[:8].hex()}"
            )

            self.cdm.parse_license(session_id, license_bytes)

            keys = []
            for key in self.cdm.get_keys(session_id):
                if key.type == "CONTENT":
                    keys.append(f"{key.kid.hex}:{key.key.hex()}")
            logger.info(f"[DRMManager] Got {len(keys)} CONTENT key(s) from '{service_name}'")
            return keys
        finally:
            self.cdm.close(session_id)

    def _get_keys_legacy(self, pssh_b64: str, license_url: str,
                         headers: dict, service_name: str = "") -> List[str]:
        from pywidevine.decrypt.wvdecryptcustom import WvDecrypt
        for attempt in range(3):
            try:
                wvd = WvDecrypt(init_data_b64=pssh_b64.encode(), cert_data_b64=None)
                challenge = wvd.get_challenge()
                resp = requests.post(license_url, data=challenge, headers=headers, timeout=20)
                resp.raise_for_status()
                wvd.update_license(base64.b64encode(resp.content))
                success, keys = wvd.start_process()
                if success and keys:
                    return keys
            except Exception as e:
                logger.warning(f"[DRMManager] Legacy key attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(2)
        raise Exception("Failed to get decryption keys after 3 legacy attempts")

    def get_keys(self, pssh_b64: str, license_url: str, headers: dict,
                 service_name: str = "") -> List[str]:
        """
        Main entry point. Checks cache first, then fetches from license server.
        """
        # Cache lookup
        cached = self.key_cache.get(pssh_b64, license_url)
        if cached:
            return cached

        # Fetch from server
        if self.legacy_mode:
            keys = self._get_keys_legacy(pssh_b64, license_url, headers, service_name)
        else:
            keys = self._get_keys_modern(pssh_b64, license_url, headers, service_name)

        if keys:
            self.key_cache.put(pssh_b64, license_url, keys)
        return keys

    # ── Multi-PSSH Fallback ───────────────────────────────────────────────────

    def get_keys_multi_pssh(self, pssh_list: List[str], license_url: str,
                             headers: dict, service_name: str = "") -> List[str]:
        """
        Try each PSSH in the list until keys are obtained.
        Merges keys from all successful attempts (de-duplicated by KID).
        """
        all_keys: Dict[str, str] = {}  # kid -> key

        for i, pssh in enumerate(pssh_list):
            try:
                logger.info(f"[DRMManager] Trying PSSH {i + 1}/{len(pssh_list)}: {pssh[:32]}…")
                keys = self.get_keys(pssh, license_url, headers, service_name)
                for pair in keys:
                    if ":" in pair:
                        kid, key = pair.split(":", 1)
                        all_keys[kid] = key
            except Exception as e:
                logger.warning(f"[DRMManager] PSSH {i + 1} failed: {e}")

        if not all_keys:
            raise RuntimeError("No keys obtained from any PSSH")

        return [f"{kid}:{key}" for kid, key in all_keys.items()]

    # ── PSSH Extraction ───────────────────────────────────────────────────────

    @staticmethod
    def extract_all_pssh_from_mpd(mpd_text: str) -> List[str]:
        """
        Extract ALL Widevine PSSH boxes from an MPD manifest.
        Returns a deduplicated list (most specific/video PSSH first).
        """
        import xmltodict

        pssh_list: List[str] = []
        seen: set = set()

        try:
            mpd = xmltodict.parse(mpd_text)
            periods = mpd.get("MPD", {}).get("Period", [])
            if isinstance(periods, dict):
                periods = [periods]

            for period in periods:
                adapt_sets = period.get("AdaptationSet", [])
                if isinstance(adapt_sets, dict):
                    adapt_sets = [adapt_sets]
                for adapt in adapt_sets:
                    cp = adapt.get("ContentProtection", [])
                    if isinstance(cp, dict):
                        cp = [cp]
                    for prot in cp:
                        scheme = prot.get("@schemeIdUri", "")
                        if scheme.lower() == WIDEVINE_SYSTEM_ID.lower():
                            pssh_elem = prot.get("cenc:pssh") or prot.get("pssh")
                            val = ""
                            if isinstance(pssh_elem, str):
                                val = pssh_elem.strip()
                            elif isinstance(pssh_elem, dict):
                                val = pssh_elem.get("#text", "").strip()
                            if val and val not in seen:
                                pssh_list.append(val)
                                seen.add(val)
        except Exception as e:
            logger.warning(f"[DRMManager] MPD XML parse error: {e}")

        # Regex fallback
        for m in re.finditer(
            r"<(?:cenc:)?pssh[^>]*>([A-Za-z0-9+/=]+)</(?:cenc:)?pssh>",
            mpd_text, re.IGNORECASE
        ):
            val = m.group(1).strip()
            if val and val not in seen:
                pssh_list.append(val)
                seen.add(val)

        logger.info(f"[DRMManager] Found {len(pssh_list)} PSSH(s) in MPD")
        return pssh_list

    # ── Health / Diagnostics ──────────────────────────────────────────────────

    def get_health_report(self) -> Dict[str, Any]:
        """
        Full DRM health report for the UI.
        """
        report: Dict[str, Any] = {
            "cdm_ready": self.is_ready(),
            "legacy_mode": self.legacy_mode,
            "wvd_file": str(self.wvd_path) if self.wvd_path else None,
            "wvd_metadata": self.wvd_metadata,
            "key_cache": self.key_cache.stats(),
            "provider_certs_fetched": list(self._provider_certs.keys()),
            "pywidevine_version": None,
            "recommendations": [],
        }

        # pywidevine version
        try:
            import pywidevine
            report["pywidevine_version"] = getattr(pywidevine, "__version__", "installed")
        except ImportError:
            report["pywidevine_version"] = "not installed"

        # Recommendations
        sl = self.wvd_metadata.get("security_level", 0)
        if not report["cdm_ready"]:
            report["recommendations"].append(
                "CDM nije spreman. Dodajte device.wvd fajl u root projekta."
            )
        elif sl == 3 or sl == 0:
            report["recommendations"].append(
                "Koristite L3 (softverski) CDM. Za 1080p+ i SDR streaming to je dovoljno. "
                "L1 zahtijeva fizički TEE čip i nije dostupan na PC-u."
            )
        elif sl == 1:
            report["recommendations"].append(
                "L1 CDM aktivan – maksimalna zaštita sadržaja, podržan hardverski output."
            )

        if report["wvd_metadata"].get("is_valid") and not self.wvd_path:
            report["recommendations"].append(
                "WVD fajl je validan ali putanja nije potvrđena."
            )

        if not self._provider_certs:
            report["recommendations"].append(
                "Nema prefetch-ovanih provider sertifikata. "
                "Koristite /api/drm/prefetch-cert za unaprijeđen license handshake."
            )

        return report


# ── Module-level singleton ────────────────────────────────────────────────────
drm_manager = DRMManager()
