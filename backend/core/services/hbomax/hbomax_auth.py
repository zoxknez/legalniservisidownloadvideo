#!/usr/bin/env python3
"""
HBO Max (Max) Authentication Module

Auth flow:
  1. POST /ara/v1/oauth2/device_code  -> device_code, user_code, verification_uri
  2. User visits verification_uri and enters user_code
  3. Poll POST /ara/v1/oauth2/token   -> access_token, refresh_token
  4. Token saved to ~/.hbomax/token.json

Token path: ~/.hbomax/token.json
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

TOKEN_DIR  = Path.home() / ".hbomax"
TOKEN_FILE = TOKEN_DIR / "token.json"

# SlyGuy-compatible client IDs per market
_CLIENT_IDS: Dict[str, str] = {
    "emea": "b012b6d7-f29b-4574-8981-28b8428ead5d",
    "latam": "0a42a31e-0f6c-432e-9e2e-8c1dca3e1fd1",
    "us":    "585b89fb-deff-45c6-a8f3-e03d18f77ec4",
}

# One API base that works for all markets
API_BASE    = "https://default.any-any.prd.api.max.com/ara"
AUTH_URL    = f"{API_BASE}/v1/oauth2"
DEVICE_CODE_URL = f"{AUTH_URL}/device_code"
TOKEN_URL   = f"{AUTH_URL}/token"

DEVICE_CODE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"

# Request defaults
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json",
}


# ── Token helpers ──────────────────────────────────────────────────────────────

def load_token() -> Dict[str, Any]:
    """Load token from disk. Returns empty dict if missing or corrupt."""
    for path in (TOKEN_FILE, Path(__file__).with_name(".hbomax_token.json")):
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("access_token"):
                    logger.debug(f"Loaded token from {path}")
                    return data
            except (OSError, json.JSONDecodeError):
                pass
    return {}


def save_token(data: Dict[str, Any]) -> None:
    """Persist token to ~/.hbomax/token.json."""
    try:
        TOKEN_DIR.mkdir(parents=True, exist_ok=True)
        with TOKEN_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        try:
            TOKEN_FILE.chmod(0o600)
        except OSError:
            pass
        logger.info(f"Token saved to {TOKEN_FILE}")
    except OSError as e:
        # Fallback: save next to the script
        fallback = Path(__file__).with_name(".hbomax_token.json")
        with fallback.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.warning(f"Could not write to {TOKEN_FILE}: {e}. Saved to {fallback}")


def is_token_valid(token: Dict[str, Any]) -> bool:
    """Return True if token exists and is not obviously expired."""
    if not token.get("access_token"):
        return False
    expires_at = token.get("expires_at", 0)
    if expires_at and time.time() > expires_at - 60:
        return False
    return True


# ── OAuth device-code flow ────────────────────────────────────────────────────

class HBOMaxAuth:
    """
    Handles HBO Max / Max OAuth 2.0 device-code authentication.

    Usage:
        auth = HBOMaxAuth(market="emea")
        auth.login()       # interactive device-code login
        token = auth.get_access_token()
    """

    def __init__(self, market: str = "emea"):
        self.market = market.lower()
        self.client_id = _CLIENT_IDS.get(self.market, _CLIENT_IDS["emea"])
        self._token: Dict[str, Any] = {}

        # Import here so other modules can import hbomax_auth without curl_cffi
        try:
            from curl_cffi import requests as cffi_requests
            self._session = cffi_requests.Session(impersonate="chrome124")
        except ImportError:
            import requests as std_requests
            self._session = std_requests.Session()
            logger.warning("curl_cffi not found; falling back to standard requests (may fail TLS fingerprint check)")

    # ── public API ────────────────────────────────────────────────────────────

    def login(self) -> None:
        """
        Interactive device-code login.
        Instructs the user to open a URL and enter a code, then polls until
        authenticated.  Saves the token on success.
        """
        logger.info("Starting HBO Max device-code login …")
        resp = self._request_device_code()

        device_code      = resp["device_code"]
        user_code        = resp["user_code"]
        verification_uri = resp.get("verification_uri_complete") or resp.get("verification_uri")
        interval         = int(resp.get("interval", 5))
        expires_in       = int(resp.get("expires_in", 300))

        print(f"\n{'='*60}")
        print(f"  Otvorite u browseru: {verification_uri}")
        print(f"  Unesite kod:         {user_code}")
        print(f"{'='*60}\n")
        print("Čekam da se logujete …")

        token = self._poll_for_token(device_code, interval, expires_in)
        self._token = token
        save_token(token)
        print("\n✓ Uspešno prijavljeni na HBO Max!")

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing if needed."""
        token = self._token or load_token()
        if not is_token_valid(token):
            token = self._refresh(token)
        self._token = token
        return token["access_token"]

    def get_auth_headers(self) -> Dict[str, str]:
        """Return Authorization header dict."""
        return {"Authorization": f"Bearer {self.get_access_token()}"}

    def is_authenticated(self) -> bool:
        """Return True if a valid token is available (on disk or in memory)."""
        token = self._token or load_token()
        if is_token_valid(token):
            self._token = token
            return True
        # Try refresh
        if token.get("refresh_token"):
            try:
                refreshed = self._refresh(token)
                self._token = refreshed
                return True
            except Exception:
                pass
        return False

    # ── private helpers ───────────────────────────────────────────────────────

    def _request_device_code(self) -> Dict[str, Any]:
        data = {
            "client_id": self.client_id,
            "scope":     "browse video_playback_free",
        }
        resp = self._session.post(DEVICE_CODE_URL, data=data, headers=_HEADERS, timeout=15)
        self._raise_for_status(resp, "device_code")
        return resp.json()

    def _poll_for_token(self, device_code: str, interval: int, expires_in: int) -> Dict[str, Any]:
        deadline = time.time() + expires_in
        data = {
            "client_id":   self.client_id,
            "device_code": device_code,
            "grant_type":  DEVICE_CODE_GRANT,
        }
        while time.time() < deadline:
            time.sleep(interval)
            resp = self._session.post(TOKEN_URL, data=data, headers=_HEADERS, timeout=15)
            body = resp.json()
            if resp.status_code == 200 and body.get("access_token"):
                body["expires_at"] = time.time() + int(body.get("expires_in", 3600))
                body["market"] = self.market
                return body
            error = body.get("error", "")
            if error == "authorization_pending":
                print(".", end="", flush=True)
                continue
            if error == "slow_down":
                interval += 5
                continue
            if error in ("access_denied", "expired_token"):
                raise RuntimeError(f"Login odbijen ili istekao: {error}")
            # Other errors — still retry
            logger.debug(f"Poll response: {body}")
        raise TimeoutError("Vreme za login je isteklo. Pokrenite ponovo.")

    def _refresh(self, token: Dict[str, Any]) -> Dict[str, Any]:
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("Nema refresh tokena. Pokrenite --login ponovo.")
        data = {
            "client_id":     self.client_id,
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
        }
        resp = self._session.post(TOKEN_URL, data=data, headers=_HEADERS, timeout=15)
        self._raise_for_status(resp, "refresh")
        body = resp.json()
        if not body.get("access_token"):
            raise RuntimeError(f"Refresh tokena nije uspeo: {body}")
        body["expires_at"] = time.time() + int(body.get("expires_in", 3600))
        body["market"] = token.get("market", self.market)
        # Preserve refresh_token if not returned
        if not body.get("refresh_token") and token.get("refresh_token"):
            body["refresh_token"] = token["refresh_token"]
        save_token(body)
        logger.info("Token osvežen.")
        return body

    @staticmethod
    def _raise_for_status(resp: Any, context: str) -> None:
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text[:200]
            raise RuntimeError(f"HBO Max API greška ({context}) HTTP {resp.status_code}: {detail}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="HBO Max authentication")
    parser.add_argument("--login",  action="store_true", help="Pokrenuti device-code login")
    parser.add_argument("--market", default="emea", help="Market (emea/latam/us)")
    parser.add_argument("--status", action="store_true", help="Proveriti status autentikacije")
    args = parser.parse_args()

    auth = HBOMaxAuth(market=args.market)

    if args.login:
        auth.login()
    elif args.status:
        if auth.is_authenticated():
            print("✓ Prijavljen na HBO Max.")
        else:
            print("✗ Niste prijavljeni. Pokrenite --login.")
            sys.exit(1)
    else:
        parser.print_help()
