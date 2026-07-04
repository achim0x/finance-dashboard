"""Identity & authorization for MCP tools.

Single-user app without login (spec §2), so the skill's per-user key model
is reduced to ONE static bearer key from the env (`MUSTERDEPOT_MCP_KEY`,
spec §9). The key is compared in constant time; no key configured means the
server refuses every request (fail closed). Run behind TLS only.
"""
from __future__ import annotations

import secrets
from contextlib import contextmanager
from contextvars import ContextVar

from mcp_server.context import get_app

_http_identity: ContextVar[dict | None] = ContextVar("mcp_http_identity", default=None)


class AuthError(Exception):
    pass


def verify_key(token: str | None) -> dict | None:
    """Static-key check; returns the single-user identity or None."""
    app = get_app()
    konfiguriert = app.config["SETTINGS"].musterdepot_mcp_key
    if not konfiguriert or not token:
        return None
    if not secrets.compare_digest(token, konfiguriert):
        return None
    return {"benutzer": "einzelnutzer"}


@contextmanager
def authorized():
    """Tool guard: verified identity + Flask app context + DB session."""
    identity = _http_identity.get()
    if identity is None:
        raise AuthError("No authenticated request (missing/invalid API key).")
    app = get_app()
    with app.app_context():
        from flask import g

        g.db_session = app.config["SESSION_FACTORY"]()
        try:
            yield identity
        finally:
            g.db_session.close()
