import json
import logging
from pathlib import Path
from typing import Dict, Any, List

from backend.config import config
from backend.core.services.hbomax.hbomax_auth import is_token_valid
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
        error = ""

        if token_path.exists():
            resolved_path = str(token_path.resolve())
            try:
                data = json.loads(token_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("token.json mora biti JSON objekat")
                if is_token_valid(data):
                    authenticated = True
                elif data.get("refresh_token"):
                    authenticated = True
                else:
                    error = "HBO Max token je istekao ili ne sadrži access/refresh token."
            except Exception as exc:
                authenticated = False
                error = f"HBO Max token fajl je neispravan: {exc}"

        result = {
            "authenticated": authenticated,
            "market": market,
            "token_path": resolved_path,
        }
        if error:
            result["error"] = error
        return result

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
