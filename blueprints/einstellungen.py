"""App/display settings (spec §7): UI language (REQ-I18N) and the holdings
column selection (kept in the session). Method/TTL/overdraw flags live in
the environment config and are shown read-only here."""
from flask import Blueprint, redirect, render_template, request, session, url_for

from blueprints.bestand import ALLE_SPALTEN, STANDARD_SPALTEN
from utils.db import current_settings
from utils.flash import flash_ok
from utils.i18n import verfuegbare_sprachen

bp = Blueprint("einstellungen", __name__, url_prefix="/einstellungen")


@bp.route("", methods=["GET"])
def index():
    return render_template(
        "einstellungen/index.html",
        alle_spalten=ALLE_SPALTEN,
        gewaehlte_spalten=session.get("bestand_spalten") or STANDARD_SPALTEN,
        settings=current_settings(),
    )


@bp.route("/sprache", methods=["POST"])
def sprache():
    gewaehlt = request.form.get("sprache", "de")
    if gewaehlt in verfuegbare_sprachen():
        session["sprache"] = gewaehlt
        flash_ok("einstellungen.sprache_gespeichert")
    return redirect(url_for(".index"))


@bp.route("/spalten", methods=["POST"])
def spalten():
    gewaehlt = [s for s in ALLE_SPALTEN if request.form.get(f"spalte_{s}")]
    session["bestand_spalten"] = gewaehlt or STANDARD_SPALTEN
    flash_ok("einstellungen.spalten_gespeichert")
    return redirect(url_for(".index"))
