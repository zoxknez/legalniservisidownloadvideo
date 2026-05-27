import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List
from backend.config import config

logger = logging.getLogger(__name__)
CWD = Path(__file__).parent.parent.parent.resolve()

class HboAdapter:
    @staticmethod
    def get_auth_status() -> Dict[str, Any]:
        """Check if HBO has token stored (implicit auth)."""
        creds = config.get_credentials("hbomax")
        market = creds.get("market", "emea")
        token = creds.get("token", "")
        
        # Check if local hbo token file exists (depending on how script saves it, e.g., in ~/.hbomax/ or similar)
        token_path = Path.home() / ".hbomax" / "token.json" # typical path or similar
        fallback_path = Path(__file__).parent.parent.parent.resolve() / ".hbomax_token.json"
        
        authenticated = token_path.exists() or fallback_path.exists() or bool(token)
        
        resolved_path = ""
        if token_path.exists():
            resolved_path = str(token_path.resolve())
        elif fallback_path.exists():
            resolved_path = str(fallback_path.resolve())

        return {
            "authenticated": authenticated,
            "market": market,
            "token_path": resolved_path
        }

    @staticmethod
    def make_login_cmd(market: str = "emea") -> List[str]:
        """Build command to trigger login."""
        # Sync market setting
        config.update_credentials("hbomax", {"market": market})
        return ["python", "hbomax_downloader.py", "--login", "--market", market]

    @staticmethod
    def make_download_cmd(video_id: str, subs: str = "sr,hr,mk,bs,sl") -> List[str]:
        """Build command to run hbomax_downloader.py."""
        cmd = ["python", "hbomax_downloader.py", "-i", video_id]
        
        # Add subtitles parameter
        if not subs or subs.strip().lower() == "none":
            cmd += ["--subs", "none"]
        else:
            cmd += ["--subs", subs.strip()]
            
        return cmd

    @staticmethod
    def make_download_direct_cmd(
        manifest_url: str,
        license_url: str,
        title: str = "",
        subs: str = "sr,hr,mk,bs,sl",
    ) -> List[str]:
        """Build command for Direct/Bypass download (manifest + license URL mode)."""
        cmd = [
            "python", "hbomax_downloader.py",
            "--manifest", manifest_url,
            "--license",  license_url,
        ]
        if title and title.strip():
            cmd += ["--title", title.strip()]
        if not subs or subs.strip().lower() == "none":
            cmd += ["--subs", "none"]
        else:
            cmd += ["--subs", subs.strip()]
        return cmd
