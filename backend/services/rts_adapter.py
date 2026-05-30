import logging
from pathlib import Path
from typing import Any, Dict, List

from backend.config import config
from backend.core.services.rtsplaneta.rtsplaneta_auth import RTSPlanetaAuth, RTSPlanetaConfig
from backend.jobs.inprocess import build_job

logger = logging.getLogger(__name__)
CWD = Path(__file__).parent.parent.parent.resolve()


class RtsAdapter:
    @staticmethod
    def get_auth_status() -> Dict[str, Any]:
        creds = config.get_credentials("rtsplaneta")
        email = creds.get("email", "")
        password = creds.get("password", "")
        if email and password:
            return {"authenticated": True, "email": email}
        return {"authenticated": False, "email": email, "error": "No credentials stored"}

    @staticmethod
    def save_credentials(email: str, password: str) -> Dict[str, Any]:
        try:
            config.update_credentials("rtsplaneta", {"email": email, "password": password})
            cfg = RTSPlanetaConfig()
            cfg.set_credentials(email, password)
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def make_download_cmd(
        target_url: str,
        start_ep: int = None,
        end_ep: int = None,
        verbose: bool = False,
    ) -> List[str]:
        params: Dict[str, Any] = {
            "target_url": target_url,
            "output_dir": config.get_output_dir(),
            "verbose": verbose,
        }
        if start_ep is not None:
            params["start_ep"] = start_ep
        if end_ep is not None:
            params["end_ep"] = end_ep
        return build_job("rtsplaneta", "download", params)

    @staticmethod
    def get_video_info(video_id: str) -> Dict[str, Any]:
        try:
            auth = RTSPlanetaAuth()
            info = auth.get_video_info(video_id)
            video_list = info.get("video", [])
            if not video_list:
                raise ValueError("Video podaci nisu pronađeni na RTS API-ju.")
            video = video_list[0]
            return {
                "success": True,
                "title": video.get("title", f"RTS Video {video_id}"),
                "description": video.get("description", ""),
                "thumbnail": video.get("poster", ""),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}
