"""Single-depot dashboard (spec §7): KPI tiles, value-history chart with
time-range/basis toggle (spec §5.5); the selection is kept in the session.
"""
from flask import Blueprint, jsonify, render_template, request, session

from domain.enums import Bezugsbasis, Zeitraum
from services.depots import depot_kennzahlen, get_depot_or_404, verlauf

bp = Blueprint("depots", __name__, url_prefix="/depots/<int:depot_id>")


def _chart_auswahl(depot, args) -> dict:
    """Resolve range/basis: query args > session > depot defaults (spec §4.1);
    the choice is remembered in the session (spec §5.5)."""
    schluessel = f"chart_auswahl_{depot.id}"
    auswahl = dict(session.get(schluessel) or {})
    if not auswahl:
        auswahl = {
            "zeitraum": depot.default_zeitraum,
            "basis": depot.default_bezugsbasis,
            "von": None,
            "bis": None,
        }
    if args.get("zeitraum"):
        auswahl["zeitraum"] = args["zeitraum"]
    if args.get("basis"):
        auswahl["basis"] = args["basis"]
    if "von" in args:
        auswahl["von"] = args.get("von") or None
    if "bis" in args:
        auswahl["bis"] = args.get("bis") or None
    try:
        Zeitraum(auswahl["zeitraum"])
        Bezugsbasis(auswahl["basis"])
    except ValueError:
        auswahl["zeitraum"] = depot.default_zeitraum
        auswahl["basis"] = depot.default_bezugsbasis
    session[schluessel] = auswahl
    return auswahl


@bp.route("")
def dashboard(depot_id):
    depot = get_depot_or_404(depot_id)
    session["aktuelles_depot_id"] = depot.id
    auswahl = _chart_auswahl(depot, request.args)
    kennzahlen, positionen = depot_kennzahlen(depot)
    chart = verlauf(
        depot,
        Zeitraum(auswahl["zeitraum"]),
        Bezugsbasis(auswahl["basis"]),
        von=auswahl.get("von"),
        bis=auswahl.get("bis"),
    )
    return render_template(
        "depots/dashboard.html",
        depot=depot,
        kennzahlen=kennzahlen,
        positionen=positionen,
        chart=chart,
        auswahl=auswahl,
        zeitraeume=[z.value for z in Zeitraum],
        basen=[b.value for b in Bezugsbasis],
    )


@bp.route("/verlauf.json")
def verlauf_json(depot_id):
    """Chart data endpoint (Chart.js fetches this on toggle)."""
    depot = get_depot_or_404(depot_id)
    auswahl = _chart_auswahl(depot, request.args)
    daten = verlauf(
        depot,
        Zeitraum(auswahl["zeitraum"]),
        Bezugsbasis(auswahl["basis"]),
        von=auswahl.get("von"),
        bis=auswahl.get("bis"),
    )
    return jsonify(
        {
            "labels": daten["labels"],
            "werte": [float(w) for w in daten["werte"]],
            "performance_eur": float(daten["performance_eur"]) if daten["performance_eur"] is not None else None,
            "performance_pct": float(daten["performance_pct"]) if daten["performance_pct"] is not None else None,
        }
    )
