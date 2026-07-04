"""Cash movement routes (deposits/withdrawals, spec §7)."""
from flask import Blueprint, redirect, render_template, request, url_for

from services.depots import get_depot_or_404
from services.zahlungen import (
    get_zahlung,
    parse_zahlung,
    zahlung_bearbeiten,
    zahlung_erfassen,
    zahlung_loeschen,
)
from utils.fehler import ValidierungsFehler
from utils.flash import flash_errors, flash_ok

bp = Blueprint("zahlungen", __name__, url_prefix="/depots/<int:depot_id>/zahlungen")


@bp.route("/neu", methods=["GET", "POST"])
def neu(depot_id):
    depot = get_depot_or_404(depot_id)
    if request.method == "POST":
        fields, errors = parse_zahlung(request.form)
        if errors:
            flash_errors(errors)
        else:
            try:
                zahlung_erfassen(depot_id, fields)
                flash_ok("zahlung.gespeichert")
                return redirect(url_for("transaktionen.index", depot_id=depot_id))
            except ValidierungsFehler as fehler:
                flash_errors(fehler.meldungen)
    return render_template("zahlungen/form.html", depot=depot, zahlung=None, form=request.form)


@bp.route("/<int:zahlung_id>/bearbeiten", methods=["GET", "POST"])
def bearbeiten(depot_id, zahlung_id):
    depot = get_depot_or_404(depot_id)
    zahlung = get_zahlung(zahlung_id)
    if zahlung is None or zahlung.depot_id != depot_id:
        return redirect(url_for("transaktionen.index", depot_id=depot_id))
    if request.method == "POST":
        fields, errors = parse_zahlung(request.form)
        if errors:
            flash_errors(errors)
        else:
            try:
                zahlung_bearbeiten(zahlung_id, fields)
                flash_ok("zahlung.gespeichert")
                return redirect(url_for("transaktionen.index", depot_id=depot_id))
            except ValidierungsFehler as fehler:
                flash_errors(fehler.meldungen)
    return render_template(
        "zahlungen/form.html", depot=depot, zahlung=zahlung, form=request.form
    )


@bp.route("/<int:zahlung_id>/loeschen", methods=["POST"])
def loeschen(depot_id, zahlung_id):
    get_depot_or_404(depot_id)
    try:
        zahlung_loeschen(zahlung_id)
        flash_ok("zahlung.geloescht")
    except ValidierungsFehler as fehler:
        flash_errors(fehler.meldungen)
    return redirect(url_for("transaktionen.index", depot_id=depot_id))
