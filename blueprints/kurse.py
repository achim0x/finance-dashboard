"""Price routes (spec §6.8/§6.9): manual "Kurse aktualisieren" button,
mini-chart JSON and manual quote entry (fallback provider)."""
from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from services.depots import get_depot_or_404
from services.kurse import depot_aktualisieren, manuellen_kurs_erfassen, mini_chart
from utils.parsing import parse_datum, parse_decimal
from utils.fehler import ValidierungsFehler
from utils.flash import flash_errors, flash_ok

bp = Blueprint("kurse", __name__, url_prefix="/depots/<int:depot_id>/kurse")


@bp.route("/aktualisieren", methods=["POST"])
def aktualisieren(depot_id):
    """Manual refresh of all quotes of the depot (REQ-KURS-MANUELL).
    Individual failures are reported without stopping the rest."""
    get_depot_or_404(depot_id)
    ergebnisse = depot_aktualisieren(depot_id)
    ok = sum(1 for e in ergebnisse if e.status == "OK")
    fehler = len(ergebnisse) - ok
    flash_ok("kurse.aktualisiert", ok=ok, fehler=fehler)
    if fehler:
        return render_template(
            "kurse/ergebnisse.html",
            depot=get_depot_or_404(depot_id),
            ergebnisse=ergebnisse,
        )
    return redirect(request.referrer or url_for("bestand.index", depot_id=depot_id))


@bp.route("/mini_chart/<int:instrument_id>")
def mini_chart_json(depot_id, instrument_id):
    """Closing-price series since the buy date, for the position mini chart."""
    get_depot_or_404(depot_id)
    ab = parse_datum(request.args.get("ab"))
    if ab is None:
        return jsonify({"labels": [], "werte": []})
    punkte = mini_chart(instrument_id, ab)
    return jsonify(
        {
            "labels": [d.isoformat() for d, _ in punkte],
            "werte": [float(w) for _, w in punkte],
        }
    )


@bp.route("/manuell", methods=["POST"])
def manuell(depot_id):
    """Manual quote entry — fallback when no provider covers an instrument."""
    get_depot_or_404(depot_id)
    instrument_id = request.form.get("instrument_id", type=int)
    wert = parse_decimal(request.form.get("kurs"))
    waehrung = (request.form.get("waehrung") or "EUR").strip().upper()
    if instrument_id is None or wert is None or wert <= 0:
        flash_errors(["fehler.kurs_positiv"])
    else:
        try:
            manuellen_kurs_erfassen(instrument_id, wert, waehrung)
            flash_ok("kurse.manuell_gespeichert")
        except ValidierungsFehler as fehler:
            flash_errors(fehler.meldungen)
    return redirect(request.referrer or url_for("bestand.index", depot_id=depot_id))
