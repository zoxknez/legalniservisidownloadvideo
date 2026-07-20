"""
Shared browser-like HTTP session factory.

Prefer curl_cffi (JA3/TLS impersonation). Fall back to urllib3 ChromeTLSAdapter
when curl_cffi is unavailable. Keeps User-Agent / sec-ch-ua aligned with the
impersonate target so API, CDN, and license calls share one fingerprint profile.
"""
from __future__ import annotations

import logging
import ssl
from typing import Any, Dict, Optional

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.util.ssl_ import create_urllib3_context

logger = logging.getLogger("HttpClient")

# Single source of truth for browser impersonation across all services.
DEFAULT_IMPERSONATE = "chrome131"
CHROME_MAJOR = "131"

CHROME_CIPHERS = (
    "TLS_AES_128_GCM_SHA256:"
    "TLS_AES_256_GCM_SHA384:"
    "TLS_CHACHA20_POLY1305_SHA256:"
    "ECDHE-ECDSA-AES128-GCM-SHA256:"
    "ECDHE-RSA-AES128-GCM-SHA256:"
    "ECDHE-ECDSA-AES256-GCM-SHA384:"
    "ECDHE-RSA-AES256-GCM-SHA384:"
    "ECDHE-ECDSA-CHACHA20-POLY1305:"
    "ECDHE-RSA-CHACHA20-POLY1305"
)

# Known DRM / auth headers captured by the browser bridge (canonical casing).
DRM_HEADER_CANON = {
    "authorization": "Authorization",
    "x-dt-custom-data": "x-dt-custom-data",
    "dt-custom-data": "dt-custom-data",
    "x-ax-drm-message": "x-ax-drm-message",
    "x-license-token": "X-License-Token",
    "x-sky-signature": "X-Sky-Signature",
    "content-type": "Content-Type",
    "origin": "Origin",
    "referer": "Referer",
    "user-agent": "User-Agent",
}


def chrome_user_agent(major: str = CHROME_MAJOR) -> str:
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.0.0 Safari/537.36"
    )


def browser_headers(major: str = CHROME_MAJOR) -> Dict[str, str]:
    return {
        "User-Agent": chrome_user_agent(major),
        "sec-ch-ua": (
            f'"Google Chrome";v="{major}", "Chromium";v="{major}", '
            '"Not_A Brand";v="24"'
        ),
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Accept-Language": "en-US,en;q=0.9",
    }


class ChromeTLSAdapter(HTTPAdapter):
    """urllib3 adapter that approximates Chrome cipher suite order (TLS 1.2–1.3)."""

    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_3
        try:
            context.set_ciphers(CHROME_CIPHERS)
        except Exception as e:
            logger.warning("Failed to set Chrome ciphers: %s", e)
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)


def apply_chrome_fingerprint(session: Any, major: str = CHROME_MAJOR) -> Any:
    """Mount ChromeTLSAdapter and browser Client Hints on a requests.Session."""
    adapter = ChromeTLSAdapter()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(browser_headers(major))
    return session


def normalize_drm_headers(headers: Optional[Dict[str, str]]) -> Dict[str, str]:
    """
    Normalize sniffer/browser DRM headers to stable casing and drop empties.
    Preserves unknown headers with original keys.
    """
    if not headers:
        return {}
    out: Dict[str, str] = {}
    for key, value in headers.items():
        if value is None:
            continue
        val = str(value).strip()
        if not val:
            continue
        canon = DRM_HEADER_CANON.get(str(key).lower().strip())
        out[canon or str(key)] = val
    return out


def create_browser_session(
    *,
    impersonate: str = DEFAULT_IMPERSONATE,
    retries: bool = True,
    verify: bool = True,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Any:
    """
    Build a browser-like session.

    Returns curl_cffi Session when available, otherwise requests.Session with
    ChromeTLSAdapter. Both expose get/post with a requests-compatible surface.
    """
    major = CHROME_MAJOR
    if impersonate and impersonate.startswith("chrome"):
        digits = "".join(ch for ch in impersonate[len("chrome"):] if ch.isdigit())
        if digits:
            major = digits

    session: Any = None
    backend = "requests"

    try:
        from curl_cffi import requests as cffi_requests

        session = cffi_requests.Session(impersonate=impersonate)
        backend = f"curl_cffi:{impersonate}"
    except ImportError:
        import requests

        session = requests.Session()
        if retries:
            retry = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=frozenset(
                    ["HEAD", "GET", "PUT", "POST", "DELETE", "OPTIONS", "TRACE"]
                ),
            )
            adapter = ChromeTLSAdapter(max_retries=retry)
        else:
            adapter = ChromeTLSAdapter()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
    except Exception as e:
        import requests

        logger.warning("curl_cffi session failed (%s); using plain requests", e)
        session = requests.Session()
        apply_chrome_fingerprint(session, major)

    # curl_cffi may not honor session.verify the same way; set when supported.
    try:
        session.verify = verify
    except Exception:
        pass

    session.headers.update(browser_headers(major))
    if extra_headers:
        session.headers.update(extra_headers)

    logger.debug("HTTP session ready via %s (verify=%s)", backend, verify)
    return session


def http_post(
    url: str,
    *,
    data: Any = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 20,
    session: Any = None,
    verify: Optional[bool] = None,
) -> Any:
    """POST helper that uses a provided session or a short-lived browser session."""
    owns = session is None
    sess = session or create_browser_session()
    try:
        kwargs: Dict[str, Any] = {
            "data": data,
            "headers": headers or {},
            "timeout": timeout,
        }
        if verify is not None:
            kwargs["verify"] = verify
        return sess.post(url, **kwargs)
    finally:
        if owns:
            try:
                sess.close()
            except Exception:
                pass
