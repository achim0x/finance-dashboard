"""create_app() factory for the Finance Dashboard (Musterdepot).

Wires settings -> extensions -> DB session lifecycle -> blueprints ->
context processor -> error handling. Both run.py (dev) and wsgi.py (prod)
call this factory. There is no authentication: the app is single-user by
design (spec §2); hardening hooks remain available through the skill.
"""
import logging
from datetime import timedelta

from flask import Flask, g, render_template

from settings import Settings
from extensions import csrf
from infrastructure.persistence.provider import (
    build_database_provider,
    build_session_factory,
)
from blueprints import register_blueprints
from utils.app_context import register_context
from utils.formatters import register_filters
from utils.i18n import register_i18n


def create_app(settings: "Settings | None" = None) -> Flask:
    settings = settings or Settings()

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.secret_key = settings.secret_key
    app.permanent_session_lifetime = timedelta(days=1)
    app.config["SETTINGS"] = settings

    logging.basicConfig(level=settings.log_level)

    # --- Extensions ---
    # CSRF tokens are required on all forms; the global auto-check stays on
    # because every form in this app carries a token.
    csrf.init_app(app)

    # --- Persistence: one session per request ---
    provider = build_database_provider(settings)
    session_factory = build_session_factory(provider)
    app.config["SESSION_FACTORY"] = session_factory
    app.config["DB_PROVIDER"] = provider

    @app.before_request
    def _open_db_session():
        g.db_session = session_factory()

    @app.teardown_request
    def _close_db_session(_exc):
        s = g.pop("db_session", None)
        if s is not None:
            s.close()

    # --- Web ---
    register_blueprints(app)
    register_context(app)
    register_filters(app)
    register_i18n(app)

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
