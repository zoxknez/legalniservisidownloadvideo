from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.queue_manager import queue_manager
from backend.services.ytdlp_adapter import YtdlpAdapter
from backend.services.ytdlp_common import cookies_file_configured, get_ytdlp_cookies_path

router = APIRouter()


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
    data = await file.read()
    if not data or len(data) < 10:
        raise HTTPException(status_code=400, detail="Fajl kolačića je prazan ili neispravan.")
    path = get_ytdlp_cookies_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"success": True, "configured": True, "path": str(path)}


@router.delete("/cookies")
async def ytdlp_delete_cookies():
    path = get_ytdlp_cookies_path()
    if path.is_file():
        path.unlink()
    return {"success": True, "configured": False}


@router.post("/download")
async def ytdlp_download(req: YtdlpDownloadRequest):
    url = req.url.strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL mora počinjati sa http:// ili https://")

    params = req.model_dump()
    params["url"] = url
    if cookies_file_configured():
        params["cookies_file"] = str(get_ytdlp_cookies_path())

    try:
        cmd, title, metadata = YtdlpAdapter.prepare_download(params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    task_id = await queue_manager.add_download("ytdlp", title, cmd, metadata=metadata)
    return {"success": True, "task_id": task_id}
