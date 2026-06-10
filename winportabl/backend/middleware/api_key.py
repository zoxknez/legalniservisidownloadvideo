"""
API key authentication for local/LAN deployments.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from backend.server_settings import get_api_key, localhost_bypass_enabled

PUBLIC_PREFIXES = (
    "/static/",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/bridge/",
)

PUBLIC_EXACT = frozenset({"/", "/api/health", "/api/sniffer/detect"})


def _client_is_localhost(request: Request) -> bool:
    if request.client and request.client.host in ("127.0.0.1", "::1", "localhost"):
        return True
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        return first in ("127.0.0.1", "::1")
    return False


def extract_api_key_from_headers(headers, query_params=None) -> str:
    header = headers.get("x-api-key", "").strip()
    if header:
        return header
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    if query_params is not None:
        return query_params.get("api_key", "").strip()
    return ""


def extract_api_key(request: Request) -> str:
    return extract_api_key_from_headers(request.headers, request.query_params)


def _connection_is_localhost(connection) -> bool:
    client = getattr(connection, "client", None)
    if client and client.host in ("127.0.0.1", "::1", "localhost"):
        return True
    headers = getattr(connection, "headers", None)
    if headers:
        forwarded = headers.get("x-forwarded-for", "")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            return first in ("127.0.0.1", "::1")
    return False


def is_authorized(connection) -> bool:
    expected = get_api_key()
    if not expected:
        return True
    if localhost_bypass_enabled() and _connection_is_localhost(connection):
        return True
    headers = connection.headers
    query = getattr(connection, "query_params", None)
    provided = extract_api_key_from_headers(headers, query)
    return secrets_compare(provided, expected)


def secrets_compare(provided: str, expected: str) -> bool:
    import hmac
    return hmac.compare_digest(provided or "", expected or "")


class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in PUBLIC_EXACT or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        if not is_authorized(request):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Neautorizovan pristup. Postavite X-API-Key header ili VIDEODOWNLOAD_API_KEY.",
                    "code": "invalid_api_key",
                },
            )

        return await call_next(request)
