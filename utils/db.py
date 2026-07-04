"""Access to the request-scoped SQLAlchemy session and app settings.

Inside a request, `create_app()` opens one session per request and stores it
on `g`. Scripts and the MCP server open sessions explicitly via the factory
in `app.config["SESSION_FACTORY"]` (within an app context).
"""
from flask import current_app, g


def current_session():
    """The SQLAlchemy session for the current request/app context."""
    if "db_session" not in g:
        # Outside the request cycle (MCP server, scripts): open lazily and
        # let teardown_appcontext of the caller close it.
        g.db_session = current_app.config["SESSION_FACTORY"]()
    return g.db_session


def current_settings():
    """The pydantic Settings instance the app was created with."""
    return current_app.config["SETTINGS"]
