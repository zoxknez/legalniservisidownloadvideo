import json
import logging
import subprocess

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, Response

from backend.config import config, PROJECT_ROOT
from backend.services.eon_adapter import EonAdapter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/playlist.m3u")
def get_iptv_playlist(request: Request):
    channels = []
    try:
        channels_file = PROJECT_ROOT / "eon_channels.json"
        if channels_file.exists():
            with open(channels_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "channels" in data:
                    channels = data["channels"]
    except Exception as e:
        logger.error("Error loading IPTV channels: %s", e)

    if not channels:
        channels = [
            {"name": "RTS 1", "url": ""},
            {"name": "RTS 2", "url": ""},
            {"name": "HRT 1", "url": ""},
            {"name": "HRT 2", "url": ""},
            {"name": "Nova S", "url": ""},
            {"name": "N1 HD", "url": ""},
        ]

    base_url = str(request.base_url).rstrip("/")
    m3u_lines = ["#EXTM3U"]

    for ch in channels:
        name = ch.get("name", "Unknown Channel")
        logo = ""
        if "rts" in name.lower():
            logo = "https://rts.rs/images/logo.png"
        elif "voyo" in name.lower():
            logo = "https://voyo.rs/assets/images/voyo-logo.png"
        elif "hrt" in name.lower():
            logo = "https://hrt.hr/images/logo.png"
        elif "n1" in name.lower():
            logo = "https://rs.n1info.com/wp-content/themes/n1-custom/assets/images/n1-logo.svg"

        logo_attr = f' tvg-logo="{logo}"' if logo else ""
        group = (
            "EON TV"
            if "eon" in name.lower() or "rts" in name.lower() or "n1" in name.lower()
            else "Local IPTV"
        )
        m3u_lines.append(
            f'#EXTINF:-1 tvg-id="{name.lower().replace(" ", "-")}"{logo_attr} group-title="{group}",{name}'
        )
        m3u_lines.append(f"{base_url}/api/iptv/stream/eon/{name}")

    return Response(content="\n".join(m3u_lines), media_type="application/x-mpegurl")


@router.get("/stream/{service}/{channel_id}")
def stream_iptv_channel(service: str, channel_id: str):
    service = service.strip().lower()
    channel_id = channel_id.strip()

    if service != "eon":
        raise HTTPException(status_code=400, detail="Service not supported yet.")

    try:
        stream_info = EonAdapter.resolve_stream(channel_id, "live")
        mpd_url = stream_info.get("mpd_url")
        if not mpd_url:
            raise HTTPException(status_code=404, detail="Live stream could not be resolved.")
    except Exception as e:
        logger.error("Error resolving EON stream for %s: %s", channel_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    ffmpeg_bin = config.get_binary_path("ffmpeg") or "ffmpeg"
    cmd = [
        ffmpeg_bin, "-hide_banner", "-loglevel", "warning", "-y",
        "-reconnect", "1", "-reconnect_streamed", "1",
        "-i", mpd_url,
        "-c", "copy",
        "-async", "1", "-vsync", "-1", "-fflags", "+genpts+igndts",
        "-f", "mpegts",
        "pipe:1",
    ]

    logger.info("Starting live stream proxy via FFmpeg for: %s", channel_id)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def segment_generator():
        try:
            while True:
                chunk = process.stdout.read(40960)
                if not chunk:
                    break
                yield chunk
        except Exception as exc:
            logger.warning("IPTV client disconnected from stream %s: %s", channel_id, exc)
        finally:
            process.kill()
            process.wait()
            logger.info("Released FFmpeg proxy resources for: %s", channel_id)

    return StreamingResponse(segment_generator(), media_type="video/mp2t")
