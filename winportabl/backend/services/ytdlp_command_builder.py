"""Build yt-dlp CLI argument lists for universal downloads."""
from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, List, Optional

from backend.config import config
from backend.services.output_files import _sanitize_title_fragment
from backend.services.ytdlp_common import (
    YTDLP_CLI_NETWORK_ARGS,
    cookies_file_configured,
    get_ytdlp_cookies_path,
)


def build_format_spec(resolution: str) -> str:
    res_match = re.search(r"(\d+)p", resolution or "")
    if res_match:
        res_val = res_match.group(1)
        return (
            f"bestvideo[height={res_val}][vcodec^=avc]+bestaudio[acodec^=mp4a]/"
            f"bestvideo[height={res_val}]+bestaudio[ext=m4a]/"
            f"bestvideo[height={res_val}]+bestaudio/"
            f"bestvideo[height<={res_val}][vcodec^=avc]+bestaudio[acodec^=mp4a]/"
            f"bestvideo[height<={res_val}]+bestaudio/"
            f"bestvideo+bestaudio/best"
        )
    return "bestvideo+bestaudio/best"


def build_ytdlp_cmd(params: Dict[str, Any]) -> List[str]:
    """Build full yt-dlp argv (including python -m yt_dlp prefix)."""
    url = (params.get("url") or "").strip()
    output_dir = params.get("output_dir") or config.get_output_dir()
    name_tmpl = params.get("name_template") or config.get_ytdlp_name_template() or "%(title)s.%(ext)s"

    cmd: List[str] = [sys.executable, "-m", "yt_dlp", url, *YTDLP_CLI_NETWORK_ARGS]

    if not params.get("download_playlist"):
        cmd.append("--no-playlist")
    elif params.get("playlist_items") and str(params["playlist_items"]).strip():
        cmd.extend(["--playlist-items", str(params["playlist_items"]).strip()])

    format_spec = (params.get("format_spec") or "").strip() or build_format_spec(
        params.get("resolution") or "1080p"
    )

    if params.get("audio_only"):
        audio_tmpl = name_tmpl
        if "%(ext)s" in audio_tmpl:
            audio_tmpl = audio_tmpl.replace("%(ext)s", "mp3")
        elif not audio_tmpl.endswith(".mp3"):
            audio_tmpl = audio_tmpl + ".mp3"
        output_tmpl = os.path.join(output_dir, audio_tmpl)
        cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "0", "-o", output_tmpl])
    else:
        output_tmpl = os.path.join(output_dir, name_tmpl)
        cmd.extend([
            "-f", format_spec,
            "-o", output_tmpl,
            "--merge-output-format", config.get_output_format(),
        ])

    subs = (params.get("subs") or "").strip()
    hardsub = bool(params.get("hardsub"))
    if subs:
        cmd.extend([
            "--write-subs", "--write-auto-subs",
            "--sub-langs", subs,
            "--sleep-subtitles", "2",
            "--ignore-errors",
        ])
        if hardsub:
            cmd.extend(["--convert-subs", "srt", "--no-embed-subs"])
        else:
            cmd.append("--embed-subs")

    sponsorblock_mode = params.get("sponsorblock_mode") or "disabled"
    if sponsorblock_mode == "remove":
        cmd.extend(["--sponsorblock-remove", "all"])
    elif sponsorblock_mode == "mark":
        cmd.extend(["--sponsorblock-mark", "all"])

    if params.get("split_chapters"):
        cmd.append("--split-chapters")
        chapter_tmpl = os.path.join(
            output_dir,
            "%(title)s - %(section_number)02d - %(section_title)s.%(ext)s",
        )
        cmd.extend(["-o", f"chapter:{chapter_tmpl}"])

    cookies_path = params.get("cookies_file")
    if cookies_path and os.path.isfile(cookies_path):
        cmd.extend(["--cookies", cookies_path])
    elif cookies_file_configured():
        cmd.extend(["--cookies", str(get_ytdlp_cookies_path())])
    elif params.get("cookies_browser"):
        cmd.extend(["--cookies-from-browser", params["cookies_browser"]])

    if params.get("use_aria2"):
        aria2_status = config.check_binaries_status().get("aria2c", {})
        if aria2_status.get("found"):
            cmd.extend([
                "--external-downloader", aria2_status.get("path"),
                "--external-downloader-args", "aria2c:-j 16 -x 16 -s 16 -k 1M",
            ])

    if params.get("impersonate_browser"):
        cmd.extend(["--impersonate", "chrome"])

    proxy = params.get("proxy")
    if proxy and str(proxy).strip():
        cmd.extend(["--proxy", str(proxy).strip()])

    if params.get("geo_bypass"):
        cmd.extend(["--geo-bypass"])

    if params.get("embed_thumbnail"):
        cmd.extend(["--embed-thumbnail"])

    if params.get("embed_metadata"):
        cmd.extend(["--embed-metadata", "--embed-chapters"])

    limit_rate = params.get("limit_rate")
    if limit_rate and str(limit_rate).strip():
        cmd.extend(["--limit-rate", str(limit_rate).strip()])

    extractor_args = params.get("extractor_args")
    if extractor_args and str(extractor_args).strip():
        cmd.extend(["--extractor-args", str(extractor_args).strip()])

    return cmd


def build_queue_metadata(params: Dict[str, Any]) -> Dict[str, Any]:
    output_dir = params.get("output_dir") or config.get_output_dir()
    meta: Dict[str, Any] = {"output_dir": output_dir}
    video_title = (params.get("video_title") or "").strip()
    if video_title:
        meta["video_title"] = video_title
        meta["file_match_title"] = video_title
        meta["file_match_prefix"] = _sanitize_title_fragment(video_title)[:50]
    if params.get("download_playlist") or params.get("split_chapters"):
        meta["multi_file"] = True
    if params.get("hardsub"):
        meta["hardsub"] = True
    return meta


def build_queue_title(url: str, video_title: Optional[str] = None) -> str:
    from urllib.parse import urlparse

    domain = urlparse(url).netloc.replace("www.", "")
    if video_title and video_title.strip():
        short = video_title.strip()
        if len(short) > 48:
            short = short[:45] + "..."
        return f"Univerzalno ({domain}): {short}"
    return f"Univerzalno ({domain}): {url[:40]}"
