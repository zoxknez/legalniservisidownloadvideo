import ipaddress
import os
import re
import tempfile
from urllib.parse import urlparse
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.queue_manager import queue_manager
from backend.services.skyshowtime_adapter import SkyShowtimeAdapter

router = APIRouter()

MAX_COOKIE_TEXT_BYTES = 2 * 1024 * 1024
MAX_COOKIE_DICT_ITEMS = 500
MAX_COOKIE_VALUE_BYTES = 8192
MAX_EPISODE_REFS = 500
MAX_URL_LEN = 4096
MAX_TOKEN_BYTES = 16 * 1024
SKY_HOSTS = {"skyshowtime.com", "www.skyshowtime.com"}
EPISODE_REF_RE = re.compile(r"^[1-9]\d{0,2}:[1-9]\d{0,3}$")
AUDIO_LANG_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z]{2,4})?$")


def _write_temp_text(text: str, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def _clean_audio_lang(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 12 or not AUDIO_LANG_RE.match(cleaned):
        raise HTTPException(status_code=400, detail="Audio jezik mora biti u formatu en, sr, hr ili en-US.")
    return cleaned


def _validate_cookies_text(text: str) -> str:
    data = text.strip()
    if not data:
        raise HTTPException(status_code=400, detail="cookies.txt ne sme biti prazan.")
    if len(data.encode("utf-8")) > MAX_COOKIE_TEXT_BYTES:
        raise HTTPException(status_code=413, detail="cookies.txt je prevelik.")
    lines = [line for line in data.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    has_cookie_row = any(len(line.split("\t")) >= 7 for line in lines)
    has_sky_cookie = any("skyshowtime" in line.lower() or "skyott" in line.lower() for line in lines)
    if not has_cookie_row or not has_sky_cookie:
        raise HTTPException(status_code=400, detail="Fajl mora biti Netscape cookies.txt za SkyShowtime.")
    return data + "\n"


def _validate_cookie_dict(cookies: Dict[str, str]) -> Dict[str, str]:
    if len(cookies) > MAX_COOKIE_DICT_ITEMS:
        raise HTTPException(status_code=413, detail="Previse kolacica je poslato.")
    cleaned: Dict[str, str] = {}
    for name, value in cookies.items():
        key = str(name).strip()
        val = str(value or "").strip()
        if not key or not val:
            continue
        if len(key) > 256 or len(val.encode("utf-8")) > MAX_COOKIE_VALUE_BYTES:
            raise HTTPException(status_code=400, detail="Kolacic ima neispravnu velicinu.")
        cleaned[key] = val
    if not cleaned:
        raise HTTPException(status_code=400, detail="Nema validnih kolacica za prijavu.")
    return cleaned


def _validate_sky_url(value: str) -> str:
    url = value.strip()
    if not url:
        raise HTTPException(status_code=400, detail="SkyShowtime URL je obavezan.")
    if len(url) > MAX_URL_LEN:
        raise HTTPException(status_code=414, detail="SkyShowtime URL je predugacak.")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in SKY_HOSTS:
        raise HTTPException(status_code=400, detail="Unesite validan https://www.skyshowtime.com URL.")
    if not re.match(r"^/watch/asset/(movies|tv|kids)/[^?#]+$", parsed.path):
        raise HTTPException(status_code=400, detail="SkyShowtime URL mora voditi na film ili seriju.")
    return url


def _validate_public_https_url(value: str, label: str) -> str:
    url = value.strip()
    if not url:
        raise HTTPException(status_code=400, detail=f"{label} je obavezan.")
    if len(url) > MAX_URL_LEN:
        raise HTTPException(status_code=414, detail=f"{label} je predugacak.")
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().lower()
    if parsed.scheme != "https" or not host:
        raise HTTPException(status_code=400, detail=f"{label} mora biti javni HTTPS URL.")
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise HTTPException(status_code=400, detail=f"{label} ne sme pokazivati na lokalnu mrezu.")
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(status_code=400, detail=f"{label} ne sme pokazivati na lokalnu mrezu.")
    except ValueError:
        if "." not in host:
            raise HTTPException(status_code=400, detail=f"{label} mora imati javni domen.")
    return url


def _clean_episode_refs(refs: List[str]) -> List[str]:
    if len(refs) > MAX_EPISODE_REFS:
        raise HTTPException(status_code=413, detail=f"Maksimalno {MAX_EPISODE_REFS} epizoda po batch poslu.")
    cleaned: List[str] = []
    seen = set()
    for raw in refs:
        ref = str(raw).strip()
        if not EPISODE_REF_RE.match(ref):
            raise HTTPException(status_code=400, detail="Episode ref mora biti u formatu sezona:epizoda.")
        if ref not in seen:
            cleaned.append(ref)
            seen.add(ref)
    return cleaned


class SkyLoginRequest(BaseModel):
    cookies_text: Optional[str] = Field(default=None, max_length=MAX_COOKIE_TEXT_BYTES)
    cookies: Optional[Dict[str, str]] = None


@router.post("/login")
async def skyshowtime_login(req: SkyLoginRequest):
    if req.cookies_text:
        temp_path = _write_temp_text(_validate_cookies_text(req.cookies_text), ".txt")
        cmd = SkyShowtimeAdapter.make_login_cmd(cookie_file=temp_path)
        title = "SkyShowtime Login (cookies.txt)"
    elif req.cookies:
        cmd = SkyShowtimeAdapter.make_login_cmd(cookies=_validate_cookie_dict(req.cookies))
        title = "SkyShowtime Login (Auto-sync)"
    else:
        raise HTTPException(status_code=400, detail="Nedostaju podaci za prijavu (kolačići).")

    task_id = await queue_manager.add_download("skyshowtime", title, cmd)
    return {"success": True, "task_id": task_id}


@router.post("/sync-browser")
async def skyshowtime_sync_browser():
    from backend.services.browser_cookies import browser_sync_supported, sync_skyshowtime_from_browser_cookies

    if not browser_sync_supported():
        raise HTTPException(
            status_code=400,
            detail=(
                "Automatska sinhronizacija iz pretraživača je dostupna samo na Windows-u "
                "(Chrome/Edge/Brave + DPAPI)."
            ),
        )

    synced = sync_skyshowtime_from_browser_cookies()
    status = SkyShowtimeAdapter.get_auth_status()
    if synced and status.get("authenticated"):
        return {
            "success": True,
            "authenticated": True,
            "message": "SkyShowtime sesija je uspešno sinhronizovana iz pretraživača.",
            **status,
        }

    raise HTTPException(
        status_code=400,
        detail=(
            "Nisu pronađeni SkyShowtime kolačići. Ulogujte se na skyshowtime.com u Chrome, "
            "Edge ili Brave pretraživaču i zatvorite ga pre ponovnog pokušaja."
        ),
    )


@router.get("/status")
def skyshowtime_status():
    return SkyShowtimeAdapter.get_auth_status()


@router.get("/resolve")
def skyshowtime_resolve(target: str = ""):
    if not target.strip():
        raise HTTPException(status_code=400, detail="Unesite URL serije.")
    try:
        result = SkyShowtimeAdapter.resolve_to_series(target.strip())
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/series")
def skyshowtime_series(target: str = ""):
    if not target.strip():
        raise HTTPException(status_code=400, detail="Unesite URL serije.")
    result = SkyShowtimeAdapter.get_series_info(target.strip())
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Serija nije pronađena."))
    return result


class SkyDownloadRequest(BaseModel):
    url: str = Field(min_length=1, max_length=MAX_URL_LEN)
    season: Optional[int] = Field(default=None, ge=1, le=999)
    start_ep: int = Field(default=1, ge=1, le=9999)
    end_ep: int = Field(default=999, ge=1, le=9999)
    vcodec: Literal["H264", "H265"] = "H264"
    quality: Literal["SDR", "HDR10", "DV"] = "SDR"
    audio_lang: Optional[str] = Field(default=None, max_length=12)
    episode_refs: Optional[List[str]] = Field(default=None, max_length=MAX_EPISODE_REFS)


@router.post("/download")
async def skyshowtime_download(req: SkyDownloadRequest):
    url = _validate_sky_url(req.url)
    audio_lang = _clean_audio_lang(req.audio_lang)
    if req.end_ep < req.start_ep:
        raise HTTPException(status_code=400, detail="Zavrsna epizoda mora biti veca ili jednaka pocetnoj.")

    status = SkyShowtimeAdapter.get_auth_status()
    if not status.get("authenticated"):
        raise HTTPException(
            status_code=401,
            detail="Niste prijavljeni na SkyShowtime. Prvo se prijavite uvozom kolačića.",
        )

    if req.episode_refs:
        refs = _clean_episode_refs(req.episode_refs)
        cmd = SkyShowtimeAdapter.make_download_batch_cmd(
            url=url,
            episode_refs=refs,
            vcodec=req.vcodec,
            quality=req.quality,
            audio_lang=audio_lang,
        )
        title = f"SkyShowtime: {len(refs)} epizoda"
        task_id = await queue_manager.add_download("skyshowtime", title, cmd)
        return {"success": True, "queued": len(refs), "task_id": task_id}

    cmd = SkyShowtimeAdapter.make_download_cmd(
        url=url,
        season=req.season,
        start_ep=req.start_ep,
        end_ep=req.end_ep,
        vcodec=req.vcodec,
        quality=req.quality,
        audio_lang=audio_lang,
    )
    title = f"SkyShowtime: {url}"
    task_id = await queue_manager.add_download("skyshowtime", title, cmd)
    return {"success": True, "task_id": task_id}


class SkyDirectDownloadRequest(BaseModel):
    manifest_url: str = Field(min_length=10, max_length=MAX_URL_LEN)
    license_url: str = Field(min_length=10, max_length=MAX_URL_LEN)
    title: str = Field(default="", max_length=240)
    license_token: str = Field(default="", max_length=MAX_TOKEN_BYTES)
    vcodec: Literal["H264", "H265"] = "H264"
    quality: Literal["SDR", "HDR10", "DV"] = "SDR"
    audio_lang: Optional[str] = None


@router.post("/download-direct")
async def skyshowtime_download_direct(req: SkyDirectDownloadRequest):
    manifest_url = _validate_public_https_url(req.manifest_url, "MPD manifest URL")
    license_url = _validate_public_https_url(req.license_url, "Widevine license URL")
    audio_lang = _clean_audio_lang(req.audio_lang)
    license_token = req.license_token.strip()
    if len(license_token.encode("utf-8")) > MAX_TOKEN_BYTES:
        raise HTTPException(status_code=413, detail="License token je prevelik.")

    status = SkyShowtimeAdapter.get_auth_status()
    if not status.get("authenticated"):
        raise HTTPException(
            status_code=401,
            detail="Niste prijavljeni na SkyShowtime. Prvo se prijavite.",
        )
    cmd = SkyShowtimeAdapter.make_download_direct_cmd(
        manifest_url=manifest_url,
        license_url=license_url,
        title=req.title.strip(),
        license_token=license_token,
        vcodec=req.vcodec,
        quality=req.quality,
        audio_lang=audio_lang,
    )
    display_title = req.title.strip() if req.title.strip() else f"SkyShowtime Direct: {req.manifest_url[:40]}…"
    task_id = await queue_manager.add_download("skyshowtime", display_title, cmd)
    return {"success": True, "task_id": task_id}
