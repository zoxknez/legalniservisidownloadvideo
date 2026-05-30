import os
import json
import base64
import sqlite3
import shutil
import ctypes
import tempfile
import logging
from ctypes import wintypes
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from Crypto.Cipher import AES

logger = logging.getLogger("BrowserCookies")

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
        # On Windows, command interpreter 'copy' handles open/locked files gracefully with shared read flags
        import subprocess
        cmd = f'copy /y "{db_path}" "{temp_db_path}"'
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
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
                                        "value": cookie["value"]
                                    })
                                else:
                                    # Update with fresh value
                                    existing[0]["value"] = cookie["value"]
                                    
    return results, browser_locked

def sync_all_supported_services() -> Dict[str, Any]:
    """
    Grabs session cookies for premium video services and automatically syncs them
    into local configuration files (~/.rtsplaneta/config.json, ~/.voyo/config.json, etc.)
    """
    targets = ["rtsplaneta.rs", "eon.tv", "voyo.rs", "hrti.hrt.hr"]
    logger.info("Initializing Browser Auto-Sync sequence...")
    
    extracted, browser_locked = get_browser_cookies(targets)
    sync_report = {t: False for t in targets}
    
    # 1. RTS Planeta
    rts_cookies = extracted.get("rtsplaneta.rs", [])
    rts_token = next((c["value"] for c in rts_cookies if c["name"] == "rts_token" or c["name"] == "token"), "")
    # Look for session cookies
    if rts_cookies:
        # RTS usually uses custom tokens or session headers. We will write them directly
        # to RTS Planeta configuration folder.
        rts_cfg_path = Path.home() / ".rtsplaneta" / "config.json"
        rts_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build cookies dict
        cookie_dict = {c["name"]: c["value"] for c in rts_cookies if c["value"]}
        if cookie_dict:
            try:
                # Save cookies formatted as cookie string or dict
                with open(rts_cfg_path, "w") as f:
                    json.dump({"cookies": cookie_dict, "token": rts_token or cookie_dict.get("token", "")}, f, indent=2)
                sync_report["rtsplaneta.rs"] = True
                logger.info("✓ RTS Planeta cookies auto-synced successfully!")
            except Exception as e:
                logger.error(f"Failed to write RTS Planeta config: {e}")

    # 2. EON TV
    eon_cookies = extracted.get("eon.tv", [])
    if eon_cookies:
        eon_cfg_path = Path.home() / ".eon" / "config.json"
        eon_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cookie_dict = {c["name"]: c["value"] for c in eon_cookies if c["value"]}
        if cookie_dict:
            try:
                with open(eon_cfg_path, "w") as f:
                    json.dump({"cookies": cookie_dict}, f, indent=2)
                sync_report["eon.tv"] = True
                logger.info("✓ EON TV cookies auto-synced successfully!")
            except Exception as e:
                logger.error(f"Failed to write EON config: {e}")

    # 3. Voyo RS
    voyo_cookies = extracted.get("voyo.rs", [])
    if voyo_cookies:
        cookie_dict = {c["name"]: c["value"] for c in voyo_cookies if c["value"]}
        voyo_token = cookie_dict.get("token") or cookie_dict.get("s")
        if voyo_token:
            try:
                from backend.credentials_store import set_secret

                set_secret("voyo", "token", voyo_token)
                sync_report["voyo.rs"] = True
                logger.info("✓ Voyo RS session token auto-synced (keyring)!")
            except Exception as e:
                logger.error(f"Failed to store Voyo token: {e}")

    # 4. HRTi
    hrti_cookies = extracted.get("hrti.hrt.hr", [])
    if hrti_cookies:
        cookie_dict = {c["name"]: c["value"] for c in hrti_cookies if c["value"]}
        hrti_token = cookie_dict.get("token") or cookie_dict.get("Authorization")
        if hrti_token:
            try:
                from backend.credentials_store import set_secret

                set_secret("hrti", "token", hrti_token.replace("Client ", ""))
                sync_report["hrti.hrt.hr"] = True
                logger.info("✓ HRTi session token auto-synced (keyring)!")
            except Exception as e:
                logger.error(f"Failed to store HRTi token: {e}")

    return {"services": sync_report, "browser_locked": browser_locked}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    print("Testing browser cookies extraction module...")
    report = sync_all_supported_services()
    print("Sync Report:", report)
