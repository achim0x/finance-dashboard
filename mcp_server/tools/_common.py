"""Shared serializers/guards for MCP tools."""
from __future__ import annotations

from utils.fehler import ValidierungsFehler


def require_depot(depot_id: int):
    from services.depots import get_depot

    depot = get_depot(depot_id)
    if depot is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    return depot


def depot_dict(depot) -> dict:
    return {
        "id": depot.id,
        "name": depot.name,
        "eroeffnet_am": depot.eroeffnet_am,
        "basiswaehrung": depot.basiswaehrung,
        "notiz": depot.notiz,
    }


def kennzahlen_dict(kz) -> dict:
    return {
        "depotbestand": kz.depotbestand,
        "barbestand": kz.barbestand,
        "gesamtwert": kz.gesamtwert,
        "realisierter_gewinn": kz.realisierter_gewinn,
        "unrealisierter_gewinn": kz.unrealisierter_gewinn,
        "gesamtgewinn": kz.gesamtgewinn,
        "dividenden": kz.dividenden,
        "steuern": kz.steuern,
        "gesamtergebnis": kz.gesamtergebnis,
        "aktuell_eur": kz.aktuell_eur,
    }


def position_dict(p) -> dict:
    kz = p.kennzahlen
    return {
        "instrument_id": p.instrument.id,
        "isin": p.instrument.isin,
        "name": p.instrument.name,
        "kategorie": p.instrument.kategorie,
        "offene_stueck": kz.offene_stueck,
        "einstandswert": kz.einstandswert,
        "positionswert": kz.positionswert,
        "tagesveraenderung_eur": kz.tagesveraenderung_eur,
        "tagesveraenderung_pct": kz.tagesveraenderung_pct,
        "gesamtveraenderung_eur": kz.gesamtveraenderung_eur,
        "gesamtveraenderung_pct": kz.gesamtveraenderung_pct,
        "gewichtung": kz.gewichtung,
        "kurs": p.kurs.kurs if p.kurs else None,
        "kurs_zeitstempel": p.kurs.zeitstempel if p.kurs else None,
        "kurs_veraltet": p.kurs_veraltet,
    }
