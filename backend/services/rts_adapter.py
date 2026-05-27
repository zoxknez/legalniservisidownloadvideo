import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List
from backend.config import config

logger = logging.getLogger(__name__)
CWD = Path(__file__).parent.parent.parent.resolve()

class RtsAdapter:
    @staticmethod
    def get_auth_status() -> Dict[str, Any]:
        """Check if RTS has stored credentials (both email AND password) in app config."""
        creds = config.get_credentials("rtsplaneta")
        email = creds.get("email", "")
        password = creds.get("password", "")
        if email and password:
            return {"authenticated": True, "email": email}
        return {"authenticated": False, "email": email, "error": "No credentials stored"}

    @staticmethod
    def save_credentials(email: str, password: str) -> Dict[str, Any]:
        """Runs the --save-credentials command for RTS Planeta."""
        try:
            config.update_credentials("rtsplaneta", {"email": email, "password": password})
            script_path = CWD / "rtsplaneta_downloader.py"
            if not script_path.exists():
                return {"success": True}

            cmd = [
                "python", "rtsplaneta_downloader.py",
                "--save-credentials",
                "-u", email,
                "-p", password
            ]
            res = subprocess.run(cmd, cwd=str(CWD.resolve()), capture_output=True, text=True)
            if res.returncode == 0:
                return {"success": True}
            return {"success": False, "error": res.stderr or res.stdout}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def make_download_cmd(target_url: str, start_ep: int = None, end_ep: int = None, verbose: bool = False) -> List[str]:
        """Build command to run rtsplaneta_downloader.py."""
        cmd = ["python", "rtsplaneta_downloader.py", "-i", target_url]
        
        if start_ep is not None:
            cmd += ["--start", str(start_ep)]
            
        if end_ep is not None:
            cmd += ["--end", str(end_ep)]
            
        if verbose:
            cmd.append("-v")

        return cmd

    @staticmethod
    def get_video_info(video_id: str) -> Dict[str, Any]:
        """Fetch metadata for a single RTS Planeta video."""
        try:
            from backend.core.services.rtsplaneta.rtsplaneta_auth import RTSPlanetaAuth
            auth = RTSPlanetaAuth()
            info = auth.get_video_info(video_id)
            # Handle potential nested lists/dicts safely
            video_list = info.get("video", [])
            if not video_list:
                raise ValueError("Video podaci nisu pronađeni na RTS API-ju.")
            video = video_list[0]
            return {
                "success": True,
                "title": video.get("title", f"RTS Video {video_id}"),
                "description": video.get("description", ""),
                "thumbnail": video.get("poster", "")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
