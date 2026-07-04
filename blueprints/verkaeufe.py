"""Sale routes + the sales tab (spec §7)."""
from flask import Blueprint, redirect, render_template, request, session, url_for

from services.depots import get_depot_or_404
from services.instrumente import alle_instrumente
from services.verkaeufe import (
    get_verkauf,
    parse_verkauf,
    verkaeufe_fuer_depot,
    verkauf_bearbeiten,
    verkauf_erfassen,
    verkauf_loeschen,
)
from utils.fehler import ValidierungsFehler
from utils.flash import flash_errors, flash_ok

bp = Blueprint("verkaeufe", __name__, url_prefix="/depots/<int:depot_id>/verkaeufe")


@bp.route("")
def index(depot_id):
    depot = get_depot_or_404(depot_id)
    session["aktuelles_depot_id"] = depot.id
    return render_template(
        "verkaeufe/index.html", depot=depot, verkaeufe=verkaeufe_fuer_depot(depot_id)
    )


@bp.route("/neu", methods=["GET", "POST"])
def neu(depot_id):
    depot = get_depot_or_404(depot_id)
    if request.method == "POST":
        fields, errors = parse_verkauf(request.form)
        if errors:
            flash_errors(errors)
        else:
            try:
                verkauf_erfassen(depot_id, fields)
                flash_ok("verkauf.gespeichert")
                return redirect(url_for(".index", depot_id=depot_id))
            except ValidierungsFehler as fehler:
                flash_errors(fehler.meldungen)
    vorauswahl = request.args.get("instrument_id", type=int)
    return render_template(
        "verkaeufe/form.html",
        depot=depot,
        verkauf=None,
        form=request.form,
        instrumente=alle_instrumente(),
        vorauswahl=vorauswahl,
    )


@bp.route("/<int:verkauf_id>/bearbeiten", methods=["GET", "POST"])
def bearbeiten(depot_id, verkauf_id):
    depot = get_depot_or_404(depot_id)
    verkauf = get_verkauf(verkauf_id)
    if verkauf is None or verkauf.depot_id != depot_id:
        return redirect(url_for(".index", depot_id=depot_id))
    if request.method == "POST":
        fields, errors = parse_verkauf(request.form)
        if errors:
            flash_errors(errors)
        else:
            try:
                verkauf_bearbeiten(verkauf_id, fields)
                flash_ok("verkauf.gespeichert")
                return redirect(url_for(".index", depot_id=depot_id))
            except ValidierungsFehler as fehler:
                flash_errors(fehler.meldungen)
    return render_template(
        "verkaeufe/form.html",
        depot=depot,
        verkauf=verkauf,
        form=request.form,
        instrumente=alle_instrumente(),
        vorauswahl=None,
    )


@bp.route("/<int:verkauf_id>/loeschen", methods=["POST"])
def loeschen(depot_id, verkauf_id):
    get_depot_or_404(depot_id)
    try:
        verkauf_loeschen(verkauf_id)
        flash_ok("verkauf.geloescht")
    except ValidierungsFehler as fehler:
        flash_errors(fehler.meldungen)
    return redirect(url_for(".index", depot_id=depot_id))
