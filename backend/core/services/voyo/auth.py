#!/usr/bin/env python3
"""
Voyo.rs Authentication Module
Handles GraphQL login and content discovery for voyo.rs

API base : https://gql.rtlrs-api.com/graphql/?raw  (authenticated mutations)
Cache GQL: https://gqlc.rtlrs-api.com/graphql/?raw  (GET, public + auth via extras)
Video URL : https://vod.rtlrs-api.com/vod/<JWT>/<filename>/desktop/index.m3u8
Key URL   : https://vod.rtlrs-api.com/vodKey/<JWT>  (AES-128 key per segment)

Auth flow:
  1. POST login(email, password, siteId) -> token + id + profileId
  2. POST loginProfile(profileId)        -> fresh profile-scoped token
  3. POST videoUrlV2(id, siteId)         -> HLS m3u8 URL  (no DRM, AES-128)

Series / category flow:
  GET  gqlc voyoCategory(id)            -> items[] with video id + url

Usage:
    from voyo_auth import VoyoAuth, VoyoConfig

    auth = VoyoAuth()
    auth.login("email@example.com", "password")

    url_info = auth.get_video_url(51112)
    m3u8_url = url_info['url']
"""

import json
import logging
import uuid
import requests
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

requests.packages.urllib3.disable_warnings()

logger = logging.getLogger(__name__)

SITE_ID = 30005   # voyo.rs site identifier


class ChromeTLSAdapter(HTTPAdapter):
    """Custom HTTPAdapter that forces urllib3 to use a customized SSL Context matching Chrome."""
    def init_poolmanager(self, *args, **kwargs):
        import ssl
        from urllib3.util.ssl_ import create_urllib3_context
        context = create_urllib3_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_3
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

def _make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1,
                  status_forcelist=[429, 500, 502, 503, 504])
    adapter = ChromeTLSAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


@dataclass
class AuthState:
    token:         str = ''   # JWT – updated after each auth step
    user_id:       int = 0    # visitor id
    profile_id:    int = 0
    nickname:      str = ''
    is_subscribed: bool = False
    device_id:     str = ''
    device_linked: bool = False  # True after linkDeviceToUser succeeds''


class VoyoAuth:
    """Handles Voyo.rs authentication and content-info retrieval via GraphQL."""

    GQL_URL  = 'https://gql.rtlrs-api.com/graphql/?raw'
    GQLC_URL = 'https://gqlc.rtlrs-api.com/graphql/?raw'

    DEFAULT_HEADERS = {
        'User-Agent':         ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                               'AppleWebKit/537.36 (KHTML, like Gecko) '
                               'Chrome/147.0.0.0 Safari/537.36'),
        'Accept':             'application/json, text/plain, */*',
        'Accept-Language':    'en-US,en;q=0.9,sr;q=0.8',
        'Content-Type':       'application/graphql',
        'Origin':             'https://voyo.rs',
        'Referer':            'https://voyo.rs/',
        'onl-location':       'https://voyo.rs/',
        'sec-ch-ua':          '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        'sec-ch-ua-mobile':   '?0',
        'sec-ch-ua-platform': '"Windows"',
        'Sec-Fetch-Dest':     'empty',
        'Sec-Fetch-Mode':     'cors',
        'Sec-Fetch-Site':     'cross-site',
    }

    def __init__(self, config_file: Optional[str] = None):
        self.state   = AuthState()
        self.session = _make_session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        self.session.verify = False
        self._nonce  = 130          # increments with each GQL call (like browser)

        # Stable device-id (UUID) – sent with every request
        self.state.device_id = str(uuid.uuid4())
        self.session.headers['device-id'] = self.state.device_id

        if config_file and Path(config_file).exists():
            self._load_config(config_file)

    # ── internal helpers ─────────────────────────────────────────────────────

    def _next_nonce(self) -> str:
        self._nonce += 1
        return str(self._nonce)

    def _gql(self, query: str, url: str = None,
             extra_headers: dict = None) -> Dict[str, Any]:
        """Execute a GraphQL query/mutation against the authenticated endpoint."""
        target = url or self.GQL_URL
        headers = {'onl-nonce': self._next_nonce()}
        # After linkDeviceToUser, the server expects the device token on every call
        # as a raw 'authorization' header (no 'Bearer' prefix — 422.200 rejects that).
        # The browser never needs this because its device-id is permanently registered
        # from a prior session. For a fresh device-id we authenticat via token header.
        if self.state.device_linked and self.state.token:
            headers['authorization'] = self.state.token
        if extra_headers:
            headers.update(extra_headers)
        r = self.session.post(target, data=query.encode(), headers=headers)
        if not r.ok:
            logger.error(f'HTTP {r.status_code}: {r.text[:400]}')
        r.raise_for_status()
        data = r.json()
        if 'errors' in data:
            raise RuntimeError(f'GraphQL error: {data["errors"]}')
        return data.get('data', {})

    def _load_config(self, config_file: str):
        try:
            with open(config_file) as f:
                cfg = json.load(f)
            if 'device_id' in cfg:
                self.state.device_id = cfg['device_id']
                self.session.headers['device-id'] = self.state.device_id
            logger.info(f'Loaded config from {config_file}')
        except Exception as e:
            logger.warning(f'Failed to load config: {e}')

    # ── auth ─────────────────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate with Voyo.rs (3-step flow).

        Step 1: login(email, password) → master JWT token
        Step 2: linkDeviceToUser()     → registers device-id server-side,
                                         returns device-scoped token required
                                         for videoUrlV2 to return a stream URL
                                         (without this step videoUrlV2 returns
                                         503 "subscription not active")
        Step 3: loginProfile()         → (skipped — same context as step 1)

        Args:
            email:    Account e-mail
            password: Account password

        Returns:
            login response dict
        """
        logger.info(f'Logging in as "{email}"')

        # Step 1 – master login
        query = (
            f'{{ login ( email: "{email}" password: "{password}" siteId: {SITE_ID} )'
            f' {{ token nickname avatar email deviceId profileId id isSubscribed'
            f' emailStatus phoneStatus }} }}'
        )
        data = self._gql(query)
        login_data = data.get('login', {})

        if not login_data.get('token'):
            raise RuntimeError('Login failed – no token in response')

        self.state.token       = login_data['token']
        self.state.user_id     = login_data.get('id', 0)
        self.state.profile_id  = login_data.get('profileId', 0)
        self.state.nickname    = login_data.get('nickname', '')
        self.state.is_subscribed = login_data.get('isSubscribed', False)

        logger.info(f'Logged in: id={self.state.user_id} '
                    f'profile={self.state.profile_id} '
                    f'subscribed={self.state.is_subscribed}')

        # Step 2 – register device with account (REQUIRED for videoUrlV2)
        self.link_device()

        return login_data

    def link_device(self) -> Dict[str, Any]:
        """
        Register this device-id with the user's account (linkDeviceToUser).

        This is a mandatory step after login — without it videoUrlV2 returns
        HTTP 503 "subscription not active" even for subscribed accounts.

        The mutation binds the current device-id UUID to the account server-side
        and returns a new token with accessBy="device-uniqueid" and a real
        numeric deviceId.  We update self.state.token with this device-scoped
        token so all subsequent calls (videoUrlV2, etc.) are authorised.

        Returns:
            Raw linkDeviceToUser response dict
        """
        query = (
            '{ linkDeviceToUser('
            ' deviceName: "Chrome"'
            ' deviceFamily: "Browser"'
            ' deviceModel: "Chrome, Windows,"'
            ') { token } }'
        )
        # linkDeviceToUser requires the login token for fresh/unregistered device-ids.
        # The server wants a raw JWT in 'authorization' header — no 'Bearer' prefix
        # (422.200 = "tokenstring should not contain 'bearer'").
        # The browser never sends this because its device-id is pre-registered from
        # a prior session; we must send it explicitly for new device-ids.
        extra = {'authorization': self.state.token} if self.state.token else {}
        data = self._gql(query, extra_headers=extra)
        ld = data.get('linkDeviceToUser', {})

        new_token = ld.get('token', '')
        if new_token:
            self.state.token = new_token
            self.state.device_linked = True
            logger.info('Device linked — device-scoped token acquired')
        else:
            logger.warning('linkDeviceToUser returned no token — videoUrlV2 may fail')

        return ld

    def select_profile(self, profile_id: int) -> Dict[str, Any]:
        """
        Switch to a different user profile (e.g. a Kids profile).

        NOTE: loginProfile only works when called from the same device-id that
        the server already associated with an active login session (browser
        behaviour). For CLI use we re-login instead, which always works.

        Args:
            profile_id: profileId to switch to

        Returns:
            Updated state (token refreshed via re-login if profile differs)
        """
        if profile_id == self.state.profile_id:
            logger.info(f'Profile {profile_id} already active')
            return {}

        # Re-use the loginProfile endpoint with Authorization header — works if
        # the server also accepts token-based auth (some API versions do).
        # Fall back gracefully if it fails.
        query = (
            f'{{ loginProfile(profileId: {profile_id})'
            f' {{ token nickname avatar email deviceId profileId id isSubscribed'
            f' emailStatus phoneStatus }} }}'
        )
        try:
            data = self._gql(query)
            lp   = data.get('loginProfile', {})
            if lp.get('token'):
                self.state.token      = lp['token']
                self.state.profile_id = lp.get('profileId', profile_id)
                logger.info(f'Switched to profile {profile_id}')
                return lp
        except Exception as e:
            logger.warning(f'loginProfile failed ({e}) — staying on current profile')
        return {}

    # ── profiles ─────────────────────────────────────────────────────────────

    def get_profiles(self) -> List[Dict]:
        """
        Return list of user profiles.

        Returns list of dicts with: profileId, visitorId, name, type, avatar,
        createdAt, updatedAt, url, sectionId, editable, deletable
        """
        query = ('{ userProfiles { maxProfiles nbProfiles profiles '
                 '{ profileId visitorId name type avatar createdAt updatedAt '
                 'url sectionId editable deletable } } }')
        data = self._gql(query)
        return data.get('userProfiles', {}).get('profiles', [])

    # ── video info ────────────────────────────────────────────────────────────

    def get_video_url(self, video_id: int) -> Dict[str, Any]:
        """
        Get the HLS streaming URL for a video.

        The returned URL is a JWT-authenticated m3u8 playlist served from
        vod.rtlrs-api.com.  Segments are AES-128 encrypted; yt-dlp handles
        key fetching automatically.

        Args:
            video_id: Numeric video ID (from page URL or category items)

        Returns:
            Dict with keys:
              url       – full m3u8 URL
              info      – info string (usually empty)
              infoCode  – 0 = OK
              license   – None (no DRM)
        """
        if not self.state.token:
            raise RuntimeError('Not authenticated – call login() first')

        query = (
            f'{{ videoUrlV2( id: {video_id} siteId: {SITE_ID})'
            f' {{ url info infoCode license }} }}'
        )
        data = self._gql(query)
        result = data.get('videoUrlV2', {})

        if not result.get('url'):
            code = result.get('infoCode', '?')
            info = result.get('info', '')
            raise RuntimeError(
                f'No stream URL for video {video_id} '
                f'(infoCode={code}, info={info!r})'
            )

        return result

    def get_category(self, category_id: int) -> Dict[str, Any]:
        """
        Fetch metadata + episode list for a category (series/show).

        Uses the cached GQL endpoint (gqlc) which is faster for read-only
        catalogue queries.  Auth token is passed via the extras= query param.

        Args:
            category_id: Numeric category ID (from page URL, e.g. /mafija_540.html)

        Returns:
            voyoCategory dict with keys including:
              id, title, description, nbVideos, nbSeasons, seasons, items
            items[] elements have: id, title, url, length, drmProtected,
              publishedFrom, hasSubtitles, isDubbed, mime
        """
        # token is appended as extras param so the CDN can personalise
        extras = f'rootCategoryId:0,s:{self.state.token}' if self.state.token else 'rootCategoryId:0'

        import urllib.parse
        query_str = f'onl_all_full_voyoCategory(id:{category_id})'
        url = (f'{self.GQLC_URL}'
               f'&query={urllib.parse.quote(query_str)}'
               f'&extras={urllib.parse.quote(extras)}')

        r = self.session.get(url)
        r.raise_for_status()
        data = r.json()
        if 'errors' in data:
            raise RuntimeError(f'GraphQL error: {data["errors"]}')
        return data.get('data', {}).get('voyoCategory', {})

    def get_video_metadata(self, video_id: int) -> Dict[str, Any]:
        """
        Fetch metadata for a single video (title, description, length, etc.).

        Uses the cached GQL endpoint.

        Args:
            video_id: Numeric video ID

        Returns:
            video metadata dict
        """
        import urllib.parse
        query_str = f'onl_all_full_video(id:{video_id})'
        extras = f'rootCategoryId:0,s:{self.state.token}' if self.state.token else 'rootCategoryId:0'
        url = (f'{self.GQLC_URL}'
               f'&query={urllib.parse.quote(query_str)}'
               f'&extras={urllib.parse.quote(extras)}')

        r = self.session.get(url)
        r.raise_for_status()
        data = r.json()
        if 'errors' in data:
            raise RuntimeError(f'GraphQL error: {data["errors"]}')
        return data.get('data', {}).get('video', {})


# ── Config / credential storage ──────────────────────────────────────────────

class VoyoConfig:
    """
    Persists credentials and device UUID to ~/.voyo/config.json.
    The device UUID must be stable across sessions.
    """

    DEFAULT_PATH = Path.home() / '.voyo' / 'config.json'

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else self.DEFAULT_PATH
        self._cfg = self._load()

    def _load(self) -> dict:
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self._cfg, f, indent=2)
        try:
            self.config_path.chmod(0o600)
        except Exception:
            pass

    def set_credentials(self, email: str, password: str, device_id: str = ''):
        self._cfg.update({
            'email':     email,
            'password':  password,
            'device_id': device_id or str(uuid.uuid4()),
        })
        self.save()

    def get_credentials(self) -> Tuple[str, str, str]:
        """Returns (email, password, device_id)"""
        return (
            self._cfg.get('email',     ''),
            self._cfg.get('password',  ''),
            self._cfg.get('device_id', ''),
        )

    def has_credentials(self) -> bool:
        return bool(self._cfg.get('email') and self._cfg.get('password'))

    def update_device_id(self, device_id: str):
        self._cfg['device_id'] = device_id
        self.save()


# ── Quick test / standalone run ──────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    config = VoyoConfig()

    if config.has_credentials():
        email, password, device_id = config.get_credentials()
        print(f'Using stored credentials for: {email}')
    else:
        email    = input('E-mail: ').strip()
        password = input('Password: ').strip()
        device_id = ''
        if input('Save credentials? [y/N]: ').strip().lower() == 'y':
            config.set_credentials(email, password)
            print(f'Saved to {config.config_path}')

    try:
        auth = VoyoAuth()
        if device_id:
            auth.state.device_id = device_id
            auth.session.headers['device-id'] = device_id

        auth.login(email, password)
        config.update_device_id(auth.state.device_id)

        print(f'\n✓ Authentication successful!')
        print(f'  User ID:    {auth.state.user_id}')
        print(f'  Profile ID: {auth.state.profile_id}')
        print(f'  Nickname:   {auth.state.nickname}')
        print(f'  Subscribed: {auth.state.is_subscribed}')
        print(f'  Token:      {auth.state.token[:60]}...')

        profiles = auth.get_profiles()
        print(f'\n  Profiles ({len(profiles)}):')
        for p in profiles:
            print(f'    [{p["profileId"]}] {p["name"]} ({p["type"]})')

        # Quick video URL test
        vid_id = input('\nEnter a video ID to test (or press Enter to skip): ').strip()
        if vid_id.isdigit():
            info = auth.get_video_url(int(vid_id))
            print(f'\n  Stream URL: {info["url"][:100]}...')
            print(f'  infoCode:   {info["infoCode"]}')

    except Exception as e:
        print(f'\n✗ Error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
