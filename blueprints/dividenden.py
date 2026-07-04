"""Dividend routes (spec §7): credited to cash, own KPI (REQ-DIV-KPI)."""
from flask import Blueprint, redirect, render_template, request, url_for

from services.depots import get_depot_or_404
from services.dividenden import (
    dividende_bearbeiten,
    dividende_erfassen,
    dividende_loeschen,
    get_dividende,
    parse_dividende,
)
from services.instrumente import alle_instrumente
from utils.fehler import ValidierungsFehler
from utils.flash import flash_errors, flash_ok

bp = Blueprint("dividenden", __name__, url_prefix="/depots/<int:depot_id>/dividenden")


@bp.route("/neu", methods=["GET", "POST"])
def neu(depot_id):
    depot = get_depot_or_404(depot_id)
    if request.method == "POST":
        fields, errors = parse_dividende(request.form)
        if errors:
            flash_errors(errors)
        else:
            try:
                dividende_erfassen(depot_id, fields)
                flash_ok("dividende.gespeichert")
                return redirect(url_for("transaktionen.index", depot_id=depot_id))
            except ValidierungsFehler as fehler:
                flash_errors(fehler.meldungen)
    vorauswahl = request.args.get("instrument_id", type=int)
    return render_template(
        "dividenden/form.html",
        depot=depot,
        dividende=None,
        form=request.form,
        instrumente=alle_instrumente(),
        vorauswahl=vorauswahl,
    )


@bp.route("/<int:dividende_id>/bearbeiten", methods=["GET", "POST"])
def bearbeiten(depot_id, dividende_id):
    depot = get_depot_or_404(depot_id)
    dividende = get_dividende(dividende_id)
    if dividende is None or dividende.depot_id != depot_id:
        return redirect(url_for("transaktionen.index", depot_id=depot_id))
    if request.method == "POST":
        fields, errors = parse_dividende(request.form)
        if errors:
            flash_errors(errors)
        else:
            try:
                dividende_bearbeiten(dividende_id, fields)
                flash_ok("dividende.gespeichert")
                return redirect(url_for("transaktionen.index", depot_id=depot_id))
            except ValidierungsFehler as fehler:
                flash_errors(fehler.meldungen)
    return render_template(
        "dividenden/form.html",
        depot=depot,
        dividende=dividende,
        form=request.form,
        instrumente=alle_instrumente(),
        vorauswahl=None,
    )


@bp.route("/<int:dividende_id>/loeschen", methods=["POST"])
def loeschen(depot_id, dividende_id):
    get_depot_or_404(depot_id)
    try:
        dividende_loeschen(dividende_id)
        flash_ok("dividende.geloescht")
    except ValidierungsFehler as fehler:
        flash_errors(fehler.meldungen)
    return redirect(url_for("transaktionen.index", depot_id=depot_id))
