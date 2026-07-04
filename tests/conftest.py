"""Shared fixtures: dual-backend app (SQLite always, MariaDB when
`TEST_MARIADB_URL` is reachable), test client, service context, fake
providers and the requirements-traceability matrix writer.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from tests.fixtures import fakes

BACKENDS = ["sqlite"]
if os.getenv("TEST_MARIADB_URL"):
    BACKENDS.append("mariadb")


def _mariadb_erreichbar(url: str) -> bool:
    try:
        engine = create_engine(url, future=True)
        with engine.connect():
            return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture(params=BACKENDS)
def db_url(request):
    if request.param == "sqlite":
        return "sqlite:///:memory:"
    url = os.environ["TEST_MARIADB_URL"]
    if not _mariadb_erreichbar(url):
        pytest.skip("MariaDB not reachable")
    return url


@pytest.fixture
def app(db_url):
    from app import create_app
    from domain.entities import Base
    from settings import Settings

    fakes.registriere_fakes()
    fakes.fake_aktien.reset()
    fakes.fake_hebel.reset()
    fakes.fake_fx.reset()

    backend = "mariadb" if db_url.startswith("mariadb") else "sqlite"
    settings = Settings(
        db_backend=backend,
        db_url=db_url,
        secret_key="test-only",
        credentials_enc_key="test-verschluesselungs-schluessel",
        # Route to the fakes; never real FMP/TR in tests (spec §10).
        provider_aktien_etf="fake_aktien",
        provider_hebelprodukt="fake_hebel",
        fx_provider="fake_fx",
        fmp_api_key="",
        kurs_cache_ttl=0,  # always ask the (fake) provider — deterministic
        seed_on_startup=False,
        _env_file=None,
    )
    application = create_app(settings)
    application.config["WTF_CSRF_ENABLED"] = False
    engine = application.config["DB_PROVIDER"].engine()
    Base.metadata.create_all(engine)
    yield application
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def svc(app):
    """Request context with an open DB session for direct service calls."""
    from flask import g

    ctx = app.test_request_context()
    ctx.push()
    g.db_session = app.config["SESSION_FACTORY"]()
    yield g.db_session
    g.db_session.close()
    ctx.pop()


# --------------------------------------------------------------------------
# Requirements-traceability matrix (skill testing reference)
# --------------------------------------------------------------------------
_ERGEBNISSE: dict[str, list[tuple[str, str]]] = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    ausgang = yield
    bericht = ausgang.get_result()
    if bericht.when != "call":
        return
    for marker in item.iter_markers(name="requirement"):
        req_id = marker.args[0] if marker.args else "?"
        _ERGEBNISSE.setdefault(req_id, []).append((item.nodeid, bericht.outcome))


def pytest_sessionfinish(session, exitstatus):
    if not _ERGEBNISSE:
        return
    ziel = Path("reports")
    ziel.mkdir(exist_ok=True)
    zeilen = ["# Requirements-Traceability-Matrix", ""]
    zeilen.append("| Requirement | Test | Ergebnis |")
    zeilen.append("|---|---|---|")
    for req_id in sorted(_ERGEBNISSE):
        for nodeid, outcome in _ERGEBNISSE[req_id]:
            zeilen.append(f"| {req_id} | `{nodeid}` | {outcome} |")
    (ziel / "requirements-matrix.md").write_text("\n".join(zeilen) + "\n", encoding="utf-8")
