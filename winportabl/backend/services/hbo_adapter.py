import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List

from backend.config import config
from backend.jobs.inprocess import build_job

logger = logging.getLogger(__name__)


class HboAdapter:
    VALID_MARKETS = ("emea", "latam", "us")

    @staticmethod
    def get_auth_status() -> Dict[str, Any]:
        creds = config.get_credentials("hbomax")
        market = creds.get("market", "emea")

        token_path = Path.home() / ".hbomax" / "token.json"

        authenticated = False
        resolved_path = ""

        if token_path.exists():
            resolved_path = str(token_path.resolve())
            try:
                data = json.loads(token_path.read_text(encoding="utf-8"))
                expires = data.get("expires_at", 0)
                if expires > time.time() + 60:
                    authenticated = True
                elif data.get("refresh_token"):
                    authenticated = True
            except Exception:
                authenticated = True

        return {
            "authenticated": authenticated,
            "market": market,
            "token_path": resolved_path,
        }

    @staticmethod
    def make_login_cmd(market: str = "emea") -> List[str]:
        if market not in HboAdapter.VALID_MARKETS:
            market = "emea"
        config.update_credentials("hbomax", {"market": market})
        return build_job("hbomax", "login", {"market": market})

    @staticmethod
    def make_download_cmd(video_id: str, subs: str = "sr,hr,mk,bs,sl",
                          market: str = "") -> List[str]:
        if not market:
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
