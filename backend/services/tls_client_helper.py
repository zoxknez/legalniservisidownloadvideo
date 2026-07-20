"""
Backward-compatible TLS helpers.

New code should import from backend.services.http_client.
This module re-exports the shared factory so existing callers keep working.
"""
from backend.services.http_client import (  # noqa: F401
    CHROME_CIPHERS,
    ChromeTLSAdapter,
    DEFAULT_IMPERSONATE,
    apply_chrome_fingerprint,
    browser_headers,
    chrome_user_agent,
    create_browser_session,
)

# Legacy name used by older call sites
def apply_curl_cffi_session(impersonate: str = DEFAULT_IMPERSONATE):
    """
    Preferred TLS client when curl_cffi is installed (JA3 fingerprint match).
    Returns a requests-like session or None.
    """
    try:
        from curl_cffi import requests as cffi_requests
        return cffi_requests.Session(impersonate=impersonate)
    except ImportError:
        import logging
        logging.getLogger("TLSClientHelper").debug(
            "curl_cffi not installed; using urllib3 ChromeTLSAdapter"
        )
        return None
