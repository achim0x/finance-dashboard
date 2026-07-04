"""Tax settlement routes (spec §7): credited to cash, tax KPI (REQ-TAX-KPI)."""
from flask import Blueprint, redirect, render_template, request, url_for

from services.depots import get_depot_or_404
from services.steuern import (
    get_steuerverrechnung,
    parse_steuerverrechnung,
    steuerverrechnung_bearbeiten,
    steuerverrechnung_erfassen,
    steuerverrechnung_loeschen,
)
from utils.fehler import ValidierungsFehler
from utils.flash import flash_errors, flash_ok

bp = Blueprint("steuern", __name__, url_prefix="/depots/<int:depot_id>/steuern")


@bp.route("/neu", methods=["GET", "POST"])
def neu(depot_id):
    depot = get_depot_or_404(depot_id)
    if request.method == "POST":
        fields, errors = parse_steuerverrechnung(request.form)
        if errors:
            flash_errors(errors)
        else:
            try:
                steuerverrechnung_erfassen(depot_id, fields)
                flash_ok("steuer.gespeichert")
                return redirect(url_for("transaktionen.index", depot_id=depot_id))
            except ValidierungsFehler as fehler:
                flash_errors(fehler.meldungen)
    return render_template(
        "steuern/form.html", depot=depot, steuerverrechnung=None, form=request.form
    )


@bp.route("/<int:id_>/bearbeiten", methods=["GET", "POST"])
def bearbeiten(depot_id, id_):
    depot = get_depot_or_404(depot_id)
    sv = get_steuerverrechnung(id_)
    if sv is None or sv.depot_id != depot_id:
        return redirect(url_for("transaktionen.index", depot_id=depot_id))
    if request.method == "POST":
        fields, errors = parse_steuerverrechnung(request.form)
        if errors:
            flash_errors(errors)
        else:
            try:
                steuerverrechnung_bearbeiten(id_, fields)
                flash_ok("steuer.gespeichert")
                return redirect(url_for("transaktionen.index", depot_id=depot_id))
            except ValidierungsFehler as fehler:
                flash_errors(fehler.meldungen)
    return render_template(
        "steuern/form.html", depot=depot, steuerverrechnung=sv, form=request.form
    )


@bp.route("/<int:id_>/loeschen", methods=["POST"])
def loeschen(depot_id, id_):
    get_depot_or_404(depot_id)
    try:
        steuerverrechnung_loeschen(id_)
        flash_ok("steuer.geloescht")
    except ValidierungsFehler as fehler:
        flash_errors(fehler.meldungen)
    return redirect(url_for("transaktionen.index", depot_id=depot_id))
