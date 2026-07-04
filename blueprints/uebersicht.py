"""Overview dashboard across ALL depots (spec §7): KPIs per depot + totals,
depot CRUD, depot switching. Not depot-scoped (root `/`).
"""
from flask import Blueprint, redirect, render_template, request, session, url_for

from services.depots import (
    alle_depots_kennzahlen,
    depot_anlegen,
    depot_bearbeiten,
    depot_loeschen,
    get_depot_or_404,
    parse_depot,
)
from utils.fehler import ValidierungsFehler
from utils.flash import flash_errors, flash_ok

bp = Blueprint("uebersicht", __name__)


@bp.route("/")
def index():
    zeilen, summen = alle_depots_kennzahlen()
    return render_template("uebersicht/index.html", zeilen=zeilen, summen=summen)


@bp.route("/depots/neu", methods=["GET", "POST"])
def depot_neu():
    if request.method == "POST":
        fields, errors = parse_depot(request.form)
        if errors:
            flash_errors(errors)
        else:
            try:
                depot = depot_anlegen(fields)
                session["aktuelles_depot_id"] = depot.id
                return redirect(url_for("depots.dashboard", depot_id=depot.id))
            except ValidierungsFehler as fehler:
                flash_errors(fehler.meldungen)
    return render_template("uebersicht/depot_form.html", depot=None, form=request.form)


@bp.route("/depots/<int:depot_id>/bearbeiten", methods=["GET", "POST"])
def depot_bearbeiten_route(depot_id):
    depot = get_depot_or_404(depot_id)
    if request.method == "POST":
        fields, errors = parse_depot(request.form)
        if errors:
            flash_errors(errors)
        else:
            try:
                depot_bearbeiten(depot_id, fields)
                return redirect(url_for("uebersicht.index"))
            except ValidierungsFehler as fehler:
                flash_errors(fehler.meldungen)
    return render_template("uebersicht/depot_form.html", depot=depot, form=request.form)


@bp.route("/depots/<int:depot_id>/loeschen", methods=["POST"])
def depot_loeschen_route(depot_id):
    get_depot_or_404(depot_id)
    try:
        depot_loeschen(depot_id)
        if session.get("aktuelles_depot_id") == depot_id:
            session.pop("aktuelles_depot_id", None)
    except ValidierungsFehler as fehler:
        flash_errors(fehler.meldungen)
    return redirect(url_for("uebersicht.index"))


@bp.route("/depots/<int:depot_id>/aktivieren")
def aktivieren(depot_id):
    """Depot switcher: remember the current depot in the session (spec §7)."""
    depot = get_depot_or_404(depot_id)
    session["aktuelles_depot_id"] = depot.id
    return redirect(url_for("depots.dashboard", depot_id=depot.id))
