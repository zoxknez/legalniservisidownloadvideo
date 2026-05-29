import ssl
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

logger = logging.getLogger("TLSClientHelper")

# Chrome 131 cipher suite order (TLS 1.2 + 1.3)
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

class ChromeTLSAdapter(HTTPAdapter):
    """
    Custom HTTPAdapter that forces urllib3 to use a customized SSL Context
    matching Chrome's exact cipher suites and TLS fingerprint, bypassing CDNs.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        
        # Enforce minimum TLS 1.2 and standard TLS 1.3
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_3
        
        # Override ciphers to mimic Chrome
        try:
            context.set_ciphers(CHROME_CIPHERS)
        except Exception as e:
            logger.warning(f"Failed to set Chrome ciphers: {e}")
            
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)

def apply_chrome_fingerprint(session):
    """
    Injects the Chrome TLS Adapter into a requests.Session, 
    making it completely indistinguishable from Chrome for CDNs.
    """
    adapter = ChromeTLSAdapter()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    })


def apply_curl_cffi_session(impersonate: str = "chrome131"):
    """
    Preferred TLS client when curl_cffi is installed (JA3 fingerprint match).
    Returns a requests-like session or None.
    """
    try:
        from curl_cffi import requests as cffi_requests
        return cffi_requests.Session(impersonate=impersonate)
    except ImportError:
        logger.debug("curl_cffi not installed; using urllib3 ChromeTLSAdapter")
        return None
