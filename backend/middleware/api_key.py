"""
API key authentication for local/LAN deployments.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
import time
import secrets
from typing import Dict

from backend.server_settings import get_api_key, localhost_bypass_enabled

PUBLIC_PREFIXES = (
    "/static/",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/bridge/",
)

PUBLIC_EXACT = frozenset({"/", "/api/health", "/api/sniffer/detect", "/favicon.ico"})


_ws_tickets: Dict[str, float] = {}
TICKET_TTL = 15.0  # seconds


def create_ws_ticket() -> str:
    token = secrets.token_urlsafe(32)
    _ws_tickets[token] = time.time() + TICKET_TTL
    return token


def verify_ws_ticket(token: str) -> bool:
    now = time.time()
    # Cleanup expired tickets
    expired = [t for t, exp in list(_ws_tickets.items()) if exp < now]
    for t in expired:
        _ws_tickets.pop(t, None)

    if token in _ws_tickets:
        _ws_tickets.pop(token)  # single use
        return True
    return False


def _client_is_localhost(request: Request) -> bool:
    if request.client and request.client.host in ("127.0.0.1", "::1", "localhost"):
        return True
    return False


def extract_api_key_from_headers(headers) -> str:
    header = headers.get("x-api-key", "").strip()
    if header:
        return header
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def extract_api_key(request: Request) -> str:
    return extract_api_key_from_headers(request.headers)


def _connection_is_localhost(connection) -> bool:
    client = getattr(connection, "client", None)
    if client and client.host in ("127.0.0.1", "::1", "localhost"):
        return True
    return False


def is_authorized(connection) -> bool:
    expected = get_api_key()
    if not expected:
        return True
    if localhost_bypass_enabled() and _connection_is_localhost(connection):
        return True

    # Check WebSocket ticket in query string
    query = getattr(connection, "query_params", None)
    if query:
        ticket = query.get("ticket", "").strip()
        if ticket and verify_ws_ticket(ticket):
            return True

    headers = connection.headers
    provided = extract_api_key_from_headers(headers)
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
