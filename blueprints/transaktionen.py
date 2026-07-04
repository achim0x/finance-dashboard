"""Transactions tab (spec §7): chronological full ledger, every row editable."""
from flask import Blueprint, render_template, request, session

from services.depots import get_depot_or_404
from services.transaktionen import ledger

bp = Blueprint("transaktionen", __name__, url_prefix="/depots/<int:depot_id>")

#: Map ledger row type -> (blueprint endpoint, id kwarg) for the edit links.
EDIT_ENDPOINTS = {
    "kauf": ("kaeufe.bearbeiten", "kauf_id"),
    "verkauf": ("verkaeufe.bearbeiten", "verkauf_id"),
    "einzahlung": ("zahlungen.bearbeiten", "zahlung_id"),
    "auszahlung": ("zahlungen.bearbeiten", "zahlung_id"),
    "dividende": ("dividenden.bearbeiten", "dividende_id"),
    "steuerverrechnung": ("steuern.bearbeiten", "id_"),
}


@bp.route("/transaktionen")
def index(depot_id):
    depot = get_depot_or_404(depot_id)
    session["aktuelles_depot_id"] = depot.id
    zeilen = ledger(depot_id)
    typ_filter = request.args.get("typ") or None
    if typ_filter:
        zeilen = [z for z in zeilen if z.typ == typ_filter]
    richtung = request.args.get("sortierung", "absteigend")
    if richtung == "absteigend":
        zeilen = list(reversed(zeilen))
    return render_template(
        "transaktionen/index.html",
        depot=depot,
        zeilen=zeilen,
        edit_endpoints=EDIT_ENDPOINTS,
        typ_filter=typ_filter,
        sortierung=richtung,
    )
