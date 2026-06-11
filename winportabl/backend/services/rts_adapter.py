import logging
from typing import Any, Dict, List

from backend.config import config
from backend.core.services.rtsplaneta.rtsplaneta_auth import RTSPlanetaAuth, RTSPlanetaConfig
from backend.jobs.inprocess import build_job

logger = logging.getLogger(__name__)


class RtsAdapter:
    @staticmethod
    def get_auth_status() -> Dict[str, Any]:
        creds = config.get_credentials("rtsplaneta")
        email = creds.get("email", "")
        token = (creds.get("token") or creds.get("secure_streaming_token") or "").strip()
        password = creds.get("password", "")

        try:
            native_cfg = RTSPlanetaConfig()
            native_email, native_password = native_cfg.get_credentials()
            email = email or native_email
            password = password or native_password
            token = token or native_cfg.get_session_token()
        except Exception as exc:
            logger.debug("RTS native auth status lookup failed: %s", exc)

        if token:
            return {"authenticated": True, "email": email or "(sesija iz browsera)"}
        if email and password:
            return {"authenticated": True, "email": email}
        return {"authenticated": False, "email": email, "error": "Nema sacuvanih kredencijala ili sesije"}

    @staticmethod
    def save_credentials(email: str, password: str) -> Dict[str, Any]:
        try:
            auth = RTSPlanetaAuth()
            auth.login(email, password)
            config.update_credentials("rtsplaneta", {"email": email, "password": password})
            cfg = RTSPlanetaConfig()
            cfg.set_credentials(email, password)
            return {"success": True, "email": email}
        except Exception as exc:
            logger.error("RTS save_credentials failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def make_download_cmd(
        target_url: str,
        start_ep: int = None,
        end_ep: int = None,
        verbose: bool = False,
    ) -> List[str]:
        target_url = target_url.strip()
        if not target_url:
            raise ValueError("RTS target URL je obavezan.")
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
                raise ValueError("Video podaci nisu pronadjeni na RTS API-ju.")
            video = video_list[0]

            raw_title = video.get("title", f"RTS Video {video_id}")
            if isinstance(raw_title, dict):
                raw_title = (
                    raw_title.get("title_long")
                    or raw_title.get("title_medium")
                    or raw_title.get("original_title")
                    or f"RTS Video {video_id}"
                )

            raw_desc = video.get("description", "")
            if isinstance(raw_desc, dict):
                raw_desc = (
                    raw_desc.get("summary_medium")
                    or raw_desc.get("summary_short")
                    or raw_desc.get("summary_long")
                    or ""
                )

            return {
                "success": True,
                "title": raw_title,
                "description": raw_desc,
                "thumbnail": video.get("poster", ""),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}
