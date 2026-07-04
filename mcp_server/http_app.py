"""ASGI app with Bearer-auth middleware (pure ASGI, per the skill's MCP ref).

Every request must carry `Authorization: Bearer <key>`; the key is verified
per request. Missing/invalid key -> 401. Bind to 127.0.0.1 and terminate TLS
at a reverse proxy — bearer tokens never travel over cleartext HTTP.
"""
from __future__ import annotations

import json

from mcp_server.auth import _http_identity, verify_key


def _extract_bearer(headers) -> str | None:
    for name, value in headers:
        if name.lower() == b"authorization":
            text = value.decode("latin-1")
            if text.lower().startswith("bearer "):
                return text[7:].strip()
    return None


async def _send_401(send):
    body = json.dumps({"error": "unauthorized"}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"www-authenticate", b"Bearer"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BearerAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        token = _extract_bearer(scope.get("headers") or [])
        identity = verify_key(token)
        if identity is None:
            await _send_401(send)
            return
        reset = _http_identity.set(identity)
        try:
            await self.app(scope, receive, send)
        finally:
            _http_identity.reset(reset)


def build_asgi_app():
    from mcp_server.server import mcp

    return BearerAuthMiddleware(mcp.streamable_http_app())
