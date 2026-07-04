"""MCP smoke tests (skill testing reference): auth (401 paths), identity,
serialization, and validation reuse in write tools — no real network."""
import asyncio
import json
from datetime import date, datetime
from decimal import Decimal

import pytest


@pytest.fixture
def mcp_app(app, monkeypatch):
    """Wire the MCP modules to the test app with a configured static key."""
    import mcp_server.context as context

    monkeypatch.setattr(context, "_app", app)
    app.config["SETTINGS"].musterdepot_mcp_key = "test-mcp-schluessel"
    return app


def test_verify_key(mcp_app):
    from mcp_server.auth import verify_key

    assert verify_key("test-mcp-schluessel") == {"benutzer": "einzelnutzer"}
    assert verify_key("falscher-schluessel") is None
    assert verify_key(None) is None
    # Fail closed: no key configured -> every request refused.
    mcp_app.config["SETTINGS"].musterdepot_mcp_key = ""
    assert verify_key("") is None
    assert verify_key("irgendwas") is None


def test_bearer_middleware_401_und_durchlass(mcp_app):
    from mcp_server.http_app import BearerAuthMiddleware

    aufgerufen = []

    async def inner(scope, receive, send):
        aufgerufen.append(True)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = BearerAuthMiddleware(inner)

    async def run(headers):
        antworten = []

        async def send(msg):
            antworten.append(msg)

        await middleware({"type": "http", "headers": headers}, None, send)
        return antworten

    # Missing/invalid key -> 401 with WWW-Authenticate, inner app not called.
    antworten = asyncio.run(run([]))
    assert antworten[0]["status"] == 401
    antworten = asyncio.run(run([(b"authorization", b"Bearer falsch")]))
    assert antworten[0]["status"] == 401
    assert not aufgerufen

    # Valid key -> passes through.
    antworten = asyncio.run(run([(b"authorization", b"Bearer test-mcp-schluessel")]))
    assert antworten[0]["status"] == 200
    assert aufgerufen


def test_authorized_verlangt_identitaet(mcp_app):
    from mcp_server.auth import AuthError, _http_identity, authorized

    with pytest.raises(AuthError):
        with authorized():
            pass

    token = _http_identity.set({"benutzer": "einzelnutzer"})
    try:
        with authorized() as identity:
            assert identity["benutzer"] == "einzelnutzer"
    finally:
        _http_identity.reset(token)


def test_to_jsonable_serialisiert_decimal_und_datum():
    from mcp_server.serialize import to_jsonable

    daten = to_jsonable(
        {
            "betrag": Decimal("12.34"),
            "datum": date(2025, 1, 2),
            "zeit": datetime(2025, 1, 2, 10, 30),
            "liste": [Decimal("1"), None, "text"],
        }
    )
    assert json.dumps(daten)  # fully JSON-serializable
    assert daten["betrag"] == 12.34
    assert daten["datum"] == "2025-01-02"


def test_write_tool_nutzt_dieselbe_validierung(mcp_app):
    """MCP writes go through the identical parse_*/validate_* helpers as the
    web forms (spec §9)."""
    from mcp_server.tools.writes import build_multidict
    from services.kaeufe import parse_kauf

    fields, errors = parse_kauf(
        build_multidict({"instrument_id": 1, "stueck": "-3", "kaufkurs": "100",
                         "kauf_zeitpunkt": "2025-01-02T10:00"})
    )
    assert "fehler.stueck_positiv" in errors

    fields, errors = parse_kauf(
        build_multidict({"instrument_id": 1, "stueck": "3", "kaufkurs": "100,50",
                         "kauf_zeitpunkt": "2025-01-02T10:00"})
    )
    assert errors == []
    assert fields["kaufkurs"] == Decimal("100.50")
