import logging
import subprocess
import shutil
import threading
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, Response

from backend.config import config
from backend.services.eon_adapter import EonAdapter
from backend.server_settings import get_api_key

router = APIRouter()
logger = logging.getLogger(__name__)

_active_streams: dict[str, int] = {}
_streams_lock = threading.Lock()


def _ffmpeg_available() -> bool:
    path = config.get_binary_path("ffmpeg")
    if path:
        return shutil.which(path) is not None or shutil.which("ffmpeg") is not None
    return shutil.which("ffmpeg") is not None


@router.get("/status")
def iptv_status():
    eon_status = EonAdapter.get_auth_status()
    ffmpeg_found = _ffmpeg_available()
    eon_ready = bool(eon_status.get("authenticated") or eon_status.get("ready"))

    try:
        channels = EonAdapter.list_channels()
        channel_count = len(channels)
    except Exception:
        channel_count = 0

    with _streams_lock:
        active = dict(_active_streams)

    return {
        "ready": eon_ready and ffmpeg_found,
        "eon_authenticated": eon_ready,
        "ffmpeg_found": ffmpeg_found,
        "channel_count": channel_count,
        "active_streams": active,
        "active_stream_count": sum(active.values()),
    }


@router.get("/playlist.m3u")
def get_iptv_playlist(request: Request):
    try:
        channels = EonAdapter.list_channels()
    except Exception as e:
        logger.error("Error loading IPTV channels via EonAdapter: %s", e)
        channels = []

    if not channels:
        return Response(
            content="#EXTM3U\n# Nema konfigurisanih kanala. Prijavite se na EON TV.\n",
            media_type="application/x-mpegurl",
        )

    base_url = str(request.base_url).rstrip("/")
    api_key = get_api_key()
    key_qs = f"?api_key={quote(api_key, safe='')}" if api_key else ""

    m3u_lines = ["#EXTM3U"]

    for ch_name in channels:
        name = str(ch_name)
        logo = ""
        name_lower = name.lower()
        if "rts" in name_lower:
            logo = "https://rts.rs/images/logo.png"
        elif "hrt" in name_lower:
            logo = "https://hrt.hr/images/logo.png"
        elif "n1" in name_lower:
            logo = "https://rs.n1info.com/wp-content/themes/n1-custom/assets/images/n1-logo.svg"
        elif "nova" in name_lower:
            logo = ""

        logo_attr = f' tvg-logo="{logo}"' if logo else ""
        tvg_id = name_lower.replace(" ", "-")
        group = "EON TV"

        m3u_lines.append(
            f'#EXTINF:-1 tvg-id="{tvg_id}"{logo_attr} group-title="{group}",{name}'
        )
        encoded_name = quote(name, safe="")
        m3u_lines.append(f"{base_url}/api/iptv/stream/eon/{encoded_name}{key_qs}")

    return Response(content="\n".join(m3u_lines), media_type="application/x-mpegurl")


@router.get("/stream/{service}/{channel_id}")
def stream_iptv_channel(service: str, channel_id: str):
    service = service.strip().lower()
    channel_id = channel_id.strip()

    if not channel_id:
        raise HTTPException(status_code=400, detail="Naziv kanala je obavezan.")

    if service != "eon":
        raise HTTPException(status_code=400, detail="Trenutno je podržan samo EON servis.")

    ffmpeg_bin = config.get_binary_path("ffmpeg") or "ffmpeg"
    if not shutil.which(ffmpeg_bin):
        raise HTTPException(status_code=503, detail="FFmpeg nije pronađen. Proverite Postavke.")

    try:
        stream_info = EonAdapter.resolve_stream(channel_id, "live")
        mpd_url = stream_info.get("mpd_url")
        if not mpd_url:
            raise HTTPException(status_code=404, detail=f"Live stream za '{channel_id}' nije pronađen.")

        has_drm = bool(stream_info.get("license_url"))
        if has_drm:
            logger.warning("Stream '%s' zahteva DRM dekripciju — proxy možda neće raditi.", channel_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error resolving EON stream for %s: %s", channel_id, e)
        raise HTTPException(status_code=502, detail=f"Greška pri povezivanju na EON stream: {channel_id}")

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
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    with _streams_lock:
        _active_streams[channel_id] = _active_streams.get(channel_id, 0) + 1

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
            stderr_out = ""
            try:
                stderr_out = process.stderr.read().decode(errors="replace")[-500:]
            except Exception:
                pass
            process.wait()
            with _streams_lock:
                count = _active_streams.get(channel_id, 1) - 1
                if count <= 0:
                    _active_streams.pop(channel_id, None)
                else:
                    _active_streams[channel_id] = count
            if stderr_out.strip():
                logger.warning("FFmpeg stderr for %s: %s", channel_id, stderr_out.strip())
            logger.info("Released FFmpeg proxy resources for: %s", channel_id)

    return StreamingResponse(segment_generator(), media_type="video/mp2t")
