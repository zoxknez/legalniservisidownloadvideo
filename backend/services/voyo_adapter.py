import logging
from typing import Dict, Any, List
from pathlib import Path

from backend.core.services.voyo import VoyoAuth, VoyoConfig, VoyoDownloader
from backend.config import config

logger = logging.getLogger(__name__)

class VoyoAdapter:
    @staticmethod
    def get_auth_status() -> Dict[str, Any]:
        """Check if Voyo has valid credentials and if login succeeds."""
        vcfg = VoyoConfig()
        email, password, device_id = vcfg.get_credentials()
        
        # If not in ~/.voyo/config.json, check our app config
        if not email or not password:
            creds = config.get_credentials("voyo")
            email = creds.get("email", "")
            password = creds.get("password", "")
            if email and password:
                vcfg.set_credentials(email, password)
        
        if not email or not password:
            return {"authenticated": False, "email": "", "error": "No credentials stored"}

        try:
            auth = VoyoAuth()
            if device_id:
                auth.state.device_id = device_id
                auth.session.headers['device-id'] = device_id
            
            auth.login(email, password)
            vcfg.update_device_id(auth.state.device_id)
            
            return {
                "authenticated": True,
                "email": email,
                "nickname": auth.state.nickname,
                "subscribed": auth.state.is_subscribed,
                "profile_id": auth.state.profile_id
            }
        except Exception as e:
            return {"authenticated": False, "email": email, "error": str(e)}

    @staticmethod
    def login(email: str, password: str) -> Dict[str, Any]:
        """Verify login, save to both ~/.voyo/config.json and app settings."""
        try:
            vcfg = VoyoConfig()
            vcfg.set_credentials(email, password)
            
            auth = VoyoAuth()
            auth.login(email, password)
            vcfg.update_device_id(auth.state.device_id)
            
            # Sync with our app config
            config.update_credentials("voyo", {"email": email, "password": password})
            
            return {
                "success": True,
                "nickname": auth.state.nickname,
                "subscribed": auth.state.is_subscribed
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_profiles() -> List[Dict[str, Any]]:
        """Fetch profiles of authenticated Voyo user."""
        try:
            vcfg = VoyoConfig()
            email, password, device_id = vcfg.get_credentials()
            if not email:
                return []
            
            auth = VoyoAuth()
            if device_id:
                auth.state.device_id = device_id
                auth.session.headers['device-id'] = device_id
            
            auth.login(email, password)
            return auth.get_profiles()
        except Exception:
            return []

    @staticmethod
    def get_series_info(series_id: int) -> Dict[str, Any]:
        """Fetch series catalog items (episodes)."""
        try:
            vcfg = VoyoConfig()
            email, password, device_id = vcfg.get_credentials()
            if not email:
                raise RuntimeError("No credentials configured")
            
            auth = VoyoAuth()
            if device_id:
                auth.state.device_id = device_id
                auth.session.headers['device-id'] = device_id
            auth.login(email, password)
            
            category = auth.get_category(series_id)
            items = category.get("items", [])
            episodes = []
            
            for ep in items:
                inner = ep.get("meta", {})
                # Try to parse season
                season_str = inner.get("season", "")
                season = 1
                if season_str:
                    import re
                    m = re.search(r"(\d+)", str(season_str))
                    if m:
                        season = int(m.group(1))

                episodes.append({
                    "id": ep.get("id"),
                    "title": ep.get("title", ""),
                    "season": season,
                    "episode": inner.get("episode", 0),
                    "length_mins": ep.get("length", 0) // 60,
                    "drm": bool(ep.get("drmProtected")),
                    "has_subs": bool(ep.get("hasSubtitles"))
                })
            
            return {
                "success": True,
                "title": category.get("title", f"Series {series_id}"),
                "description": category.get("description", ""),
                "episodes": episodes
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def make_download_cmd(target: str, mode: str, episodes_range: str = "", resolution: str = "1080p") -> List[str]:
        """
        Build download command (for backwards compatibility with queue manager).
        Returns a list representing Python function call args.
        """
        output_dir = config.get_output_dir()
        return ["voyo_download", target, mode, episodes_range, resolution, output_dir]

    @staticmethod
    def download_video(video_id: int, output_dir: str = None, resolution: str = "1080p") -> bool:
        """Download a single Voyo video."""
        try:
            vcfg = VoyoConfig()
            email, password, device_id = vcfg.get_credentials()
            if not email:
                raise RuntimeError("No Voyo credentials configured")
            
            auth = VoyoAuth()
            if device_id:
                auth.state.device_id = device_id
                auth.session.headers['device-id'] = device_id
            auth.login(email, password)
            vcfg.update_device_id(auth.state.device_id)
            
            out_dir = output_dir or config.get_output_dir()
            downloader = VoyoDownloader(auth, out_dir, resolution)
            return downloader.download_video(video_id)
        except Exception as e:
            logging.error(f"Download failed: {e}")
            return False

    @staticmethod
    def download_series(series_id: int, episodes_range: str = "", 
                       output_dir: str = None, resolution: str = "1080p") -> tuple:
        """Download Voyo series episodes."""
        try:
            vcfg = VoyoConfig()
            email, password, device_id = vcfg.get_credentials()
            if not email:
                raise RuntimeError("No Voyo credentials configured")
            
            auth = VoyoAuth()
            if device_id:
                auth.state.device_id = device_id
                auth.session.headers['device-id'] = device_id
            auth.login(email, password)
            vcfg.update_device_id(auth.state.device_id)
            
            out_dir = output_dir or config.get_output_dir()
            downloader = VoyoDownloader(auth, out_dir, resolution)
            return downloader.download_series(series_id, episodes_range)
        except Exception as e:
            logging.error(f"Series download failed: {e}")
            return 0, 0
