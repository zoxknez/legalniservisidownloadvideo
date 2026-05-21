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


def _make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1,
                  status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
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
    device_linked: bool = False


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
        self._nonce  = 130

        self.state.device_id = str(uuid.uuid4())
        self.session.headers['device-id'] = self.state.device_id

        if config_file and Path(config_file).exists():
            self._load_config(config_file)

    def _next_nonce(self) -> str:
        self._nonce += 1
        return str(self._nonce)

    def _gql(self, query: str, url: str = None,
             extra_headers: dict = None) -> Dict[str, Any]:
        """Execute a GraphQL query/mutation against the authenticated endpoint."""
        target = url or self.GQL_URL
        headers = {'onl-nonce': self._next_nonce()}
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

    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate with Voyo.rs (3-step flow)."""
        logger.info(f'Logging in as "{email}"')

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

        self.link_device()
        return login_data

    def link_device(self) -> Dict[str, Any]:
        """Register this device-id with the user's account."""
        query = (
            '{ linkDeviceToUser('
            ' deviceName: "Chrome"'
            ' deviceFamily: "Browser"'
            ' deviceModel: "Chrome, Windows,"'
            ') { token } }'
        )
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

    def get_profiles(self) -> List[Dict]:
        """Return list of user profiles."""
        query = ('{ userProfiles { maxProfiles nbProfiles profiles '
                 '{ profileId visitorId name type avatar createdAt updatedAt '
                 'url sectionId editable deletable } } }')
        data = self._gql(query)
        return data.get('userProfiles', {}).get('profiles', [])

    def get_video_url(self, video_id: int) -> Dict[str, Any]:
        """Get the HLS streaming URL for a video."""
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
        """Fetch metadata + episode list for a category (series/show)."""
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
        """Fetch metadata for a single video."""
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


class VoyoConfig:
    """Persists credentials and device UUID to ~/.voyo/config.json."""

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
        self.config_path.chmod(0o600)

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
