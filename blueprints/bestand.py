"""Holdings tab (spec §7): aggregated open positions, expandable into the
individual buy tranches, with the column set from the settings."""
from flask import Blueprint, render_template, session

from services.depots import get_depot_or_404
from services.positionen import positionen_fuer_depot

#: Column keys in display order; the settings page lets the user pick.
ALLE_SPALTEN = [
    "stueck", "kaufkurs", "kaufdatum", "kaufwert", "spesen", "chart",
    "kurs", "boerse", "zeit", "akt_eur", "akt_pct", "ges_eur", "ges_pct",
    "wert", "gewichtung",
]
STANDARD_SPALTEN = [s for s in ALLE_SPALTEN if s not in ("boerse", "spesen")]

bp = Blueprint("bestand", __name__, url_prefix="/depots/<int:depot_id>")


@bp.route("/bestand")
def index(depot_id):
    depot = get_depot_or_404(depot_id)
    session["aktuelles_depot_id"] = depot.id
    positionen = positionen_fuer_depot(depot)
    spalten = session.get("bestand_spalten") or STANDARD_SPALTEN
    return render_template(
        "bestand/index.html", depot=depot, positionen=positionen, spalten=spalten
    )
