"""Export service (spec §7): tabular data for xlsx/CSV downloads and the
printable PDF views. Column headers are i18n keys — the blueprint translates
them before rendering (REQ-I18N).
"""
from __future__ import annotations

import csv
import io
from decimal import Decimal

from domain.entities import Depot


def daten_bestand(depot: Depot) -> tuple[list[str], list[list]]:
    from services.positionen import positionen_fuer_depot  # lazy: avoid cycle

    header = [
        "export.instrument", "export.isin", "export.stueck", "export.einstandswert",
        "export.kurs", "export.wert", "export.akt_eur", "export.akt_pct",
        "export.ges_eur", "export.ges_pct", "export.gewichtung",
    ]
    zeilen = []
    for p in positionen_fuer_depot(depot):
        kz = p.kennzahlen
        zeilen.append(
            [
                p.instrument.name,
                p.instrument.isin,
                kz.offene_stueck,
                kz.einstandswert,
                p.kurs.kurs if p.kurs else None,
                kz.positionswert,
                kz.tagesveraenderung_eur,
                kz.tagesveraenderung_pct,
                kz.gesamtveraenderung_eur,
                kz.gesamtveraenderung_pct,
                kz.gewichtung,
            ]
        )
    return header, zeilen


def daten_verkaeufe(depot: Depot) -> tuple[list[str], list[list]]:
    from services.verkaeufe import verkaeufe_fuer_depot  # lazy: avoid cycle

    header = [
        "export.zeitpunkt", "export.instrument", "export.stueck", "export.kurs",
        "export.spesen", "export.steuer", "export.realisierter_gewinn",
    ]
    zeilen = []
    for v in verkaeufe_fuer_depot(depot.id):
        zeilen.append(
            [
                v.verkauf_zeitpunkt,
                v.instrument.name if v.instrument else "",
                v.stueck,
                v.verkaufskurs,
                v.spesen,
                v.steuer,
                v.realisierter_gewinn,
            ]
        )
    return header, zeilen


def daten_transaktionen(depot: Depot) -> tuple[list[str], list[list]]:
    from services.transaktionen import ledger  # lazy: avoid cycle

    header = ["export.zeitpunkt", "export.typ", "export.instrument", "export.betrag", "export.details"]
    zeilen = []
    for zeile in ledger(depot.id):
        zeilen.append(
            [
                zeile.zeitpunkt,
                f"transaktionen.typ.{zeile.typ}",  # translated by the blueprint
                zeile.instrument_name or "",
                zeile.betrag,
                zeile.details or "",
            ]
        )
    return header, zeilen


def daten_uebersicht() -> tuple[list[str], list[list]]:
    from services.depots import alle_depots_kennzahlen  # lazy: avoid cycle

    header = [
        "export.depot", "export.gesamtwert", "export.depotbestand", "export.barbestand",
        "export.gesamtgewinn", "export.performance", "export.dividenden",
        "export.steuern", "export.gesamtergebnis",
    ]
    zeilen_raw, summen = alle_depots_kennzahlen()
    zeilen = []
    for zeile in zeilen_raw:
        kz = zeile.kennzahlen
        zeilen.append(
            [
                zeile.depot.name, kz.gesamtwert, kz.depotbestand, kz.barbestand,
                kz.gesamtgewinn, kz.unrealisierter_gewinn, kz.dividenden,
                kz.steuern, kz.gesamtergebnis,
            ]
        )
    zeilen.append(
        [
            "export.summe", summen.gesamtwert, summen.depotbestand, summen.barbestand,
            summen.gesamtgewinn, summen.unrealisierter_gewinn, summen.dividenden,
            summen.steuern, summen.gesamtergebnis,
        ]
    )
    return header, zeilen


def daten_snapshot_vergleich(a_id: int, b_id: int) -> tuple[list[str], list[list]]:
    from services.snapshots import vergleich  # lazy: avoid cycle

    daten = vergleich(a_id, b_id)
    header = ["export.kennzahl", "export.snapshot_a", "export.snapshot_b", "export.differenz"]
    zeilen = [
        [f"kennzahl.{k['feld']}", k["a"], k["b"], k["differenz"]] for k in daten["kpis"]
    ]
    for p in daten["positionen"]:
        zeilen.append([p["name"], p["wert_a"], p["wert_b"], p["differenz"]])
    return header, zeilen


# --------------------------------------------------------------------------
# Format writers
# --------------------------------------------------------------------------

def _zelle(wert):
    if isinstance(wert, Decimal):
        # Commercial rounding to 2 dp happens only at output time (spec §5).
        return f"{wert:.2f}"
    if hasattr(wert, "isoformat"):
        return wert.isoformat(sep=" ") if hasattr(wert, "time") else wert.isoformat()
    return "" if wert is None else str(wert)


def als_csv(header: list[str], zeilen: list[list]) -> str:
    puffer = io.StringIO()
    writer = csv.writer(puffer, delimiter=";")
    writer.writerow(header)
    for zeile in zeilen:
        writer.writerow([_zelle(w) for w in zeile])
    return puffer.getvalue()


def als_xlsx(header: list[str], zeilen: list[list]) -> bytes:
    from openpyxl import Workbook  # lazy import

    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for zeile in zeilen:
        ws.append(
            [float(w) if isinstance(w, Decimal) else (_zelle(w) if w is not None else "") for w in zeile]
        )
    puffer = io.BytesIO()
    wb.save(puffer)
    return puffer.getvalue()
