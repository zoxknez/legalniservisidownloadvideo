#!/usr/bin/env python3
"""
HRTI (hrti.hrt.hr) Authentication Module

Auth flow:
  1. GET /api/ott/getIPAddress          -> get public IP
  2. POST /api/ott/GrantAccess          -> login -> Token + CustomerId
  3. POST hsapi.aviion.tv/RegisterDevice -> register device UUID -> ReferenceId
  4. Subsequent API calls use: DeviceId, DeviceTypeId, IPAddress, OperatorReferenceId headers

DRM flow (DRMtoday / aviion2):
  - POST /api/ott/AuthorizeSession      -> DrmId (session token)
  - dt-custom-data header = base64({"userId":..., "sessionId": DrmId, "merchant":"aviion2"})
  - License URL: https://lic.drmtoday.com/license-proxy-widevine/cenc/
"""

import requests
import json
import re
import uuid
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path
import base64

from backend.services.tls_client_helper import apply_chrome_fingerprint

logger = logging.getLogger(__name__)

BASE_URL = "https://hrti.hrt.hr/api/api/ott"
AVIION_API = "https://hsapi.aviion.tv/client.svc/json"
OPERATOR_REF = "hrt"
DEVICE_TYPE_ID = "6"
APP_VERSION = "5.97.7"


@dataclass
class HRTIAuthState:
    device_id: str = ""
    ip_address: str = ""
    token: str = ""
    customer_id: str = ""
    aviion_ref_id: str = ""




class HRTIAuth:
    """
    Handles HRTI authentication.

    Usage:
        auth = HRTIAuth()
        auth.login("user@email.com", "password")
        mpd_url, drm_headers = auth.get_stream_info("9a7bb881-0b1b-bc57-ab38-07b93d293a56")
    """

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Accept-Language": "en-US,en;q=0.9,hr;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    def __init__(self, config_path: Optional[str] = None):
        self.session = requests.Session()
        apply_chrome_fingerprint(self.session)
        self.session.headers.update(self.DEFAULT_HEADERS)
        self.state = HRTIAuthState()
        self.config_path = Path(config_path) if config_path else Path.home() / ".hrti" / "config.json"
        self._load_config()

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _load_config(self):
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    cfg = json.load(f)
                self.state.device_id = cfg.get("device_id", "")
                self.state.aviion_ref_id = cfg.get("aviion_ref_id", "")
                logger.debug(f"Loaded config from {self.config_path}")
            except Exception as e:
                logger.warning(f"Could not load config: {e}")

    def _save_config(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        cfg = {"device_id": self.state.device_id}
        if self.state.aviion_ref_id:
            cfg["aviion_ref_id"] = self.state.aviion_ref_id
        with open(self.config_path, "w") as f:
            json.dump(cfg, f, indent=2)
        try:
            self.config_path.chmod(0o600)
        except Exception:
            pass

    def save_credentials(self, username: str, password: str):
        from backend.credentials_store import set_secret
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        cfg = {}
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    cfg = json.load(f)
            except Exception:
                pass
        cfg["username"] = username
        cfg["email"] = username
        cfg.pop("password", None)
        cfg["device_id"] = self.state.device_id
        with open(self.config_path, "w") as f:
            json.dump(cfg, f, indent=2)
        try:
            self.config_path.chmod(0o600)
        except Exception:
            pass
        if password:
            set_secret("hrti", "password", password)
        logger.info(f"Credentials saved to {self.config_path}")

    def get_stored_credentials(self):
        from backend.credentials_store import get_secret
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    cfg = json.load(f)
                u = cfg.get("username", "")
                p = get_secret("hrti", "password") or cfg.get("password", "")
                if u and p:
                    return u, p
            except Exception:
                pass
        return None, None

    # ------------------------------------------------------------------
    # Internal API helpers
    # ------------------------------------------------------------------

    def _api_headers(self, referer: str = "https://hrti.hrt.hr/") -> Dict[str, str]:
        """Headers required by hrti.hrt.hr API endpoints.
        Authorization must be 'Client <token>' — not Bearer. Source: Kodi plugin.
        """
        hdrs = {
            "DeviceId": self.state.device_id,
            "DeviceTypeId": DEVICE_TYPE_ID,
            "IPAddress": self.state.ip_address,
            "OperatorReferenceId": OPERATOR_REF,
            "Referer": referer,
            "Origin": "https://hrti.hrt.hr",
        }
        if self.state.token:
            hdrs["Authorization"] = f"Client {self.state.token}"
        return hdrs

    # ------------------------------------------------------------------
    # Auth steps
    # ------------------------------------------------------------------

    def _get_ip(self) -> str:
        """Fetch current public IP from HRTI endpoint."""
        resp = self.session.get(f"{BASE_URL}/getIPAddress", timeout=15)
        resp.raise_for_status()
        ip = resp.json().strip('"')
        logger.info(f"Public IP: {ip}")
        return ip

    def _ensure_device_id(self):
        """Generate a stable device UUID on first run, reuse on subsequent runs."""
        if not self.state.device_id:
            self.state.device_id = str(uuid.uuid4())
            self._save_config()
            logger.info(f"Generated device ID: {self.state.device_id}")

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
        """
        Login flow:
          1. Get IP
          2. Ensure device UUID (stable, saved to disk)
          3. POST GrantAccess -> Token + CustomerId

        Args:
            username: Email. If None, uses stored credentials.
            password: Password. If None, uses stored credentials.

        Returns:
            Customer dict from GrantAccess response.
        """
        if not username or not password:
            username, password = self.get_stored_credentials()
            if not username:
                raise ValueError("No credentials provided and none stored. "
                                 "Run with --save-credentials first.")
            logger.info(f"Using stored credentials for: {username}")

        self.state.ip_address = self._get_ip()
        self._ensure_device_id()

        logger.info(f"Logging in as {username}...")

        resp = self.session.post(
            f"{BASE_URL}/GrantAccess",
            json={
                "Username": username,
                "Password": password,
                "OperatorReferenceId": OPERATOR_REF,
            },
            headers=self._api_headers(referer="https://hrti.hrt.hr/signin"),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("ErrorCode", -1) != 0:
            raise Exception(f"Login failed: {data.get('ErrorDescription', 'Unknown error')}")

        result = data["Result"]
        self.state.token = result["Token"]
        self.state.customer_id = result["Customer"]["CustomerId"]

        logger.info(f"Login successful. CustomerId: {self.state.customer_id}")
        logger.debug(f"Token: {self.state.token[:20]}...")

        # Register device with aviion
        self._register_device()
        self._save_config()

        return result["Customer"]

    def _register_device(self, retry_on_used_device: bool = True):
        """
        Register device with aviion backend.
        Uses HRTI Token as Authorization: Client.
        Must be called after GrantAccess (needs token).
        """
        payload = {
            "DeviceSerial": self.state.device_id,
            "DeviceReferenceId": DEVICE_TYPE_ID,
            "IpAddress": self.state.ip_address,
            "ConnectionType": "LAN/WiFi",
            "ApplicationVersion": APP_VERSION,
            "DrmId": self.state.device_id,
            "OsVersion": "Windows 10",
            "ClientType": "Chrome 147",
        }
        resp = self.session.post(
            f"{AVIION_API}/RegisterDevice",
            json=payload,
            headers={
                "Authorization": f"Client {self.state.token}",
                "Origin": "https://hrti.hrt.hr",
                "Referer": "https://hrti.hrt.hr/",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("ErrorCode", -1) != 0:
            error_desc = data.get("ErrorDescription", "")
            if retry_on_used_device and "already used on another customer" in error_desc.lower():
                logger.warning("Device ID already registered to another customer. Generating a new one and retrying...")
                self.state.device_id = str(uuid.uuid4())
                self._save_config()
                return self._register_device(retry_on_used_device=False)
            raise Exception(f"RegisterDevice failed: {error_desc}")
        self.state.aviion_ref_id = data["Result"].get("ReferenceId", "")
        logger.info(f"Device registered. ReferenceId: {self.state.aviion_ref_id}")

    def is_authenticated(self) -> bool:
        return bool(self.state.token and self.state.customer_id)

    # ------------------------------------------------------------------
    # Video / streaming
    # ------------------------------------------------------------------

    def get_vod_details(self, reference_id: str) -> Dict[str, Any]:
        """
        Get VOD metadata including MPD URL (FileName field).

        Args:
            reference_id: The UUID-format video reference ID.

        Returns:
            Result dict with FileName, OriginalTitle, etc.
        """
        resp = self.session.post(
            f"{BASE_URL}/GetVodDetails",
            json={"ReferenceId": reference_id},
            headers=self._api_headers(referer="https://hrti.hrt.hr/videostore"),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.debug(f"GetVodDetails raw response: {data}")
        if data.get("ErrorCode", -1) != 0:
            raise Exception(f"GetVodDetails failed (ErrorCode={data.get('ErrorCode')}): {data.get('ErrorDescription')}")
        return data["Result"]

    def authorize_session(self, reference_id: str, content_drm_id: Optional[str] = None) -> str:
        """
        Authorize a playback session and retrieve a DrmId (session token).

        Args:
            reference_id: VOD UUID.
            content_drm_id: Optional DRM content ID. Constructed from reference_id if absent.

        Returns:
            DrmId string (used as sessionId in dt-custom-data for license requests).
        """
        if not content_drm_id:
            content_drm_id = f"hrtvodorigin_{reference_id}.smil"

        payload = {
            "ContentType": "svod",
            "ContentReferenceId": reference_id,
            "ContentDrmId": content_drm_id,
            "VideostoreReferenceIds": ["hrttest", "hrthbbtv"],
            "ChannelReferenceId": None,
            "StartTime": None,
            "EndTime": None,
        }

        resp = self.session.post(
            f"{BASE_URL}/AuthorizeSession",
            json=payload,
            headers=self._api_headers(referer="https://hrti.hrt.hr/videostore"),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("ErrorCode", -1) != 0:
            raise Exception(f"AuthorizeSession failed: {data.get('ErrorDescription')}")

        drm_id = data["Result"]["DrmId"]
        logger.info(f"Session authorized. DrmId: {drm_id[:20]}...")
        return drm_id

    def build_drm_headers(self, drm_id: str) -> Dict[str, str]:
        """
        Build the license request header for DRMtoday (aviion2 merchant).

        dt-custom-data = base64({"userId": customer_id, "sessionId": drm_id, "merchant": "aviion2"})
        """
        custom_data = {
            "userId": self.state.customer_id,
            "sessionId": drm_id,
            "merchant": "aviion2",
        }
        encoded = base64.b64encode(json.dumps(custom_data).encode()).decode()
        return {
            "dt-custom-data": encoded,
            "Origin": "https://hrti.hrt.hr",
            "Referer": "https://hrti.hrt.hr/",
        }

    def get_stream_info(self, reference_id: str) -> Dict[str, Any]:
        """
        Full streaming info for a VOD item:
          - Fetches VOD details (MPD URL)
          - Authorizes session (DrmId)
          - Returns mpd_url, license_url, drm_headers, title
        """
        if not self.is_authenticated():
            raise Exception("Not authenticated. Call login() first.")

        details = self.get_vod_details(reference_id)
        mpd_url = details.get("FileName", "")
        if not mpd_url:
            raise Exception("No MPD URL (FileName) in GetVodDetails response")

        content_drm_id = None
        m = re.search(r'hrtvodorigin/([^/]+)\.smil', mpd_url)
        if m:
            content_drm_id = f"hrtvodorigin_{m.group(1)}.smil"

        drm_id = self.authorize_session(reference_id, content_drm_id)
        drm_headers = self.build_drm_headers(drm_id)

        series_name = (details.get("SeriesName") or "").strip()
        season = details.get("SeasonNr")
        episode = details.get("EpisodeNr")
        if series_name and season is not None and episode is not None:
            from .hrti_downloader import HRTIDownloader

            base = HRTIDownloader.sanitize_filename(series_name.replace(" ", "."))
            title = f"{base}.S{int(season):02d}E{int(episode):02d}"
        else:
            title = details.get("OriginalTitle") or details.get("Title") or reference_id

        return {
            "mpd_url": mpd_url,
            "license_url": "https://lic.drmtoday.com/license-proxy-widevine/cenc/",
            "drm_headers": drm_headers,
            "title": title,
            "duration_frames": details.get("DurationInFrames", 0),
            "details": details,
        }

    def get_catalogue(self, category_id: Optional[str] = None, page: int = 1, page_size: int = 24) -> Dict:
        """Fetch catalogue items."""
        payload: Dict[str, Any] = {
            "PageNumber": page,
            "ItemsPerPage": page_size,
        }
        if category_id:
            payload["ReferenceId"] = category_id
        else:
            payload["ReferenceId"] = "vod"

        resp = self.session.post(
            f"{BASE_URL}/GetCatalogue",
            json=payload,
            headers=self._api_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("ErrorCode", -1) != 0:
            raise Exception(f"GetCatalogue failed: {data.get('ErrorDescription')}")
        return data["Result"]


if __name__ == "__main__":
    import sys
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Test HRTI auth")
    parser.add_argument("-u", "--username")
    parser.add_argument("-p", "--password")
    parser.add_argument("--save-credentials", action="store_true")
    parser.add_argument("--ref-id", help="Test with a video reference ID")
    args = parser.parse_args()

    auth = HRTIAuth()

    if args.save_credentials:
        if not args.username or not args.password:
            print("--save-credentials requires -u and -p")
            sys.exit(1)
        auth.save_credentials(args.username, args.password)

    try:
        auth.login(args.username, args.password)
        print(f"\n✓ Logged in. CustomerId: {auth.state.customer_id}")
        print(f"  Device ID: {auth.state.device_id}")

        if args.ref_id:
            info = auth.get_stream_info(args.ref_id)
            print(f"\n✓ Stream info for '{info['title']}':")
            print(f"  MPD:     {info['mpd_url']}")
            print(f"  License: {info['license_url']}")
            print(f"  dt-custom-data: {info['drm_headers']['dt-custom-data'][:40]}...")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
