"""Buy routes ("Wert hinzufügen", spec §7): create/edit/delete incl. the
backfill question when the buy date lies in the past (spec §6.9).
"""
from datetime import date

from flask import Blueprint, redirect, render_template, request, url_for

from services.depots import get_depot_or_404
from services.instrumente import alle_instrumente, get_instrument
from services.kaeufe import (
    get_kauf,
    kauf_bearbeiten,
    kauf_erfassen,
    kauf_loeschen,
    parse_kauf,
)
from services.kurse import schlusskurse_backfill
from utils.fehler import ValidierungsFehler
from utils.flash import flash_errors, flash_ok

bp = Blueprint("kaeufe", __name__, url_prefix="/depots/<int:depot_id>/kaeufe")


@bp.route("/neu", methods=["GET", "POST"])
def neu(depot_id):
    depot = get_depot_or_404(depot_id)
    if request.method == "POST":
        fields, errors = parse_kauf(request.form)
        if errors:
            flash_errors(errors)
        else:
            try:
                kauf, backfill = kauf_erfassen(depot_id, fields)
                flash_ok("kauf.gespeichert")
                if backfill:
                    return redirect(
                        url_for(".backfill_frage", depot_id=depot_id, kauf_id=kauf.id)
                    )
                return redirect(url_for("bestand.index", depot_id=depot_id))
            except ValidierungsFehler as fehler:
                flash_errors(fehler.meldungen)
    vorauswahl = request.args.get("instrument_id", type=int)
    return render_template(
        "kaeufe/form.html",
        depot=depot,
        kauf=None,
        form=request.form,
        instrumente=alle_instrumente(),
        vorauswahl=vorauswahl,
    )


@bp.route("/<int:kauf_id>/bearbeiten", methods=["GET", "POST"])
def bearbeiten(depot_id, kauf_id):
    depot = get_depot_or_404(depot_id)
    kauf = get_kauf(kauf_id)
    if kauf is None or kauf.depot_id != depot_id:
        return redirect(url_for("bestand.index", depot_id=depot_id))
    if request.method == "POST":
        fields, errors = parse_kauf(request.form)
        if errors:
            flash_errors(errors)
        else:
            try:
                kauf, backfill = kauf_bearbeiten(kauf_id, fields)
                flash_ok("kauf.gespeichert")
                if backfill:
                    return redirect(
                        url_for(".backfill_frage", depot_id=depot_id, kauf_id=kauf.id)
                    )
                return redirect(url_for("bestand.index", depot_id=depot_id))
            except ValidierungsFehler as fehler:
                flash_errors(fehler.meldungen)
    return render_template(
        "kaeufe/form.html",
        depot=depot,
        kauf=kauf,
        form=request.form,
        instrumente=alle_instrumente(),
        vorauswahl=None,
    )


@bp.route("/<int:kauf_id>/loeschen", methods=["POST"])
def loeschen(depot_id, kauf_id):
    get_depot_or_404(depot_id)
    try:
        kauf_loeschen(kauf_id)
        flash_ok("kauf.geloescht")
    except ValidierungsFehler as fehler:
        flash_errors(fehler.meldungen)
    return redirect(url_for("bestand.index", depot_id=depot_id))


@bp.route("/<int:kauf_id>/backfill", methods=["GET", "POST"])
def backfill_frage(depot_id, kauf_id):
    """Ask whether to prefill the mini chart with historical daily closes
    (REQ-CHART-BACKFILL). 'Nein' or missing history falls back cleanly to
    forward filling."""
    depot = get_depot_or_404(depot_id)
    kauf = get_kauf(kauf_id)
    if kauf is None or kauf.depot_id != depot_id:
        return redirect(url_for("bestand.index", depot_id=depot_id))
    if request.method == "POST":
        if request.form.get("antwort") == "ja":
            anzahl = schlusskurse_backfill(
                kauf.instrument_id, kauf.kauf_zeitpunkt.date(), date.today()
            )
            if anzahl > 0:
                flash_ok("kauf.backfill_ok", anzahl=anzahl)
            else:
                flash_ok("kauf.backfill_leer")
        return redirect(url_for("bestand.index", depot_id=depot_id))
    return render_template(
        "kaeufe/backfill_frage.html",
        depot=depot,
        kauf=kauf,
        instrument=get_instrument(kauf.instrument_id),
    )
