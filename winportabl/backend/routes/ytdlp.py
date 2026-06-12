import re
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.queue_manager import queue_manager
from backend.services.ytdlp_adapter import YtdlpAdapter
from backend.services.ytdlp_common import cookies_file_configured, get_ytdlp_cookies_path

router = APIRouter()

_MAX_COOKIE_FILE_BYTES = 2 * 1024 * 1024
_MAX_URL_LEN = 4096
_MAX_FORMAT_SPEC_LEN = 512
_MAX_EXTRACTOR_ARGS_LEN = 512
_MAX_PROXY_LEN = 300
_MAX_VIDEO_TITLE_LEN = 200
_MAX_PLAYLIST_ITEMS_LEN = 100
_MAX_SUBS_LEN = 120
_VALID_BROWSERS = frozenset({"chrome", "edge", "firefox", "brave"})
_VALID_SPONSORBLOCK = frozenset({"remove", "mark", "disabled"})
_VALID_PROXY_SCHEMES = frozenset({"http", "https", "socks4", "socks5", "socks5h"})
_LIMIT_RATE_RE = re.compile(r"^\d+(?:\.\d+)?[KMGTP]?$", re.I)
_PLAYLIST_ITEMS_RE = re.compile(r"^[0-9,\-\s]+$")
_SUBS_RE = re.compile(r"^(?:all|[A-Za-z0-9_.*-]+(?:,[A-Za-z0-9_.*-]+)*)$", re.I)
_EXTRACTOR_ARGS_RE = re.compile(r"^[A-Za-z0-9_:.=,;+\-\s]+$")


class YtdlpDownloadRequest(BaseModel):
    url: str
    resolution: str = "1080p"
    subs: str = ""
    audio_only: bool = False
    use_aria2: bool = False
    hardsub: bool = False
    video_title: Optional[str] = None

    cookies_browser: Optional[str] = None
    impersonate_browser: bool = False
    proxy: Optional[str] = None
    geo_bypass: bool = False
    embed_thumbnail: bool = False
    embed_metadata: bool = False
    limit_rate: Optional[str] = None
    format_spec: Optional[str] = None
    extractor_args: Optional[str] = None

    sponsorblock_mode: str = "disabled"  # "remove", "mark", "disabled"
    split_chapters: bool = False
    download_playlist: bool = False
    playlist_items: Optional[str] = None


def _clean_optional_text(value: Optional[str], *, max_len: int, label: str) -> Optional[str]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > max_len:
        raise HTTPException(status_code=400, detail=f"{label} je predugačak.")
    if any(ord(ch) < 32 for ch in text):
        raise HTTPException(status_code=400, detail=f"{label} ne sme sadržati kontrolne karaktere.")
    return text


def _validate_netscape_cookies(data: bytes) -> None:
    if b"\x00" in data:
        raise HTTPException(status_code=400, detail="Fajl kolačića nije tekstualni Netscape cookies.txt fajl.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Fajl kolačića mora biti UTF-8 tekst.") from exc

    has_cookie = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
            continue
        parts = raw_line.split("\t")
        if len(parts) != 7:
            raise HTTPException(status_code=400, detail="Fajl kolačića mora biti u Netscape cookies.txt formatu.")
        domain, include_subdomains, path, secure, expires, name, value = parts
        if include_subdomains.upper() not in {"TRUE", "FALSE"} or secure.upper() not in {"TRUE", "FALSE"}:
            raise HTTPException(status_code=400, detail="Fajl kolačića ima neispravne TRUE/FALSE vrednosti.")
        if not domain or not path or not name:
            raise HTTPException(status_code=400, detail="Fajl kolačića sadrži nepotpun cookie zapis.")
        try:
            int(expires)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Fajl kolačića ima neispravan expiry zapis.") from exc
        if value == "":
            raise HTTPException(status_code=400, detail="Fajl kolačića sadrži prazan cookie token.")
        has_cookie = True

    if not has_cookie:
        raise HTTPException(status_code=400, detail="Fajl kolačića ne sadrži nijedan cookie zapis.")


def _validate_download_request(req: YtdlpDownloadRequest) -> dict:
    url = req.url.strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL mora počinjati sa http:// ili https://")
    if len(url) > _MAX_URL_LEN:
        raise HTTPException(status_code=400, detail="URL je predugačak.")

    params = req.model_dump()
    params["url"] = url

    sponsorblock_mode = (req.sponsorblock_mode or "disabled").strip().lower()
    if sponsorblock_mode not in _VALID_SPONSORBLOCK:
        raise HTTPException(status_code=400, detail="SponsorBlock režim mora biti remove, mark ili disabled.")
    params["sponsorblock_mode"] = sponsorblock_mode

    cookies_browser = _clean_optional_text(req.cookies_browser, max_len=30, label="Browser za cookies")
    if cookies_browser:
        cookies_browser = cookies_browser.lower()
        if cookies_browser not in _VALID_BROWSERS:
            raise HTTPException(status_code=400, detail="Browser za cookies mora biti chrome, edge, firefox ili brave.")
    params["cookies_browser"] = cookies_browser

    proxy = _clean_optional_text(req.proxy, max_len=_MAX_PROXY_LEN, label="Proxy URL")
    if proxy:
        parsed = urlparse(proxy)
        if parsed.scheme.lower() not in _VALID_PROXY_SCHEMES or not parsed.netloc:
            raise HTTPException(status_code=400, detail="Proxy mora biti validan http/https/socks URL.")
    params["proxy"] = proxy

    limit_rate = _clean_optional_text(req.limit_rate, max_len=20, label="Limit brzine")
    if limit_rate and not _LIMIT_RATE_RE.match(limit_rate):
        raise HTTPException(status_code=400, detail="Limit brzine mora biti u formatu npr. 50K, 5M ili 1G.")
    params["limit_rate"] = limit_rate

    playlist_items = _clean_optional_text(req.playlist_items, max_len=_MAX_PLAYLIST_ITEMS_LEN, label="Opseg plejliste")
    if playlist_items and not _PLAYLIST_ITEMS_RE.match(playlist_items):
        raise HTTPException(status_code=400, detail="Opseg plejliste sme sadržati samo brojeve, zareze i crtice.")
    params["playlist_items"] = playlist_items

    subs = req.subs.strip()
    if subs and subs.lower() != "all":
        subs = ",".join(part.strip() for part in subs.split(",") if part.strip())
    if len(subs) > _MAX_SUBS_LEN:
        raise HTTPException(status_code=400, detail="Lista titlova je predugačka.")
    if subs and (any(ord(ch) < 32 for ch in subs) or not _SUBS_RE.match(subs)):
        raise HTTPException(status_code=400, detail="Titlovi moraju biti 'all' ili lista oznaka jezika odvojena zarezom.")
    params["subs"] = subs

    params["format_spec"] = _clean_optional_text(req.format_spec, max_len=_MAX_FORMAT_SPEC_LEN, label="Napredni format")

    extractor_args = _clean_optional_text(req.extractor_args, max_len=_MAX_EXTRACTOR_ARGS_LEN, label="Extractor argumenti")
    if extractor_args and not _EXTRACTOR_ARGS_RE.match(extractor_args):
        raise HTTPException(status_code=400, detail="Extractor argumenti sadrže nedozvoljene karaktere.")
    params["extractor_args"] = extractor_args

    params["video_title"] = _clean_optional_text(req.video_title, max_len=_MAX_VIDEO_TITLE_LEN, label="Naziv videa")
    return params


@router.get("/cookies/status")
async def ytdlp_cookies_status():
    path = get_ytdlp_cookies_path()
    return {
        "success": True,
        "configured": cookies_file_configured(),
        "path": str(path) if cookies_file_configured() else "",
    }


@router.post("/cookies")
async def ytdlp_upload_cookies(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Fajl kolačića je obavezan.")
    data = await file.read(_MAX_COOKIE_FILE_BYTES + 1)
    if not data or len(data) < 10:
        raise HTTPException(status_code=400, detail="Fajl kolačića je prazan ili neispravan.")
    if len(data) > _MAX_COOKIE_FILE_BYTES:
        raise HTTPException(status_code=400, detail="Fajl kolačića je prevelik (maksimum 2 MB).")
    _validate_netscape_cookies(data)
    path = get_ytdlp_cookies_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return {"success": True, "configured": True, "path": str(path)}


@router.delete("/cookies")
async def ytdlp_delete_cookies():
    path = get_ytdlp_cookies_path()
    if path.is_file():
        path.unlink()
    return {"success": True, "configured": False}


@router.post("/download")
async def ytdlp_download(req: YtdlpDownloadRequest):
    params = _validate_download_request(req)
    if cookies_file_configured():
        params["cookies_file"] = str(get_ytdlp_cookies_path())

    try:
        cmd, title, metadata = YtdlpAdapter.prepare_download(params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    task_id = await queue_manager.add_download("ytdlp", title, cmd, metadata=metadata)
    return {"success": True, "task_id": task_id}
