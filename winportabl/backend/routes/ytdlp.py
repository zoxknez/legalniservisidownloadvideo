import os
import re
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import config
from backend.queue_manager import queue_manager

router = APIRouter()


class YtdlpDownloadRequest(BaseModel):
    url: str
    resolution: str = "1080p"
    subs: str = ""
    audio_only: bool = False
    use_aria2: bool = False
    
    cookies_browser: Optional[str] = None
    impersonate_browser: bool = False
    proxy: Optional[str] = None
    geo_bypass: bool = False
    embed_thumbnail: bool = False
    embed_metadata: bool = False
    limit_rate: Optional[str] = None


@router.post("/download")
async def ytdlp_download(req: YtdlpDownloadRequest):
    url = req.url.strip()
    output_dir = config.get_output_dir()

    cmd = ["python", "-m", "yt_dlp", url, "--no-playlist"]

    if req.audio_only:
        output_tmpl = os.path.join(output_dir, "%(title)s.mp3")
        cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "0", "-o", output_tmpl])
    else:
        output_tmpl = os.path.join(output_dir, "%(title)s.%(ext)s")
        _res_match = re.search(r"(\d+)p", req.resolution)
        if _res_match:
            res_val = _res_match.group(1)
            format_spec = (
                f"bestvideo[height<={res_val}][vcodec^=avc]+bestaudio[acodec^=mp4a]/"
                f"bestvideo[height<={res_val}]+bestaudio/"
                f"best[height<={res_val}]/best"
            )
        else:
            format_spec = "bestvideo+bestaudio/best"
        cmd.extend(["-f", format_spec, "-o", output_tmpl, "--merge-output-format", "mp4"])

    if req.subs:
        cmd.extend(["--write-subs", "--write-auto-subs", "--sub-langs", req.subs, "--embed-subs"])
    cmd.extend(["--sponsorblock-remove", "all"])

    if req.use_aria2:
        aria2_status = config.check_binaries_status().get("aria2c", {})
        if aria2_status.get("found"):
            cmd.extend([
                "--external-downloader", aria2_status.get("path"),
                "--external-downloader-args", "aria2c:-j 16 -x 16 -s 16 -k 1M",
            ])

    # Advanced options
    if req.cookies_browser:
        cmd.extend(["--cookies-from-browser", req.cookies_browser])

    if req.impersonate_browser:
        cmd.extend(["--impersonate", "chrome"])

    if req.proxy and req.proxy.strip():
        cmd.extend(["--proxy", req.proxy.strip()])

    if req.geo_bypass:
        cmd.extend(["--geo-bypass"])

    if req.embed_thumbnail:
        cmd.extend(["--embed-thumbnail"])

    if req.embed_metadata:
        cmd.extend(["--embed-metadata", "--embed-chapters"])

    if req.limit_rate and req.limit_rate.strip():
        cmd.extend(["--limit-rate", req.limit_rate.strip()])

    domain = urlparse(url).netloc.replace("www.", "")
    title = f"Univerzalni ({domain}): {url[:40]}"
    task_id = await queue_manager.add_download("ytdlp", title, cmd)
    return {"success": True, "task_id": task_id}
