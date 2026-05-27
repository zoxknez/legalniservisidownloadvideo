import os
import sqlite3
import shutil
import tempfile
import base64
import json
import ctypes
import logging
from ctypes import wintypes
from pathlib import Path
from typing import Dict, Any, List, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

def decrypt_dpapi(encrypted_data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    in_blob = DATA_BLOB(len(encrypted_data), ctypes.cast(ctypes.create_string_buffer(encrypted_data), ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()
    
    success = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob)
    )
    if not success:
        raise OSError("DPAPI decryption failed.")
        
    decrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    return decrypted

def get_master_key(local_state_path: str) -> Optional[bytes]:
    if not os.path.exists(local_state_path):
        return None
    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)
        encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        # Strip DPAPI prefix (5 bytes)
        encrypted_key = encrypted_key[5:]
        return decrypt_dpapi(encrypted_key)
    except Exception as e:
        logger.error(f"Error reading master key from {local_state_path}: {e}")
        return None

def decrypt_cookie(encrypted_value: bytes, master_key: bytes) -> str:
    if not master_key:
        return ""
    try:
        if encrypted_value[:3] == b'v10' or encrypted_value[:3] == b'v11':
            iv = encrypted_value[3:15]
            ciphertext = encrypted_value[15:]
            aesgcm = AESGCM(master_key)
            decrypted = aesgcm.decrypt(iv, ciphertext, None)
            return decrypted.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Error decrypting cookie: {e}")
        return ""
    return ""

def copy_locked_file(src: str, dst: str) -> None:
    try:
        shutil.copyfile(src, dst)
    except OSError:
        # Fallback to low-level Windows API copy
        kernel32 = ctypes.windll.kernel32
        GENERIC_READ = 0x80000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        FILE_SHARE_DELETE = 0x00000004
        OPEN_EXISTING = 3
        FILE_ATTRIBUTE_NORMAL = 0x80
        INVALID_HANDLE_VALUE = -1

        handle = kernel32.CreateFileW(
            src,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None
        )
        if handle == INVALID_HANDLE_VALUE:
            raise OSError(f"Failed to open locked file: {src}")

        try:
            with open(dst, "wb") as f_out:
                buf = ctypes.create_string_buffer(1024 * 1024)
                bytes_read = wintypes.DWORD(0)
                while True:
                    res = kernel32.ReadFile(handle, buf, len(buf), ctypes.byref(bytes_read), None)
                    if not res or bytes_read.value == 0:
                        break
                    f_out.write(buf.raw[:bytes_read.value])
        finally:
            kernel32.CloseHandle(handle)