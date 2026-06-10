#!/usr/bin/env python3
"""
RTSPlaneta Authentication Module
Handles dynamic session, login, and token acquisition

Usage:
    from rtsplaneta_auth import RTSPlanetaAuth
    
    auth = RTSPlanetaAuth()
    auth.login("email@example.com", "password")
    
    streaming_info = auth.get_streaming_url(video_id)
    mpd_url = streaming_info['url']
    license_url = streaming_info['drm']['widevine_la_url']
"""

import requests
import json
import random
import re
import logging
import socket
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# Disable SSL warnings (RTSPlaneta has cert issues)
requests.packages.urllib3.disable_warnings()

logger = logging.getLogger(__name__)


def test_dns(hostname: str) -> bool:
    """Test if we can resolve a hostname"""
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.gaierror as e:
        logger.error(f"DNS resolution failed for {hostname}: {e}")
        return False


class ChromeTLSAdapter(HTTPAdapter):
    """Custom HTTPAdapter that forces urllib3 to use a customized SSL Context matching Chrome."""
    def init_poolmanager(self, *args, **kwargs):
        import ssl
        from urllib3.util.ssl_ import create_urllib3_context
        context = create_urllib3_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_3
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            context.set_ciphers(
                "TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:"
                "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
                "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
                "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
            )
        except Exception:
            pass
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)

def create_session_with_retries() -> requests.Session:
    """Create a requests session with retry logic"""
    session = requests.Session()
    
    # Configure retries
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    adapter = ChromeTLSAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


@dataclass
class AuthState:
    """Holds current authentication state"""
    uuid: str = ""
    session_id: str = ""
    access_token: str = ""
    user_id: str = ""
    profile_id: str = ""


class RTSPlanetaAuth:
    """
    Handles RTSPlaneta authentication flow:
    1. Identify -> session_id
    2. Login -> access_token
    3. Get streaming URL -> mpd_url + license_url with tokens
    """
    
    BASE_URL = "https://prd-rts.spectar.tv/client_api.php"
    
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
        'Content-Type': 'application/json',
        'Origin': 'https://rtsplaneta.rs',
        'Referer': 'https://rtsplaneta.rs/',
        'Accept': 'application/json, text/plain, */*',
    }
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize the auth module.
        
        Args:
            config_file: Optional path to config file with credentials
        """
        self.session = create_session_with_retries()
        self.session.headers.update(self.DEFAULT_HEADERS)
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session.verify = False  # RTSPlaneta's SSL certificates are unreliable
        
        self.state = AuthState()
        self.config = {}
        
        # Test DNS resolution
        if not test_dns("prd-rts.spectar.tv"):
            logger.warning("DNS resolution failed. Trying alternative...")
            # You might need to add the IP directly or use a different DNS
        
        if config_file and Path(config_file).exists():
            self._load_config(config_file)
    
    def _load_config(self, config_file: str):
        """Load config from JSON file"""
        try:
            with open(config_file, 'r') as f:
                self.config = json.load(f)
            logger.info(f"Loaded config from {config_file}")
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
    
    @staticmethod
    def generate_uuid() -> str:
        """
        Generate a device UUID in RTSPlaneta's format.
        Format: 13 hex chars + "-" + 8 digits
        """
        part1 = ''.join(random.choices('0123456789abcdef', k=13))
        part2 = ''.join(random.choices('0123456789', k=8))
        return f"{part1}-{part2}"
    
    def identify(self) -> Dict[str, Any]:
        """
        Step 1: Call identify endpoint to establish a session.
        
        The flow is:
        1. POST to register the device UUID
        2. PUT to get full config with session_id
        
        Returns:
            Full config response from the API
        
        Raises:
            Exception if identify fails
        """
        logger.info("Starting identify flow...")
        
        # Generate new UUID if we don't have one
        if not self.state.uuid:
            self.state.uuid = self.generate_uuid()
            logger.info(f"Generated device UUID: {self.state.uuid}")
        
        url = f"{self.BASE_URL}/config/identify/format/json"
        
        payload = {
            "application_publication_id": "Web",
            "uuid": self.state.uuid,
            "screen_height": 1080,
            "screen_width": 1920,
            "os": "Windows",
            "device_model_string_id": "Chrome",
            "application_version": "1.0.0"
        }
        
        # Step 1: POST to register the device
        logger.debug("POST to register device UUID...")
        post_response = self.session.post(url, json=payload)
        post_response.raise_for_status()
        logger.debug(f"POST response: {post_response.json()}")
        
        # Step 2: PUT to get full config with session_id
        logger.debug("PUT to get session config...")
        put_response = self.session.put(url, json=payload)
        put_response.raise_for_status()
        
        data = put_response.json()
        
        # Check for error
        error = data.get('error', {})
        if isinstance(error, dict) and error.get('message'):
            raise Exception(f"Identify failed: {error.get('message')}")
        
        # Extract session_id
        self.state.session_id = data.get('session_id', '')
        
        if self.state.session_id:
            logger.info(f"Got session_id: {self.state.session_id[:16]}...")
        else:
            logger.warning("Could not extract session_id from identify response")
            logger.debug(f"Response keys: {list(data.keys())}")
        
        return data
    
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Step 2: Login with credentials to get access_token.
        
        Args:
            username: Email/username
            password: Password
            
        Returns:
            User data from login response
            
        Raises:
            Exception if login fails
        """
        # Ensure we have a session first
        if not self.state.session_id:
            self.identify()
        
        if not self.state.session_id:
            raise Exception("No session_id available. Identify failed.")
        
        logger.info(f"Logging in as {username}...")
        
        url = f"{self.BASE_URL}/user/login/session_id/{self.state.session_id}/language/sr/format/json"
        
        payload = {
            "username": username,
            "password": password
        }
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        # Check for error in response
        error = data.get('error', {})
        if isinstance(error, dict) and error.get('@attributes', {}).get('status') != '0':
            error_msg = error.get('message', 'Unknown login error')
            raise Exception(f"Login failed: {error_msg}")
        
        # Extract secure_streaming_token (this is the access token for RTSPlaneta)
        self.state.access_token = (
            data.get('secure_streaming_token') or
            data.get('session_token') or
            data.get('access_token', '')
        )
        
        # Get user_id and profile_id
        self.state.user_id = str(data.get('id', ''))
        self.state.profile_id = str(data.get('subscriber_id', ''))
        
        if self.state.access_token:
            logger.info(f"Login successful! Token: {self.state.access_token[:16]}...")
        else:
            logger.error("Login failed - no token in response")
            logger.debug(f"Response keys: {list(data.keys())}")
            raise Exception("Login failed - no access_token received")
        
        return data
    
    def get_streaming_url(self, video_id: str, asset_type: str = "Movie") -> Dict[str, Any]:
        """
        Get the streaming URL with MPD token and DRM license URLs.
        
        Uses the catalog API which returns the MPD URL with a {TOKEN} placeholder,
        then replaces it with the secure_streaming_token from login.
        
        Args:
            video_id: The video ID to get streaming URL for
            asset_type: Type of asset ("Movie", "Episode", etc.)
            
        Returns:
            Dict containing:
                - url: MPD manifest URL with token
                - drm: Dict with widevine_la_url, etc.
        """
        if not self.state.access_token:
            raise Exception("Not authenticated. Call login() first.")
        
        logger.info(f"Getting streaming URL for video_id: {video_id}")
        
        # Get video info from catalog API
        video_info = self.get_video_info(video_id)
        
        # Extract MPD URL and DRM info from video_assets
        try:
            movie = video_info['video'][0]['video_assets']['movie'][0]
            mpd_url_template = movie.get('url', '')
            drm_info = movie.get('drm', {})
        except (KeyError, IndexError) as e:
            raise Exception(f"Could not find video assets: {e}")
        
        if not mpd_url_template:
            raise Exception("No MPD URL found in video assets")
        
        # Replace {TOKEN} placeholder with actual token
        mpd_url = mpd_url_template.replace('{TOKEN}', self.state.access_token)
        
        # Build license URL with token
        widevine_la_url = drm_info.get('widevine_la_url', 'https://rtsplaneta.rs/drm.php/widevine?token=')
        if not widevine_la_url.endswith(self.state.access_token):
            widevine_la_url = widevine_la_url + self.state.access_token
        
        logger.info("Got streaming URL successfully")
        
        return {
            'url': mpd_url,
            'drm': {
                'protected': drm_info.get('protected', True),
                'widevine_la_url': widevine_la_url,
                'fairplay_la_url': drm_info.get('fairplay_la_url', '') + self.state.access_token,
                'playready_la_url': drm_info.get('playready_la_url', '') + self.state.access_token,
            }
        }
    
    def extract_tokens_from_url(self, url: str) -> Dict[str, str]:
        """
        Extract tokens from MPD or license URL.
        
        Args:
            url: URL containing query parameters
            
        Returns:
            Dict with extracted parameters
        """
        tokens = {}
        
        # Extract token
        token_match = re.search(r'token=([a-f0-9]+)', url)
        if token_match:
            tokens['token'] = token_match.group(1)
        
        # Extract video_id
        vid_match = re.search(r'video_id=(\d+)', url)
        if vid_match:
            tokens['video_id'] = vid_match.group(1)
        
        # Extract other useful params
        for param in ['uuid', 'subscriber_id', 'profile_id', 'application_id']:
            match = re.search(rf'{param}=([^&]+)', url)
            if match:
                tokens[param] = match.group(1)
        
        return tokens
    
    def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """
        Get video metadata from the catalog API.
        
        Args:
            video_id: Video ID to look up
            
        Returns:
            Video metadata dict
        """
        # This uses the old static API endpoint from your original script
        url = (
            f"https://static.rtsplaneta.rs/rev-1584641435/client_api.php"
            f"/vod_catalog/search/instance_id/1/language/en"
            f"/application_id/helium/application_version/1.0.0"
            f"/device_configuration/1/http_proto/https"
            f"/video_id/{video_id}/format/json"
        )
        
        response = self.session.get(url)
        response.raise_for_status()
        
        return response.json()


class RTSPlanetaConfig:
    """
    Configuration manager for RTSPlaneta credentials.
    Stores credentials securely in a config file.
    """
    
    DEFAULT_CONFIG_PATH = Path.home() / '.rtsplaneta' / 'config.json'
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH
        self.config = self._load()
    
    def _load(self) -> dict:
        """Load config from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save(self):
        """Save config to file"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        # Set restrictive permissions
        try:
            self.config_path.chmod(0o600)
        except Exception:
            pass
    
    def set_credentials(self, username: str, password: str):
        """Store credentials (password in OS keyring only)."""
        from backend.credentials_store import set_secret
        self.config['username'] = username
        self.config.pop('password', None)
        self.save()
        if password:
            set_secret('rtsplaneta', 'password', password)

    def get_credentials(self) -> tuple:
        """Get stored credentials"""
        from backend.credentials_store import get_secret
        password = get_secret('rtsplaneta', 'password') or self.config.get('password', '')
        return (
            self.config.get('username', ''),
            password,
        )

    def get_session_token(self) -> str:
        """Token from browser sync / session import (OS keyring)."""
        from backend.credentials_store import get_secret

        return (
            get_secret("rtsplaneta", "secure_streaming_token")
            or get_secret("rtsplaneta", "token")
            or (self.config.get("token") or "").strip()
        )

    def set_session_token(self, token: str) -> None:
        from backend.credentials_store import set_secret

        token = (token or "").strip()
        if not token:
            return
        set_secret("rtsplaneta", "token", token)
        set_secret("rtsplaneta", "secure_streaming_token", token)
        self.config.pop("token", None)
        self.save()

    def has_credentials(self) -> bool:
        """Check if credentials or a synced session token are stored."""
        if self.get_session_token():
            return True
        username, password = self.get_credentials()
        return bool(username and password)


# Example usage and test
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Initialize auth
    auth = RTSPlanetaAuth()
    
    # Check for stored credentials
    config = RTSPlanetaConfig()
    
    if config.has_credentials():
        username, password = config.get_credentials()
        print(f"Using stored credentials for: {username}")
    else:
        username = input("Enter RTSPlaneta username: ").strip()
        password = input("Enter RTSPlaneta password: ").strip()
        
        save = input("Save credentials for future use? (y/n): ").strip().lower()
        if save == 'y':
            config.set_credentials(username, password)
            print(f"Credentials saved to: {config.config_path}")
    
    try:
        # Login
        auth.login(username, password)
        
        print(f"\n✓ Authentication successful!")
        print(f"  Session ID: {auth.state.session_id}")
        print(f"  Access Token: {auth.state.access_token}")
        
        # Test with a video
        video_id = input("\nEnter video ID to test (or press Enter to skip): ").strip()
        
        if video_id:
            streaming = auth.get_streaming_url(video_id)
            
            print(f"\n✓ Got streaming info!")
            print(f"  MPD URL: {streaming.get('url', 'N/A')[:80]}...")
            
            if 'drm' in streaming:
                print(f"  Widevine License URL: {streaming['drm'].get('widevine_la_url', 'N/A')}")
            
            # Extract tokens
            tokens = auth.extract_tokens_from_url(streaming.get('url', ''))
            print(f"\n  Extracted tokens: {tokens}")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
