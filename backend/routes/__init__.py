from fastapi import FastAPI

from .system import router as system_router
from .ws import router as ws_router
from .queue import router as queue_router
from .voyo import router as voyo_router
from .ytdlp import router as ytdlp_router
from .hrti import router as hrti_router
from .eon import router as eon_router
from .rts import router as rts_router
from .hbo import router as hbo_router
from .skyshowtime import router as skyshowtime_router
from .sniffer import router as sniffer_router
from .bridge import router as bridge_router
from .scheduler import router as scheduler_router
from .drm import router as drm_router
from .transcoder import router as transcoder_router
from .iptv import router as iptv_router


def register_routes(app: FastAPI) -> None:
    app.include_router(system_router, tags=["System"])
    app.include_router(ws_router, tags=["WebSocket"])
    app.include_router(queue_router, prefix="/api/queue", tags=["Queue"])
    app.include_router(voyo_router, prefix="/api/voyo", tags=["Voyo"])
    app.include_router(ytdlp_router, prefix="/api/ytdlp", tags=["yt-dlp"])
    app.include_router(hrti_router, prefix="/api/hrti", tags=["HRTi"])
    app.include_router(eon_router, prefix="/api/eon", tags=["EON"])
    app.include_router(rts_router, prefix="/api/rts", tags=["RTS Planeta"])
    app.include_router(hbo_router, prefix="/api/hbo", tags=["HBO Max"])
    app.include_router(skyshowtime_router, prefix="/api/skyshowtime", tags=["SkyShowtime"])
    app.include_router(sniffer_router, prefix="/api/sniffer", tags=["Sniffer"])
    app.include_router(bridge_router, prefix="/api/bridge", tags=["Bridge"])
    app.include_router(scheduler_router, prefix="/api/scheduler", tags=["Scheduler"])
    app.include_router(drm_router, prefix="/api/drm", tags=["DRM"])
    app.include_router(transcoder_router, prefix="/api/transcoder", tags=["Transcoder"])
    app.include_router(iptv_router, prefix="/api/iptv", tags=["IPTV"])
