"""Export routes (spec §7): xlsx / CSV downloads and printable PDF views
(print CSS; the browser's print dialog produces the PDF file)."""
from flask import Blueprint, Response, render_template, request

from services.depots import get_depot_or_404
from services.export import (
    als_csv,
    als_xlsx,
    daten_bestand,
    daten_snapshot_vergleich,
    daten_transaktionen,
    daten_uebersicht,
    daten_verkaeufe,
)
from utils.i18n import uebersetze

bp = Blueprint("export", __name__)

_DATEN_JE_BEREICH = {
    "bestand": daten_bestand,
    "verkaeufe": daten_verkaeufe,
    "transaktionen": daten_transaktionen,
}


def _uebersetzt(header, zeilen):
    """Translate i18n keys in headers/cells before output (REQ-I18N)."""
    header = [uebersetze(h) for h in header]
    zeilen = [
        [uebersetze(z) if isinstance(z, str) and "." in z and " " not in z else z for z in zeile]
        for zeile in zeilen
    ]
    return header, zeilen


def _antwort(header, zeilen, fmt: str, name: str, titel: str):
    header, zeilen = _uebersetzt(header, zeilen)
    if fmt == "xlsx":
        return Response(
            als_xlsx(header, zeilen),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={name}.xlsx"},
        )
    if fmt == "pdf":
        # Printable view with print CSS; the user prints to PDF (spec §7).
        return render_template(
            "export/druck.html", titel=titel, header=header, zeilen=zeilen
        )
    return Response(
        als_csv(header, zeilen),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={name}.csv"},
    )


@bp.route("/depots/<int:depot_id>/export/<bereich>.<fmt>")
def depot_export(depot_id, bereich, fmt):
    depot = get_depot_or_404(depot_id)
    lader = _DATEN_JE_BEREICH.get(bereich)
    if lader is None:
        return Response(status=404)
    header, zeilen = lader(depot)
    titel = f"{depot.name} — {uebersetze('export.' + bereich)}"
    return _antwort(header, zeilen, fmt, f"{bereich}_{depot.id}", titel)


@bp.route("/export/uebersicht.<fmt>")
def uebersicht_export(fmt):
    header, zeilen = daten_uebersicht()
    return _antwort(header, zeilen, fmt, "uebersicht", uebersetze("export.uebersicht"))


@bp.route("/depots/<int:depot_id>/export/snapshot_vergleich.<fmt>")
def snapshot_vergleich_export(depot_id, fmt):
    get_depot_or_404(depot_id)
    a_id = request.args.get("a", type=int)
    b_id = request.args.get("b", type=int)
    if not a_id or not b_id:
        return Response(status=400)
    header, zeilen = daten_snapshot_vergleich(a_id, b_id)
    return _antwort(
        header, zeilen, fmt, "snapshot_vergleich", uebersetze("export.snapshot_vergleich")
    )
