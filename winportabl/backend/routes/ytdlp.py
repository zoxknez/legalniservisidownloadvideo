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
    hardsub: bool = False
    
    cookies_browser: Optional[str] = None
    impersonate_browser: bool = False
    proxy: Optional[str] = None
    geo_bypass: bool = False
    embed_thumbnail: bool = False
    embed_metadata: bool = False
    limit_rate: Optional[str] = None
    
    sponsorblock_mode: str = "remove"  # "remove", "mark", "disabled"
    split_chapters: bool = False
    download_playlist: bool = False
    playlist_items: Optional[str] = None


@router.post("/download")
async def ytdlp_download(req: YtdlpDownloadRequest):
    url = req.url.strip()
    output_dir = config.get_output_dir()

    # tv_embedded + ios ne zahtijevaju PO Token i daju pun pristup DASH formatima (4K/8K)
    # android je blokiran SABR eksperimentom, mweb zahtijeva GVS PO Token
    cmd = [
        "python", "-m", "yt_dlp", url,
        "--extractor-args", "youtube:player_client=tv_embedded,ios",
        "--retries", "5",
        "--fragment-retries", "5",
        "--retry-sleep", "exp=1:4",
    ]
    if not req.download_playlist:
        cmd.append("--no-playlist")
    elif req.playlist_items and req.playlist_items.strip():
        cmd.extend(["--playlist-items", req.playlist_items.strip()])

    name_tmpl = config.get_ytdlp_name_template() or "%(title)s.%(ext)s"
    if req.audio_only:
        if "%(ext)s" in name_tmpl:
            name_tmpl = name_tmpl.replace("%(ext)s", "mp3")
        else:
            if not name_tmpl.endswith(".mp3"):
                name_tmpl = name_tmpl + ".mp3"
        output_tmpl = os.path.join(output_dir, name_tmpl)
        cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "0", "-o", output_tmpl])
    else:
        output_tmpl = os.path.join(output_dir, name_tmpl)
        _res_match = re.search(r"(\d+)p", req.resolution)
        if _res_match:
            res_val = _res_match.group(1)
            # Format spec logika:
            # 1. Tražena rezolucija sa AVC+AAC (kompatibilni MP4 kodeci)
            # 2. Tražena rezolucija sa bilo kojim kodecima
            # 3. Bila koja rezolucija <= tražene, sa bilo kojim kodecima
            # 4. Apsolutni fallback — uvijek bestvideo+bestaudio (NIKAD goli 'best' koji je najlošiji)
            format_spec = (
                f"bestvideo[height={res_val}][vcodec^=avc]+bestaudio[acodec^=mp4a]/"
                f"bestvideo[height={res_val}]+bestaudio[ext=m4a]/"
                f"bestvideo[height={res_val}]+bestaudio/"
                f"bestvideo[height<={res_val}][vcodec^=avc]+bestaudio[acodec^=mp4a]/"
                f"bestvideo[height<={res_val}]+bestaudio/"
                f"bestvideo+bestaudio/best"
            )
        else:
            format_spec = "bestvideo+bestaudio/best"
        cmd.extend(["-f", format_spec, "-o", output_tmpl, "--merge-output-format", "mp4"])

    if req.subs:
        cmd.extend([
            "--write-subs", "--write-auto-subs",
            "--sub-langs", req.subs,
            "--embed-subs",
            "--sleep-subtitles", "2",   # anti-429: pauza između subtitle req.
            "--ignore-errors",           # nastavi download i ako sub greška
        ])
        if req.hardsub:
            cmd.extend(["--convert-subs", "srt"])
            
    if req.sponsorblock_mode == "remove":
        cmd.extend(["--sponsorblock-remove", "all"])
    elif req.sponsorblock_mode == "mark":
        cmd.extend(["--sponsorblock-mark", "all"])

    if req.split_chapters:
        cmd.append("--split-chapters")
        # Define chapter-specific naming template to prevent overwrites
        chapter_tmpl = os.path.join(output_dir, "%(title)s - %(section_number)02d - %(section_title)s.%(ext)s")
        cmd.extend(["-o", f"chapter:{chapter_tmpl}"])

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
    task_id = await queue_manager.add_download(
        "ytdlp",
        title,
        cmd,
        metadata={"hardsub": True} if req.hardsub else None
    )
    return {"success": True, "task_id": task_id}
