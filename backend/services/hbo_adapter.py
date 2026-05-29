import logging
from pathlib import Path
from typing import Dict, Any, List

from backend.config import config
from backend.jobs.inprocess import build_job

logger = logging.getLogger(__name__)
CWD = Path(__file__).parent.parent.parent.resolve()


class HboAdapter:
    @staticmethod
    def get_auth_status() -> Dict[str, Any]:
        creds = config.get_credentials("hbomax")
        market = creds.get("market", "emea")
        token = creds.get("token", "")

        token_path = Path.home() / ".hbomax" / "token.json"
        fallback_path = CWD / ".hbomax_token.json"

        authenticated = token_path.exists() or fallback_path.exists() or bool(token)

        resolved_path = ""
        if token_path.exists():
            resolved_path = str(token_path.resolve())
        elif fallback_path.exists():
            resolved_path = str(fallback_path.resolve())

        return {
            "authenticated": authenticated,
            "market": market,
            "token_path": resolved_path,
        }

    @staticmethod
    def make_login_cmd(market: str = "emea") -> List[str]:
        config.update_credentials("hbomax", {"market": market})
        return build_job("hbomax", "login", {"market": market})

    @staticmethod
    def make_download_cmd(video_id: str, subs: str = "sr,hr,mk,bs,sl") -> List[str]:
        market = config.get_credentials("hbomax").get("market", "emea")
        return build_job(
            "hbomax",
            "video",
            {
                "video_id": video_id,
                "subs": subs,
                "market": market,
                "output_dir": config.get_output_dir(),
            },
        )

    @staticmethod
    def make_download_direct_cmd(
        manifest_url: str,
        license_url: str,
        title: str = "",
        subs: str = "sr,hr,mk,bs,sl",
    ) -> List[str]:
        market = config.get_credentials("hbomax").get("market", "emea")
        return build_job(
            "hbomax",
            "direct",
            {
                "manifest_url": manifest_url,
                "license_url": license_url,
                "title": title,
                "subs": subs,
                "market": market,
                "output_dir": config.get_output_dir(),
            },
        )
