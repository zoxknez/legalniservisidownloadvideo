#!/usr/bin/env python3
"""
EON TV Authentication Module
Handles device registration, login, and token acquisition for EON TV (eon.tv)

EON TV is a multi-brand streaming platform operated by United Group.
Supported providers: SBB (Serbia), Telemach, Vivacom, Nova, etc.

Usage:
    from eon_auth import EONAuth
    
    auth = EONAuth(provider='sbb')  # or 'telemach', 'vivacom', etc.
    auth.login("username", "password")
    
    # Access token is now available
    print(auth.state.access_token)
"""

import requests
import json
import hashlib
import base64
import secrets
import logging
import platform
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

logger = logging.getLogger(__name__)


# Provider configurations - maps provider identifier to CDN identifier
PROVIDERS = {
    'sbb': {
        'cdn': 'ug',
        'api_region': 'be',  # Backend region
        'name': 'SBB',
        'country': 'RS',
    },
    'sbb-qa': {
        'cdn': 'ug',
        'api_region': 'be',
        'name': 'SBB',
        'country': 'RS',
    },
    'telemach': {
        'cdn': 'ug',
        'api_region': 'be',
        'name': 'Telemach',
        'country': 'SI',
    },
    'vivacom': {
        'cdn': 'vivacom',
        'api_region': 'be',
        'name': 'Vivacom',
        'country': 'BG',
    },
    'nova': {
        'cdn': 'forthnet',
        'api_region': 'be',
        'name': 'Nova',
        'country': 'GR',
    },
}


def create_session_with_retries() -> requests.Session:
    """Create a requests session with retry logic"""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def generate_device_serial() -> str:
    """
    Generate a device serial number.
    Format: base64-encoded random bytes (22 chars + padding)
    Example from HAR: "k3He+v62zEgZFljHKdSipA"
    """
    # Generate 16 random bytes and base64 encode
    random_bytes = secrets.token_bytes(16)
    serial = base64.urlsafe_b64encode(random_bytes).decode('utf-8').rstrip('=')
    return serial


def hash_username(username: str, salt: str = '') -> str:
    """
    Hash the username for authentication.
    
    EON TV sends the username as a SHA256 hash (uppercase hex).
    The exact salt/format may vary by provider.
    
    Args:
        username: The actual username/email
        salt: Optional salt to append
        
    Returns:
        SHA256 hash in uppercase hex format
    """
    data = username + salt
    return hashlib.sha256(data.encode('utf-8')).hexdigest().upper()


@dataclass
class AuthState:
    """Holds current authentication state"""
    device_number: str = ""
    device_id: int = 0
    access_token: str = ""
    refresh_token: str = ""
    user_id: int = 0
    subscriber_id: int = 0
    profile_id: int = 0
    profiles: List[Dict] = field(default_factory=list)
    
    # Streaming credentials (from token response)
    stream_un: str = ""  # Stream username
    stream_key: str = ""  # Stream key for authentication
    
    # Additional useful fields
    sub_package_ids: List[int] = field(default_factory=list)  # Subscribed packages
    topics: List[str] = field(default_factory=list)  # Push notification topics


@dataclass
class DeviceInfo:
    """Device registration information"""
    device_type: str = "web_windows_chrome"
    model_name: str = "Chrome 147"
    platform: str = "web"
    os_name: str = "Windows"
    os_version: str = "10"
    client_version: str = ""


class EONAuth:
    """
    Handles EON TV authentication flow:
    1. Register device -> device_number
    2. Login with username/password -> access_token, refresh_token
    3. Select profile (optional) -> updated access_token
    """
    
    BROKER_URL = "https://broker.global.united.cloud"
    
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9,sr;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Origin': 'https://eon.tv',
        'Referer': 'https://eon.tv/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors', 
        'Sec-Fetch-Site': 'cross-site',
        'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        # EON-specific headers (from HAR analysis)
        'X-UCP-TIME-FORMAT': 'timestamp',
        'X-Ucp-Language': 'srp',
        'X-Ucp-Theme-Mode': 'ALL',
    }
    
    def __init__(self, provider: str = 'sbb', config_file: Optional[str] = None):
        """
        Initialize the EON auth module.
        
        Args:
            provider: Provider identifier ('sbb', 'telemach', 'vivacom', etc.)
            config_file: Optional path to config file with credentials
        """
        self.provider = provider.lower()
        
        if self.provider not in PROVIDERS:
            available = ', '.join(PROVIDERS.keys())
            raise ValueError(f"Unknown provider '{provider}'. Available: {available}")
        
        self.provider_config = PROVIDERS[self.provider]
        
        # Build API base URL from CDN info
        cdn = self.provider_config['cdn']
        region = self.provider_config['api_region']
        self.api_base = f"https://api-web.{cdn}-{region}.cdn.united.cloud"
        
        logger.info(f"EON API base: {self.api_base}")
        
        # Session setup
        self.session = create_session_with_retries()
        self.session.headers.update(self.DEFAULT_HEADERS)
        
        # State
        self.state = AuthState()
        self.device_info = self._detect_device_info()
        self.device_serial = generate_device_serial()
        
        # Load config if provided
        if config_file and Path(config_file).exists():
            self._load_config(config_file)
    
    def set_server_ip(self, ip: str):
        """
        Force requests to use a specific server IP.
        This can help when load balancers route Python differently than browsers.
        
        Args:
            ip: IP address to use (e.g., '5.22.186.37')
        """
        from urllib3.util.ssl_ import create_urllib3_context
        import socket
        
        # Create a custom adapter that resolves to our IP
        class ForcedIPAdapter(HTTPAdapter):
            def __init__(self, dest_ip, *args, **kwargs):
                self.dest_ip = dest_ip
                super().__init__(*args, **kwargs)
            
            def send(self, request, *args, **kwargs):
                # Modify the URL to use the IP but keep the Host header
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(request.url)
                # Replace hostname with IP in the connection
                connection_key = (parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80))
                return super().send(request, *args, **kwargs)
        
        # Alternative: Use requests-toolbelt or override getaddrinfo
        original_getaddrinfo = socket.getaddrinfo
        target_host = 'api-web.ug-be.cdn.united.cloud'
        
        def patched_getaddrinfo(host, port, *args, **kwargs):
            if host == target_host:
                logger.debug(f"Resolving {host} to forced IP {ip}")
                # Return IPv4 address info
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port))]
            return original_getaddrinfo(host, port, *args, **kwargs)
        
        socket.getaddrinfo = patched_getaddrinfo
        logger.info(f"Forcing server IP: {ip} for {target_host}")
    
    def _detect_device_info(self) -> DeviceInfo:
        """Detect current device information"""
        system = platform.system()
        
        if system == 'Windows':
            return DeviceInfo(
                device_type='web_windows_chrome',
                model_name='Chrome 147',
                platform='web',
                os_name='Windows',
                os_version='10'
            )
        elif system == 'Darwin':
            return DeviceInfo(
                device_type='web_macos_chrome',
                model_name='Chrome 147',
                platform='web',
                os_name='macOS',
                os_version='14'
            )
        else:
            return DeviceInfo(
                device_type='web_linux_chrome',
                model_name='Chrome 147',
                platform='web',
                os_name='Linux',
                os_version='6'
            )
    
    def _load_config(self, config_file: str):
        """Load config from JSON file"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded config from {config_file}")
            
            # Restore device serial if available
            if 'device_serial' in config:
                self.device_serial = config['device_serial']
            if 'device_number' in config:
                self.state.device_number = config['device_number']
                
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
    
    def _add_common_headers(self, extra: Optional[Dict] = None) -> Dict:
        """Build common headers for API calls"""
        headers = {
            'X-UCP-TIME-FORMAT': 'timestamp',
        }
        
        # Add Bearer token if authenticated
        if self.state.access_token:
            headers['Authorization'] = f'Bearer {self.state.access_token}'
        
        if extra:
            headers.update(extra)
        return headers
    
    def get_brands(self) -> List[Dict]:
        """
        Get list of available provider brands.
        
        Returns:
            List of brand configurations
        """
        url = f"{self.BROKER_URL}/v2/brands"
        
        response = self.session.get(url)
        response.raise_for_status()
        
        return response.json()
    
    def get_cdn_info(self) -> List[Dict]:
        """
        Get CDN configuration info.
        
        Returns:
            List of CDN configurations
        """
        url = f"{self.BROKER_URL}/v1/cdninfo"
        
        response = self.session.get(url)
        response.raise_for_status()
        
        return response.json()
    
    def register_device(self) -> Dict[str, Any]:
        """
        Register this device with the EON service.
        
        Returns:
            Device registration response containing deviceNumber
            
        Raises:
            Exception if registration fails
        """
        url = f"{self.api_base}/v1/devices"
        
        payload = {
            "deviceName": "",
            "deviceType": self.device_info.device_type,
            "modelName": self.device_info.model_name,
            "platform": self.device_info.platform,
            "serial": self.device_serial,
            "clientSwVersion": self.device_info.client_version,
            "systemSwVersion": {
                "name": self.device_info.os_name,
                "version": self.device_info.os_version
            }
        }
        
        # OAuth client credentials for Basic auth
        import base64
        client_id = 'b8d9ade4-1093-46a7-a4f7-0e47be463c10'
        client_secret = '1w4dmww87x1e9l89essqvc81pidrqsa0li1rva23'
        auth_string = f"{client_id}:{client_secret}"
        auth_bytes = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Basic {auth_bytes}',
        }
        
        logger.info("Registering device...")
        logger.debug(f"Device payload: {json.dumps(payload)}")
        
        response = self.session.post(url, json=payload, headers=headers)
        
        logger.debug(f"Device registration status: {response.status_code}")
        logger.debug(f"Device registration response: {response.text[:500] if response.text else 'empty'}")
        
        response.raise_for_status()
        
        data = response.json()
        
        self.state.device_number = data.get('deviceNumber', '')
        self.state.device_id = data.get('deviceId', 0)
        
        logger.info(f"Device registered: {self.state.device_number}")
        logger.debug(f"Device ID: {self.state.device_id}")
        
        return data
    
    def set_device(self, serial: str, device_number: str, save: bool = True):
        """
        Set device credentials manually (for reusing existing device).
        
        Args:
            serial: Device serial (from HAR)
            device_number: Device number/UUID (from HAR)  
            save: Save to config file for future use
        """
        self.device_serial = serial
        self.state.device_number = device_number
        logger.info(f"Device set manually: {device_number}")
        
        if save:
            config = EONConfig()
            config.set_device_info(serial, device_number)
            logger.info(f"Device info saved to: {config.config_path}")
    
    def login(self, username: str, password: str, hash_username_flag: bool = True, 
              force_new_device: bool = False) -> Dict[str, Any]:
        """
        Login with username/password.
        
        The login flow:
        1. Load existing device or register new one
        2. POST to /oauth/token with credentials
        3. Store access_token and refresh_token
        
        Args:
            username: Username or email
            password: Password
            hash_username_flag: Whether to hash the username (default True for EON)
            force_new_device: Force registration of a new device (helps with server routing)
            
        Returns:
            Login response data
            
        Raises:
            Exception if login fails
        """
        # Try to load existing device first (unless forcing new)
        if not self.state.device_number and not force_new_device:
            config = EONConfig()
            if config.has_device_info():
                serial, device_number = config.get_device_info()
                self.device_serial = serial
                self.state.device_number = device_number
                logger.info(f"Using existing device: {device_number}")
        
        # Register new device if needed
        if not self.state.device_number or force_new_device:
            try:
                self.register_device()
                # Save the new device
                config = EONConfig()
                config.set_device_info(self.device_serial, self.state.device_number)
            except Exception as e:
                logger.error(f"Device registration failed: {e}")
                raise Exception(
                    "Device registration failed. You may need to provide existing device info.\n"
                    "Use: auth.set_device('serial', 'device_number') or save via config."
                )
        
        url = f"{self.api_base}/oauth/token?grant_type=password"
        
        # EON expects the username as a SHA256 hash
        if hash_username_flag:
            login_username = hash_username(username)
        else:
            login_username = username
        
        logger.info(f"Logging in as: {username}")
        if hash_username_flag:
            logger.debug(f"Username hash: {login_username}")
        
        # EON uses multipart/form-data for the OAuth token request
        # We use the 'files' parameter trick to send multipart data
        form_data = {
            'username': (None, login_username),
            'password': (None, password),
            'device_number': (None, self.state.device_number),
        }
        
        # OAuth client credentials from Kodi pvr.eon addon
        # These are required for Basic auth on the token endpoint
        import base64
        client_id = 'b8d9ade4-1093-46a7-a4f7-0e47be463c10'
        client_secret = '1w4dmww87x1e9l89essqvc81pidrqsa0li1rva23'
        
        # Always use Basic auth now (server requires it as of April 2026)
        auth_string = f"{client_id}:{client_secret}"
        auth_bytes = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://eon.tv',
            'Referer': 'https://eon.tv/',
            'Authorization': f'Basic {auth_bytes}',
        }
        
        logger.debug(f"Login URL: {url}")
        logger.debug(f"Device number: {self.state.device_number}")
        
        response = self.session.post(url, files=form_data, headers=headers)
        
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Server: {response.headers.get('X-Ucp-Server', 'unknown')}")
        
        logger.debug(f"Response headers: {dict(response.headers)}")
        logger.debug(f"Response body: {response.text[:1000] if response.text else 'empty'}")
        
        if response.status_code == 401:
            # Try to get error details
            try:
                error_data = response.json()
                error_msg = error_data.get('error_description', error_data.get('error', 'Unknown'))
                logger.error(f"Login failed: {error_msg}")
            except:
                logger.error(f"Login failed with status 401")
            raise Exception(f"Invalid username or password. Response: {response.text[:200]}")
        
        response.raise_for_status()
        
        data = response.json()
        
        # Extract tokens
        self.state.access_token = data.get('access_token', '')
        self.state.refresh_token = data.get('refresh_token', '')
        
        # Extract streaming credentials (critical for video playback)
        self.state.stream_un = data.get('stream_un', '')
        self.state.stream_key = data.get('stream_key', '')
        
        # Extract additional useful data
        self.state.sub_package_ids = data.get('sub_package_ids', [])
        self.state.topics = data.get('topics', [])
        
        # Decode JWT to get user info (access_token is a JWT)
        try:
            payload = self._decode_jwt(self.state.access_token)
            self.state.user_id = payload.get('user_id', 0)
            self.state.subscriber_id = payload.get('sub_id', 0)
            self.state.profile_id = payload.get('active_profile_id', 0)
        except Exception as e:
            logger.warning(f"Failed to decode JWT: {e}")
        
        logger.info("Login successful!")
        logger.debug(f"Access token: {self.state.access_token[:50]}...")
        logger.debug(f"Stream credentials: un={self.state.stream_un}, key={self.state.stream_key[:10]}...")
        
        return data
    
    def _decode_jwt(self, token: str) -> Dict:
        """Decode JWT payload (without verification)"""
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return {}
            
            # Add padding
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            
            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded)
        except Exception:
            return {}
    
    def refresh_access_token(self) -> Dict[str, Any]:
        """
        Refresh the access token using the refresh token.
        
        Returns:
            New token response
        """
        if not self.state.refresh_token:
            raise Exception("No refresh token available")
        
        url = f"{self.api_base}/oauth/token?grant_type=refresh_token&refresh_token={self.state.refresh_token}"
        
        # Empty multipart body
        response = self.session.post(url, files={})
        response.raise_for_status()
        
        data = response.json()
        
        self.state.access_token = data.get('access_token', '')
        self.state.refresh_token = data.get('refresh_token', '')
        
        logger.info("Token refreshed successfully")
        
        return data
    
    def get_profiles(self) -> List[Dict]:
        """
        Get list of user profiles.
        
        Returns:
            List of profile objects
        """
        url = f"{self.api_base}/v1/profiles"
        
        headers = self._add_common_headers()
        
        response = self.session.get(url, headers=headers)
        response.raise_for_status()
        
        self.state.profiles = response.json()
        
        return self.state.profiles
    
    def select_profile(self, profile_id: int) -> Dict[str, Any]:
        """
        Select a user profile.
        
        This updates the access token with the selected profile.
        
        Args:
            profile_id: Profile ID to select
            
        Returns:
            New token response
        """
        if not self.state.refresh_token:
            raise Exception("Not logged in")
        
        url = f"{self.api_base}/oauth/token?grant_type=refresh_token&refresh_token={self.state.refresh_token}"
        
        form_data = {
            'profile_id': (None, str(profile_id)),
        }
        
        response = self.session.post(url, files=form_data)
        response.raise_for_status()
        
        data = response.json()
        
        self.state.access_token = data.get('access_token', '')
        self.state.refresh_token = data.get('refresh_token', '')
        self.state.profile_id = profile_id
        
        logger.info(f"Selected profile: {profile_id}")
        
        return data
    
    def get_current_profile(self) -> Dict:
        """
        Get current active profile info.
        
        Returns:
            Current profile data
        """
        url = f"{self.api_base}/v1/profiles/me"
        
        headers = self._add_common_headers({
            'X-Ucp-Language': 'srp',
        })
        
        response = self.session.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    def get_auth_header(self) -> Dict[str, str]:
        """
        Get authorization header for API calls.
        
        Note: EON may use session cookies rather than explicit auth headers
        for most calls after login. This is for cases where it's needed.
        
        Returns:
            Header dict with Authorization
        """
        if not self.state.access_token:
            raise Exception("Not authenticated")
        
        return {
            'Authorization': f'Bearer {self.state.access_token}'
        }


class EONConfig:
    """
    Configuration manager for EON credentials.
    Stores credentials and device info securely.
    """
    
    DEFAULT_CONFIG_PATH = Path.home() / '.eon' / 'config.json'
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH
        self.config = self._load()
    
    def _load(self) -> dict:
        """Load config from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception:
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
    
    def set_credentials(self, username: str, password: str, provider: str = 'sbb'):
        """Store credentials"""
        self.config['username'] = username
        self.config['password'] = password
        self.config['provider'] = provider
        self.save()
    
    def get_credentials(self) -> Tuple[str, str, str]:
        """Get stored credentials (username, password, provider)"""
        return (
            self.config.get('username', ''),
            self.config.get('password', ''),
            self.config.get('provider', 'sbb')
        )
    
    def has_credentials(self) -> bool:
        """Check if credentials are stored"""
        return bool(self.config.get('username') and self.config.get('password'))
    
    def set_device_info(self, device_serial: str, device_number: str):
        """Store device information for reuse"""
        self.config['device_serial'] = device_serial
        self.config['device_number'] = device_number
        self.save()
    
    def get_device_info(self) -> Tuple[str, str]:
        """Get stored device info (serial, device_number)"""
        return (
            self.config.get('device_serial', ''),
            self.config.get('device_number', '')
        )
    
    def has_device_info(self) -> bool:
        """Check if device info is stored"""
        return bool(self.config.get('device_number'))


# Example usage and test
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Check for stored credentials
    config = EONConfig()
    
    if config.has_credentials():
        username, password, provider = config.get_credentials()
        print(f"Using stored credentials for: {username} ({provider})")
    else:
        print("Available providers:")
        for p, info in PROVIDERS.items():
            print(f"  - {p}: {info['name']} ({info['country']})")
        
        provider = input("\nEnter provider (default: sbb): ").strip() or 'sbb'
        username = input("Enter username/email: ").strip()
        password = input("Enter password: ").strip()
        
        save = input("Save credentials for future use? (y/n): ").strip().lower()
        if save == 'y':
            config.set_credentials(username, password, provider)
            print(f"Credentials saved to: {config.config_path}")
    
    try:
        # Initialize auth
        auth = EONAuth(provider=provider)
        
        # Login
        auth.login(username, password)
        
        print(f"\n✓ Authentication successful!")
        print(f"  Device Number: {auth.state.device_number}")
        print(f"  User ID: {auth.state.user_id}")
        print(f"  Profile ID: {auth.state.profile_id}")
        print(f"  Access Token: {auth.state.access_token[:50]}...")
        
        # Save device info for reuse
        config.set_device_info(auth.device_serial, auth.state.device_number)
        
        # Get profiles
        profiles = auth.get_profiles()
        print(f"\n  Profiles ({len(profiles)}):")
        for p in profiles:
            print(f"    - {p.get('profileName', 'Unknown')} (ID: {p.get('id')})")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)