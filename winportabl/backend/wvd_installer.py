"""
Install and manage device.wvd (Widevine CDM) without manual path editing.
"""
from __future__ import annotations

import base64
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CANONICAL_WVD = Path.home() / ".videodownload" / "device.wvd"
MIN_WVD_SIZE = 100
MAX_WVD_SIZE = 102400


def verify_wvd_bytes(data: bytes) -> Optional[str]:
    if len(data) < MIN_WVD_SIZE or len(data) > MAX_WVD_SIZE:
        return f"Veličina mora biti između {MIN_WVD_SIZE} i {MAX_WVD_SIZE} bajtova."
    if data[:3] not in (b"WVD", b"\x08\x01"):
        return "Fajl nije prepoznat kao WVD (očekivan magic WVD ili protobuf header)."
    try:
        from pywidevine.device import Device
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wvd", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            Device.load(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    except Exception as exc:
        return f"pywidevine ne može učitati WVD: {exc}"
    return None


def verify_wvd_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return "Fajl ne postoji."
    try:
        data = path.read_bytes()
    except OSError as exc:
        return str(exc)
    return verify_wvd_bytes(data)


def discover_wvd_files() -> List[Dict[str, Any]]:
    """Find valid .wvd files in known locations (newest first)."""
    from backend.services.drm_manager import drm_manager

    seen: set[str] = set()
    found: List[Dict[str, Any]] = []

    def add(path: Path):
        key = str(path.resolve())
        if key in seen:
            return
        err = verify_wvd_file(path)
        if err:
            return
        seen.add(key)
        try:
            st = path.stat()
            found.append(
                {
                    "path": key,
                    "size": st.st_size,
                    "modified": st.st_mtime,
                    "is_canonical": key == str(CANONICAL_WVD.resolve()),
                }
            )
        except OSError:
            pass

    current = drm_manager.wvd_path
    if current:
        add(Path(current))

    search = drm_manager._search_wvd()
    if search:
        add(search)

    from backend.config import PROJECT_ROOT, config

    extra_dirs = [
        Path(config.get_binary_path("device_wvd")).parent,
        PROJECT_ROOT,
        PROJECT_ROOT / "binaries",
        PROJECT_ROOT / "cdm",
        Path.home() / ".wvd",
        Path.home() / ".videodownload",
        Path.home() / ".hrti",
        Path.home() / ".rtsplaneta",
        Path.cwd(),
    ]
    for d in extra_dirs:
        if not d or not d.exists():
            continue
        candidates = [d / "device.wvd"] if d.is_dir() else [d]
        for c in candidates:
            if c.is_file():
                add(c)
        if d.is_dir():
            for wvd in d.glob("*.wvd"):
                add(wvd)

    found.sort(key=lambda x: x["modified"], reverse=True)
    return found


def install_wvd_bytes(data: bytes, *, reload_drm: bool = True) -> Dict[str, Any]:
    err = verify_wvd_bytes(data)
    if err:
        return {"success": False, "error": err}

    CANONICAL_WVD.parent.mkdir(parents=True, exist_ok=True)
    CANONICAL_WVD.write_bytes(data)
    try:
        CANONICAL_WVD.chmod(0o600)
    except OSError:
        pass

    from backend.config import config

    config.update_binary_path("device_wvd", str(CANONICAL_WVD))

    metadata: Dict[str, Any] = {}
    if reload_drm:
        from backend.services.drm_manager import drm_manager

        drm_manager.reload()
        metadata = drm_manager.wvd_metadata

    return {
        "success": True,
        "path": str(CANONICAL_WVD),
        "size": len(data),
        "wvd_metadata": metadata,
        "message": f"device.wvd instaliran u {CANONICAL_WVD}",
    }


def install_wvd_from_path(source: Path, *, reload_drm: bool = True) -> Dict[str, Any]:
    err = verify_wvd_file(source)
    if err:
        return {"success": False, "error": err}
    return install_wvd_bytes(source.read_bytes(), reload_drm=reload_drm)


def install_wvd_from_base64(b64_text: str, *, reload_drm: bool = True) -> Dict[str, Any]:
    raw = b64_text.strip()
    if raw.startswith("data:"):
        raw = raw.split(",", 1)[-1]
    raw = "".join(raw.split())
    try:
        data = base64.b64decode(raw, validate=False)
    except Exception as exc:
        return {"success": False, "error": f"Neispravan base64: {exc}"}
    return install_wvd_bytes(data, reload_drm=reload_drm)


def auto_install_wvd(*, reload_drm: bool = True) -> Dict[str, Any]:
    """Copy newest discovered WVD to canonical location."""
    candidates = discover_wvd_files()
    if not candidates:
        return {
            "success": False,
            "error": "Nije pronađen nijedan validan .wvd fajl. Stavite device.wvd u root projekta ili ~/.wvd/",
        }
    best = candidates[0]
    if best.get("is_canonical"):
        from backend.services.drm_manager import drm_manager

        if reload_drm:
            drm_manager.reload()
        return {
            "success": True,
            "path": best["path"],
            "message": "Kanonski device.wvd već postoji.",
            "wvd_metadata": drm_manager.wvd_metadata,
            "source": best["path"],
        }
    return {
        **install_wvd_from_path(Path(best["path"]), reload_drm=reload_drm),
        "source": best["path"],
    }
