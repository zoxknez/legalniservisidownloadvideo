import os
import json
import base64
import sqlite3
import shutil
import ctypes
import tempfile
import logging
import sys
from ctypes import wintypes
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from Crypto.Cipher import AES

from backend.utils.cancellable_subprocess import run as run_subprocess

logger = logging.getLogger("BrowserCookies")

DOMAIN_TO_SERVICE = {
    "rtsplaneta.rs": "rtsplaneta",
    "eon.tv": "eon",
    "voyo.rs": "voyo",
    "voyo.hr": "voyo",
    "voyo.rtl.hr": "voyo",
    "hrti.hrt.hr": "hrti",
    "skyshowtime.com": "skyshowtime",
    "skyott.com": "skyshowtime",
}


def browser_sync_supported() -> bool:
    return sys.platform == "win32"


def _service_report(domain_report: Dict[str, bool]) -> Dict[str, bool]:
    return {
        DOMAIN_TO_SERVICE[domain]: ok
        for domain, ok in domain_report.items()
        if domain in DOMAIN_TO_SERVICE
    }


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ('cbData', wintypes.DWORD),
        ('pbData', ctypes.POINTER(ctypes.c_char))
    ]

def _dpapi_decrypt(encrypted_bytes: bytes) -> bytes:
    """Decrypt bytes using Windows DPAPI."""
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    p_data_in = DATA_BLOB(len(encrypted_bytes), (ctypes.c_byte * len(encrypted_bytes))(*encrypted_bytes))
    p_data_out = DATA_BLOB()

    # Call CryptUnprotectData
    success = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(p_data_in),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(p_data_out)
    )

    if not success:
        raise RuntimeError("DPAPI CryptUnprotectData failed.")

    # Retrieve data
    decrypted_bytes = bytes(ctypes.cast(p_data_out.pbData, ctypes.POINTER(ctypes.c_byte * p_data_out.cbData)).contents)
    
    # Free memory
    ctypes.windll.kernel32.LocalFree(p_data_out.pbData)
    
    return decrypted_bytes

def _get_chromium_key(local_state_path: Path) -> Optional[bytes]:
    """Retrieve and decrypt the Chromium master key from Local State."""
    try:
        if not local_state_path.exists():
            return None
        with open(local_state_path, 'r', encoding='utf-8') as f:
            local_state = json.load(f)
        
        encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
        # Remove DPAPI prefix 'DPAPI'
        encrypted_key = encrypted_key[5:]
        decrypted_key = _dpapi_decrypt(encrypted_key)
        return decrypted_key
    except Exception as e:
        logger.error(f"Error fetching encryption key from {local_state_path}: {e}")
        return None

def _decrypt_cookie_value(encrypted_value: bytes, key: bytes) -> str:
    """Decrypt a Chromium cookie value encrypted with AES-256-GCM."""
    try:
        if not encrypted_value:
            return ""
        if encrypted_value[:3] == b'v10':
            # Format: 'v10' + 12-byte IV + ciphertext + 16-byte GCM Auth Tag
            payload = encrypted_value[3:]
            iv = payload[:12]
            ciphertext_with_tag = payload[12:]
            
            # pycryptodome requires ciphertext and tag separated
            ciphertext = ciphertext_with_tag[:-16]
            tag = ciphertext_with_tag[-16:]
            
            cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
            decrypted = cipher.decrypt_and_verify(ciphertext, tag)
            return decrypted.decode('utf-8', errors='ignore')
        else:
            # Older versions used pure DPAPI
            return _dpapi_decrypt(encrypted_value).decode('utf-8', errors='ignore')
    except Exception as e:
        logger.debug(f"Failed to decrypt cookie value: {e}")
        return ""

def _extract_cookies_from_db(db_path: Path, key: bytes, domains: List[str]) -> Tuple[List[Dict[str, str]], bool]:
    """Query and decrypt cookies from a specific Chromium database file."""
    cookies = []
    browser_locked = False
    if not db_path.exists():
        return cookies, browser_locked

    # Copy database to temporary file to avoid locking issues when browser is open
    temp_dir = tempfile.gettempdir()
    temp_db_path = Path(temp_dir) / f"temp_cookies_{os.getpid()}.db"
    
    try:
        import subprocess
        import sys
        if sys.platform == "win32":
            run_subprocess(
                ["cmd", "/c", "copy", "/y", str(db_path), str(temp_db_path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            run_subprocess(
                ["cp", "--", str(db_path), str(temp_db_path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        
        # Fallback to shutil.copyfile if copy command failed or file wasn't created
        if not temp_db_path.exists():
            shutil.copyfile(db_path, temp_db_path)
        
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Build SQL query with domain filters
        query = "SELECT host_key, name, value, encrypted_value FROM cookies WHERE "
        query += " OR ".join([f"host_key LIKE '%{d}%'" for d in domains])
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        for host_key, name, value, encrypted_value in rows:
            decrypted_val = value
            if encrypted_value:
                decrypted_val = _decrypt_cookie_value(encrypted_value, key)
            
            cookies.append({
                "domain": host_key,
                "name": name,
                "value": decrypted_val
            })
            
        conn.close()
    except PermissionError:
        browser_locked = True
        logger.warning(
            "Cookies baza je zaključana (%s) — zatvorite Chrome/Edge/Brave pa pokušajte ponovo.",
            db_path,
        )
    except Exception as e:
        err = str(e).lower()
        if "permission denied" in err or "being used by another process" in err:
            browser_locked = True
            logger.warning(
                "Cookies baza je zaključana (%s) — zatvorite pretraživač pa pokušajte ponovo.",
                db_path,
            )
        else:
            logger.error(f"Error querying SQLite database {db_path}: {e}")
    finally:
        if temp_db_path.exists():
            try:
                os.remove(temp_db_path)
            except Exception:
                pass
                
    return cookies, browser_locked


def get_browser_cookies(domains: List[str]) -> Tuple[Dict[str, List[Dict[str, str]]], bool]:
    """
    Search all chromium installations and user profiles for specific domain cookies.
    Returns:
        (results dict, browser_locked flag)
    """
    appdata = Path(os.environ.get('LOCALAPPDATA', ''))
    
    # Configure known Chromium browsers and their user data paths
    browsers = {
        "Google Chrome": appdata / r"Google\Chrome\User Data",
        "Microsoft Edge": appdata / r"Microsoft\Edge\User Data",
        "Brave Browser": appdata / r"BraveSoftware\Brave-Browser\User Data"
    }
    
    results = {d: [] for d in domains}
    browser_locked = False
    
    for browser_name, user_data_path in browsers.items():
        if not user_data_path.exists():
            continue
            
        logger.info(f"Scanning browser: {browser_name}")
        local_state = user_data_path / "Local State"
        key = _get_chromium_key(local_state)
        if not key:
            continue
            
        # Standard profiles list to scan
        profiles = ["Default", "Profile 1", "Profile 2", "Profile 3", "Profile 4", "Profile 5", "Guest Profile"]
        # Scan profiles
        for profile in profiles:
            profile_path = user_data_path / profile
            if not profile_path.exists():
                continue
                
            # Cookies SQLite paths can vary between versions (modern Chrome puts it under Network)
            cookie_paths = [
                profile_path / "Network" / "Cookies",
                profile_path / "Cookies"
            ]
            
            for cookie_path in cookie_paths:
                if cookie_path.exists():
                    logger.debug(f"Found cookies db at: {cookie_path}")
                    extracted, locked = _extract_cookies_from_db(cookie_path, key, domains)
                    if locked:
                        browser_locked = True
                    
                    # Group by target domains
                    for cookie in extracted:
                        for target in domains:
                            if target in cookie["domain"]:
                                # Avoid duplicates (prefer newer values from profile scans)
                                existing = [c for c in results[target] if c["name"] == cookie["name"]]
                                if not existing:
                                    results[target].append({
                                        "name": cookie["name"],
                                        "value": cookie["value"],
                                        "domain": cookie["domain"]
                                    })
                                else:
                                    # Update with fresh value
                                    existing[0]["value"] = cookie["value"]
                                    existing[0]["domain"] = cookie["domain"]
                                    
    return results, browser_locked


def sync_skyshowtime_from_browser_cookies(
    extracted: Optional[Dict[str, List[Dict[str, str]]]] = None,
) -> bool:
    """Write SkyShowtime cookies and exchange them for an OVP user token."""
    if extracted is None:
        if not browser_sync_supported():
            return False
        extracted, _browser_locked = get_browser_cookies(["skyshowtime.com", "skyott.com"])

    skyshowtime_cookies = extracted.get("skyshowtime.com", []) + extracted.get("skyott.com", [])
    if not skyshowtime_cookies:
        return False

    try:
        skyshowtime_dir = Path.home() / ".skyshowtime"
        skyshowtime_dir.mkdir(parents=True, exist_ok=True)
        cookie_file = skyshowtime_dir / "cookies.txt"

        lines = [
            "# Netscape HTTP Cookie File",
            "# This file is generated by Multi-Service Video Downloader.",
            "",
        ]
        for c in skyshowtime_cookies:
            domain = c.get("domain", ".skyshowtime.com")
            name = c["name"]
            value = c["value"]
            if value:
                lines.append(f"{domain}\tTRUE\t/\tTRUE\t0\t{name}\t{value}")

        cookie_file.write_text("\n".join(lines), encoding="utf-8")
        try:
            cookie_file.chmod(0o600)
        except OSError:
            pass

        from backend.core.services.skyshowtime.skyshowtime_auth import SkyShowtimeAuth

        auth = SkyShowtimeAuth()
        auth.login_with_cookies(str(cookie_file))
        logger.info("SkyShowtime browser session synced and authenticated successfully.")
        return True
    except Exception as e:
        logger.error("SkyShowtime auth post-sync login failed: %s", e)
        return False


def sync_all_supported_services() -> Dict[str, Any]:
    """Extract Chromium cookies; store tokens in keyring + central config (Windows only)."""
    domain_report = {d: False for d in DOMAIN_TO_SERVICE}

    if not browser_sync_supported():
        return {
            "services": _service_report(domain_report),
            "browser_locked": False,
            "unsupported_platform": True,
        }

    targets = list(DOMAIN_TO_SERVICE.keys())
    logger.info("Initializing Browser Auto-Sync sequence...")

    extracted, browser_locked = get_browser_cookies(targets)

    from backend.credentials_store import set_secret
    from backend.config import config

    rts_cookies = extracted.get("rtsplaneta.rs", [])
    if rts_cookies:
        cookie_dict = {c["name"]: c["value"] for c in rts_cookies if c["value"]}
        rts_token = next(
            (
                c["value"]
                for c in rts_cookies
                if c["name"] in ("rts_token", "token", "secure_streaming_token")
            ),
            "",
        ) or cookie_dict.get("token") or cookie_dict.get("secure_streaming_token", "")
        if rts_token:
            try:
                set_secret("rtsplaneta", "token", rts_token)
                set_secret("rtsplaneta", "secure_streaming_token", rts_token)
                email = (cookie_dict.get("email") or cookie_dict.get("username") or "").strip()
                if email:
                    config.update_credentials("rtsplaneta", {"email": email})
                try:
                    from backend.core.services.rtsplaneta.rtsplaneta_auth import RTSPlanetaConfig

                    cfg = RTSPlanetaConfig()
                    if email:
                        cfg.config["username"] = email
                    cfg.config.pop("token", None)
                    cfg.save()
                except Exception as exc:
                    logger.debug("RTS native config sync skipped: %s", exc)
                domain_report["rtsplaneta.rs"] = True
                logger.info("RTS Planeta session token synced (keyring).")
            except Exception as e:
                logger.error("Failed to store RTS token: %s", e)

    eon_cookies = extracted.get("eon.tv", [])
    if eon_cookies:
        cookie_dict = {c["name"]: c["value"] for c in eon_cookies if c["value"]}
        if cookie_dict:
            try:
                eon_cfg_path = Path.home() / ".eon" / "config.json"
                eon_cfg_path.parent.mkdir(parents=True, exist_ok=True)
                with open(eon_cfg_path, "w", encoding="utf-8") as f:
                    json.dump({"cookies": cookie_dict}, f, indent=2)
                try:
                    eon_cfg_path.chmod(0o600)
                except OSError:
                    pass
                domain_report["eon.tv"] = True
                logger.info("EON TV browser cookies saved (device credentials still required).")
            except Exception as e:
                logger.error("Failed to write EON cookie cache: %s", e)

    # Voyo RS
    voyo_rs_cookies = extracted.get("voyo.rs", [])
    # Voyo HR
    voyo_hr_cookies = extracted.get("voyo.hr", []) or extracted.get("voyo.rtl.hr", [])

    voyo_token = None
    voyo_variant = None
    target_domain = None

    if voyo_hr_cookies:
        cookie_dict = {c["name"]: c["value"] for c in voyo_hr_cookies if c["value"]}
        voyo_token = cookie_dict.get("token") or cookie_dict.get("s")
        if voyo_token:
            voyo_variant = "hr"
            target_domain = "voyo.hr"
    
    if not voyo_token and voyo_rs_cookies:
        cookie_dict = {c["name"]: c["value"] for c in voyo_rs_cookies if c["value"]}
        voyo_token = cookie_dict.get("token") or cookie_dict.get("s")
        if voyo_token:
            voyo_variant = "rs"
            target_domain = "voyo.rs"

    if voyo_token:
        try:
            set_secret("voyo", "token", voyo_token)
            # Update variant in app config and VoyoConfig
            config.update_credentials("voyo", {"variant": voyo_variant})
            try:
                from backend.core.services.voyo.auth import VoyoConfig as _VoyoConfig
                vc = _VoyoConfig()
                # Set dummy email or keep existing to store variant in ~/.voyo/config.json
                email, _, _ = vc.get_credentials()
                vc.set_credentials(email, "", variant=voyo_variant)
            except Exception:
                pass

            try:
                from backend.services.voyo_adapter import _VOYO_CACHE
                import time

                _VOYO_CACHE["token"] = voyo_token
                _VOYO_CACHE["variant"] = voyo_variant
                _VOYO_CACHE["last_check"] = time.time()
                _VOYO_CACHE["authenticated"] = True
            except Exception:
                pass
            if target_domain:
                domain_report[target_domain] = True
                if target_domain == "voyo.hr" and "voyo.rtl.hr" in extracted:
                    domain_report["voyo.rtl.hr"] = True
            logger.info(f"Voyo {voyo_variant.upper()} session token auto-synced (keyring).")
        except Exception as e:
            logger.error("Failed to store Voyo token: %s", e)

    hrti_cookies = extracted.get("hrti.hrt.hr", [])
    if hrti_cookies:
        cookie_dict = {c["name"]: c["value"] for c in hrti_cookies if c["value"]}
        hrti_token = cookie_dict.get("token") or cookie_dict.get("Authorization")
        if hrti_token:
            try:
                set_secret("hrti", "token", hrti_token.replace("Client ", "").strip())
                domain_report["hrti.hrt.hr"] = True
                logger.info("HRTi session token auto-synced (keyring).")
            except Exception as e:
                logger.error("Failed to store HRTi token: %s", e)

    sky_ok = sync_skyshowtime_from_browser_cookies(extracted)
    if sky_ok:
        domain_report["skyshowtime.com"] = True
        domain_report["skyott.com"] = True

    return {
        "services": _service_report(domain_report),
        "domains": domain_report,
        "browser_locked": browser_locked,
        "unsupported_platform": False,
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    print("Testing browser cookies extraction module...")
    report = sync_all_supported_services()
    print("Sync Report:", report)
