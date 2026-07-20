#!/usr/bin/env python3
"""
SkyShowtime Authentication Module

Auth flow:
  1. Load browser cookies from a Netscape cookies.txt or browser sync dict
  2. POST to ovp.skyshowtime.com/auth/tokens with those cookies → userToken
  3. Cache userToken for subsequent downloads
"""

import base64
import hashlib
import hmac as _hmac
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 20


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class SkyConfig:
    PROPOSITION      = "SKYSHOWTIME"
    PROVIDER         = "SKYSHOWTIME"
    TERRITORY        = "RS"
    ACTIVE_TERRITORY = "RS"
    LANGUAGE         = "en-US"
    PLATFORM         = "ANDROID"
    DEVICE           = "MOBILE"
    AUTH_SCHEME      = "MESSO"
    AUTH_ISSUER      = "NOWTV"
    DRM_DEVICE_ID    = "UNKNOWN"
    DEVICE_ID        = "Ptudy2gGV4nNa9nUyFbl"
    HMAC_KEY         = "jfj9qGg6aDHaBbFpH6wNEvN6cHuHtZVppHRvBgZs"
    CLIENT_SDK       = "SKYSHOWTIME-ANDROID-v1"
    SIG_VERSION      = "1.0"
    SIG_FORMAT       = 'SkyOTT client="{client}",signature="{signature}",timestamp="{timestamp}",version="1.0"'

    CACHE_DIR   = Path.home() / ".skyshowtime"
    TOKEN_CACHE = CACHE_DIR / "tokens.json"
    CRED_FILE   = CACHE_DIR / "config.json"
    COOKIE_FILE = CACHE_DIR / "cookies.txt"


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def _make_session() -> requests.Session:
    from backend.services.http_client import create_browser_session

    s = create_browser_session(
        extra_headers={
            "Origin": "https://www.skyshowtime.com",
            "Referer": "https://www.skyshowtime.com/",
        }
    )
    return s


# ---------------------------------------------------------------------------
# HMAC signature
# ---------------------------------------------------------------------------

class SkySignature:
    def __init__(self, key: str = SkyConfig.HMAC_KEY):
        self._key = key.encode("utf-8")

    @staticmethod
    def _header_md5(headers: Dict[str, str]) -> str:
        if headers:
            text = "\n".join(f"{k.lower()}: {v}"
                             for k, v in headers.items()) + "\n"
        else:
            text = "{}"
        return hashlib.md5(text.encode()).hexdigest()

    @staticmethod
    def _body_md5(body: str) -> str:
        return hashlib.md5(body.encode()).hexdigest()

    def sign(self, method: str, path: str,
             sky_headers: Dict[str, str], body: str,
             timestamp: Optional[int] = None) -> str:
        if timestamp is None:
            timestamp = int(time.time())

        msg = "\n".join([
            method.upper(),
            path,
            "",
            SkyConfig.CLIENT_SDK,
            SkyConfig.SIG_VERSION,
            self._header_md5(sky_headers),
            str(timestamp),
            self._body_md5(body),
        ]) + "\n"

        digest = _hmac.new(self._key, msg.encode("utf-8"), hashlib.sha1).digest()
        sig_b64 = base64.b64encode(digest).decode()

        return SkyConfig.SIG_FORMAT.format(
            client=SkyConfig.CLIENT_SDK,
            signature=sig_b64,
            timestamp=timestamp,
        )


# ---------------------------------------------------------------------------
# Auth state
# ---------------------------------------------------------------------------

def _gen_device_id() -> str:
    return base64.urlsafe_b64encode(uuid.uuid4().bytes)[:20].decode().rstrip("=")


@dataclass
class AuthState:
    device_id:    str = field(default_factory=lambda: SkyConfig.DEVICE_ID)
    persona_id:   str = ""
    user_token:   str = ""
    token_expiry: str = ""
    territory:    str = ""

    def is_valid(self) -> bool:
        if not self.user_token:
            return False
        if self.token_expiry:
            try:
                exp = datetime.fromisoformat(
                    self.token_expiry.replace("Z", "+00:00"))
                return exp > datetime.now(timezone.utc)
            except ValueError:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id":    self.device_id,
            "persona_id":   self.persona_id,
            "user_token":   self.user_token,
            "token_expiry": self.token_expiry,
            "territory":    self.territory,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuthState":
        obj = cls.__new__(cls)
        obj.device_id    = d.get("device_id",    SkyConfig.DEVICE_ID)
        obj.persona_id   = d.get("persona_id",   "")
        obj.user_token   = d.get("user_token",   "")
        obj.token_expiry = d.get("token_expiry", "")
        obj.territory    = d.get("territory",    "")
        return obj


def _default_territory() -> str:
    try:
        from backend.config import config
        t = str(config.get_credentials("skyshowtime").get("territory") or "").strip().upper()
        if t:
            return t
    except Exception:
        pass
    return SkyConfig.TERRITORY


# ---------------------------------------------------------------------------
# Main auth class
# ---------------------------------------------------------------------------

class SkyShowtimeAuth:
    """Authenticates to SkyShowtime using browser cookies."""

    def __init__(self, territory: Optional[str] = None):
        self.territory = (territory or _default_territory()).upper()
        self.session   = _make_session()
        self.state     = AuthState()
        self.signer    = SkySignature()
        self._load_cache()

    def login_with_cookies(self, cookie_file: str) -> None:
        """Load Netscape cookies.txt file and exchange for userToken."""
        self._load_cookies(cookie_file)
        SkyConfig.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        dest = str(SkyConfig.COOKIE_FILE)
        if str(Path(cookie_file).resolve()) != str(Path(dest).resolve()):
            import shutil
            shutil.copy2(cookie_file, dest)
            try:
                Path(dest).chmod(0o600)
            except OSError:
                pass
            logger.info(f"Cookies saved to {dest}")
        self.state.persona_id = self._get_persona_id()
        self._get_ovp_token()
        self._save_cache()
        logger.info("Login sa cookies.txt uspešan.")

    def login_with_cookie_dict(self, cookies: Dict[str, str]) -> None:
        """Authenticate using a dict of cookie name/values (e.g. from browser sync)."""
        count = 0
        for name, value in cookies.items():
            if not value:
                continue
            for domain in ("skyshowtime.com", ".skyshowtime.com", "skyott.com", ".skyott.com"):
                self.session.cookies.set(name, value, domain=domain)
            count += 1
        logger.info(f"Uvezeno {count} kolačića iz rečnika pretraživača.")
        self.state.persona_id = self._get_persona_id()
        self._get_ovp_token()
        self._save_cache()
        logger.info("Login sa pretraživač kolačićima uspešan.")

    def ensure_authenticated(self) -> None:
        """Refresh token if expired."""
        if self.state.is_valid():
            return
        logger.info("Token istekao – osvežavam sesiju …")
        if SkyConfig.COOKIE_FILE.exists():
            self._load_cookies(str(SkyConfig.COOKIE_FILE))
        self.state.persona_id = self._get_persona_id()
        self._get_ovp_token()
        self._save_cache()

    def is_authenticated(self) -> bool:
        return self.state.is_valid()

    def _load_cookies(self, cookie_file: str) -> None:
        """Load a Netscape/Mozilla cookies.txt into the requests session."""
        path = Path(cookie_file)
        if not path.exists():
            raise FileNotFoundError(f"Cookie fajl nije pronađen: {cookie_file}")

        jar = MozillaCookieJar(str(path))
        jar.load(ignore_discard=True, ignore_expires=True)

        count = 0
        for cookie in jar:
            if "skyshowtime" in cookie.domain or "skyott" in cookie.domain:
                self.session.cookies.set(
                    cookie.name, cookie.value, domain=cookie.domain)
                count += 1

        if count == 0:
            for cookie in jar:
                self.session.cookies.set(
                    cookie.name, cookie.value, domain=cookie.domain)
            count = len(list(jar))

        logger.info(f"Učitano {count} kolačića iz {cookie_file}")

    def _get_persona_id(self) -> str:
        """POST to BFF personas using browser cookies."""
        resp = self.session.post(
            "https://web.clients.skyshowtime.com/bff/personas/v2",
            params={"in_setup": "false"},
            headers={
                "Content-Type":             "application/json",
                "Accept":                   "application/json",
                "X-SkyOTT-Platform":        SkyConfig.PLATFORM,
                "X-SkyOTT-ActiveTerritory": self.territory,
                "X-SkyOTT-Provider":        SkyConfig.PROVIDER,
                "X-SkyOTT-Proposition":     SkyConfig.PROPOSITION,
                "X-SkyOTT-Device":          SkyConfig.DEVICE,
                "X-SkyOTT-Language":        SkyConfig.LANGUAGE,
                "X-SkyOTT-Territory":       self.territory,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        personas = data.get("personas", [])
        if not personas:
            raise RuntimeError("Nema persona sa ovim kolačićima – proverite nalog.")

        persona_id = personas[0]["id"]
        for p in personas:
            if p.get("isAccountHolder"):
                persona_id = p["id"]
                t = (p.get("providerTerritory") or
                     p.get("homeTerritory") or
                     p.get("currentLocationTerritory"))
                if t:
                    self.territory = t.upper()
                    logger.info(f"Teritorija iz naloga: {self.territory}")
                break

        return persona_id

    def _get_ovp_token(self) -> None:
        if not self.state.persona_id:
            self.state.persona_id = self._get_persona_id()

        sky_headers = {
            "x-skyott-Activeterritory": self.territory,
            "x-skyott-device":          SkyConfig.DEVICE,
            "x-skyott-language":        SkyConfig.LANGUAGE,
            "x-skyott-platform":        SkyConfig.PLATFORM,
            "x-skyott-proposition":     SkyConfig.PROPOSITION,
            "x-skyott-provider":        SkyConfig.PROVIDER,
            "x-skyott-territory":       self.territory,
        }

        body = json.dumps({
            "auth": {
                "authScheme":        SkyConfig.AUTH_SCHEME,
                "authIssuer":        SkyConfig.AUTH_ISSUER,
                "provider":          SkyConfig.PROVIDER,
                "providerTerritory": self.territory,
                "proposition":       SkyConfig.PROPOSITION,
                "personaId":         self.state.persona_id,
            },
            "device": {
                "type":        SkyConfig.DEVICE,
                "platform":    SkyConfig.PLATFORM,
                "id":          self.state.device_id,
                "drmDeviceId": SkyConfig.DRM_DEVICE_ID,
            },
        }, separators=(",", ":"))

        ts  = int(time.time())
        sig = self.signer.sign("POST", "/auth/tokens", sky_headers, body, ts)

        resp = self.session.post(
            "https://ovp.skyshowtime.com/auth/tokens",
            data=body,
            headers={
                **sky_headers,
                "Accept":          "application/vnd.tokens.v1+json",
                "Content-Type":    "application/vnd.tokens.v1+json",
                "X-Sky-Signature": sig,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        tokens = resp.json()

        if "errorCode" in tokens:
            raise RuntimeError(
                f"OVP token error: {tokens.get('description')} [{tokens['errorCode']}]"
            )

        self.state.user_token   = tokens.get("userToken", "")
        self.state.token_expiry = tokens.get("tokenExpiryTime", "")

        if not self.state.user_token:
            raise RuntimeError(f"Nema userToken u odgovoru: {tokens}")

    def sky_headers_with_token(self) -> Dict[str, str]:
        """Sky headers for signed requests that include the userToken."""
        return {
            "x-skyott-Activeterritory": self.territory,
            "x-skyott-agent": ".".join([
                SkyConfig.PROPOSITION.lower(),
                SkyConfig.DEVICE.lower(),
                SkyConfig.PLATFORM.lower(),
            ]),
            "x-skyott-device":          SkyConfig.DEVICE,
            "x-skyott-language":        SkyConfig.LANGUAGE,
            "x-skyott-platform":        SkyConfig.PLATFORM,
            "x-skyott-proposition":     SkyConfig.PROPOSITION,
            "x-skyott-provider":        SkyConfig.PROVIDER,
            "x-skyott-territory":       self.territory,
            "x-skyott-usertoken":       self.state.user_token,
        }

    def _load_cache(self) -> None:
        if SkyConfig.TOKEN_CACHE.exists():
            try:
                with open(SkyConfig.TOKEN_CACHE) as f:
                    self.state = AuthState.from_dict(json.load(f))
                if self.state.territory:
                    self.territory = self.state.territory.upper()
                if self.state.is_valid():
                    logger.info("Učitan validan keširani token.")
            except Exception as e:
                logger.debug(f"Neuspešno učitavanje keša: {e}")

    def _save_cache(self) -> None:
        self.state.territory = self.territory
        SkyConfig.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(SkyConfig.TOKEN_CACHE, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)
        try:
            SkyConfig.TOKEN_CACHE.chmod(0o600)
        except OSError:
            pass
        try:
            from backend.services.skyshowtime_adapter import SkyShowtimeAdapter

            SkyShowtimeAdapter.sync_auth_to_config(self)
        except Exception as exc:
            logger.debug("SkyShowtime config sync skipped: %s", exc)


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="SkyShowtime auth cli")
    parser.add_argument("-c", "--cookies", help="Path to Netscape cookies.txt")
    parser.add_argument("--territory", default=SkyConfig.TERRITORY, help="Territory code")
    args = parser.parse_args()

    auth = SkyShowtimeAuth(territory=args.territory)

    if auth.is_authenticated():
        print("Already authenticated (cached token is still valid).")
        print(f"  User Token : {auth.state.user_token[:40]}…")
        print(f"  Expires    : {auth.state.token_expiry}")
        sys.exit(0)

    cookie_file = args.cookies
    if not cookie_file:
        if SkyConfig.COOKIE_FILE.exists():
            cookie_file = str(SkyConfig.COOKIE_FILE)
            logger.info(f"Using saved cookies from {cookie_file}")
        else:
            print("\nNo cached token and no cookies provided.")
            print("Run:  python skyshowtime_auth.py --cookies cookies.txt\n")
            sys.exit(1)

    try:
        auth.login_with_cookies(cookie_file)
        print(f"\n✓ Authenticated!")
        print(f"  User Token : {auth.state.user_token[:40]}…")
        print(f"  Expires    : {auth.state.token_expiry}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
