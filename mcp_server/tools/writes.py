"""Write tools (spec §9, phase 3).

Every write reuses the SAME `parse_*`/`validate_*` helpers as the web forms
(fields dict -> MultiDict -> parse), so identical validation and the same
recalculation run for UI and MCP (skill rule / spec §9).
"""
from __future__ import annotations

from werkzeug.datastructures import MultiDict

from mcp_server.auth import authorized
from mcp_server.serialize import to_jsonable
from mcp_server.tools._common import require_depot
from utils.fehler import ValidierungsFehler


def build_multidict(fields: dict) -> MultiDict:
    """Convert a tool `fields` object into the form shape the parsers expect."""
    return MultiDict({k: "" if v is None else str(v) for k, v in fields.items()})


def _validiert(parse, fields: dict) -> dict:
    geparst, errors = parse(build_multidict(fields))
    if errors:
        raise ValidierungsFehler(*errors)
    return geparst


def register(mcp):
    @mcp.tool()
    def kauf_erfassen(depot_id: int, fields: dict) -> dict:
        """Record a buy. fields: instrument_id, stueck, kaufkurs,
        kauf_zeitpunkt (ISO), spesen?, boerse?"""
        with authorized():
            from services.kaeufe import kauf_erfassen as svc, parse_kauf

            require_depot(depot_id)
            kauf, backfill = svc(depot_id, _validiert(parse_kauf, fields))
            return to_jsonable({"id": kauf.id, "backfill_empfohlen": backfill})

    @mcp.tool()
    def verkauf_erfassen(depot_id: int, fields: dict) -> dict:
        """Record a sale (incl. tax). fields: instrument_id, stueck,
        verkaufskurs, verkauf_zeitpunkt (ISO), spesen?, steuer?, boerse?"""
        with authorized():
            from services.verkaeufe import parse_verkauf, verkauf_erfassen as svc

            require_depot(depot_id)
            verkauf = svc(depot_id, _validiert(parse_verkauf, fields))
            return to_jsonable(
                {"id": verkauf.id, "realisierter_gewinn": verkauf.realisierter_gewinn}
            )

    @mcp.tool()
    def einzahlung(depot_id: int, betrag: str, zeitpunkt: str, notiz: str | None = None) -> dict:
        """Record a cash deposit."""
        return _zahlung(depot_id, "EINZAHLUNG", betrag, zeitpunkt, notiz)

    @mcp.tool()
    def auszahlung(depot_id: int, betrag: str, zeitpunkt: str, notiz: str | None = None) -> dict:
        """Record a cash withdrawal (coverage-checked)."""
        return _zahlung(depot_id, "AUSZAHLUNG", betrag, zeitpunkt, notiz)

    def _zahlung(depot_id, typ, betrag, zeitpunkt, notiz):
        with authorized():
            from services.zahlungen import parse_zahlung, zahlung_erfassen

            require_depot(depot_id)
            fields = _validiert(
                parse_zahlung,
                {"typ": typ, "betrag": betrag, "zeitpunkt": zeitpunkt, "notiz": notiz},
            )
            zahlung = zahlung_erfassen(depot_id, fields)
            return to_jsonable({"id": zahlung.id})

    @mcp.tool()
    def dividende_erfassen(depot_id: int, fields: dict) -> dict:
        """Record a dividend. fields: instrument_id, betrag, zeitpunkt (ISO),
        notiz?, betrag_je_anteil?, stueck_zum_zeitpunkt?"""
        with authorized():
            from services.dividenden import dividende_erfassen as svc, parse_dividende

            require_depot(depot_id)
            dividende = svc(depot_id, _validiert(parse_dividende, fields))
            return to_jsonable({"id": dividende.id})

    @mcp.tool()
    def steuerverrechnung_erfassen(depot_id: int, betrag: str, zeitpunkt: str,
                                   notiz: str | None = None) -> dict:
        """Record a portfolio-wide tax settlement (credit)."""
        with authorized():
            from services.steuern import parse_steuerverrechnung, steuerverrechnung_erfassen as svc

            require_depot(depot_id)
            fields = _validiert(
                parse_steuerverrechnung,
                {"betrag": betrag, "zeitpunkt": zeitpunkt, "notiz": notiz},
            )
            sv = svc(depot_id, fields)
            return to_jsonable({"id": sv.id})

    # -- edit/delete any booking (spec §4.11) -----------------------------
    _BEARBEITER = {
        "kauf": ("services.kaeufe", "parse_kauf", "kauf_bearbeiten", "kauf_loeschen"),
        "verkauf": ("services.verkaeufe", "parse_verkauf", "verkauf_bearbeiten", "verkauf_loeschen"),
        "zahlung": ("services.zahlungen", "parse_zahlung", "zahlung_bearbeiten", "zahlung_loeschen"),
        "dividende": ("services.dividenden", "parse_dividende", "dividende_bearbeiten", "dividende_loeschen"),
        "steuerverrechnung": (
            "services.steuern", "parse_steuerverrechnung",
            "steuerverrechnung_bearbeiten", "steuerverrechnung_loeschen",
        ),
    }

    @mcp.tool()
    def buchung_bearbeiten(typ: str, buchung_id: int, fields: dict) -> dict:
        """Edit any booking incl. its timestamp; triggers full recalculation
        (spec §5.6). typ: kauf|verkauf|zahlung|dividende|steuerverrechnung."""
        with authorized():
            import importlib

            eintrag = _BEARBEITER.get(typ)
            if eintrag is None:
                raise ValidierungsFehler("fehler.nicht_gefunden")
            modul = importlib.import_module(eintrag[0])
            geparst = _validiert(getattr(modul, eintrag[1]), fields)
            ergebnis = getattr(modul, eintrag[2])(buchung_id, geparst)
            if isinstance(ergebnis, tuple):  # kauf_bearbeiten returns (kauf, backfill)
                ergebnis = ergebnis[0]
            return to_jsonable({"id": ergebnis.id, "typ": typ})

    @mcp.tool()
    def buchung_loeschen(typ: str, buchung_id: int) -> dict:
        """Delete any booking; triggers full recalculation (spec §5.6)."""
        with authorized():
            import importlib

            eintrag = _BEARBEITER.get(typ)
            if eintrag is None:
                raise ValidierungsFehler("fehler.nicht_gefunden")
            modul = importlib.import_module(eintrag[0])
            getattr(modul, eintrag[3])(buchung_id)
            return to_jsonable({"geloescht": True, "typ": typ, "id": buchung_id})

    @mcp.tool()
    def snapshot_erstellen(depot_id: int, name: str, notiz: str | None = None) -> dict:
        """Create a named, frozen snapshot of a depot."""
        with authorized():
            from services.snapshots import snapshot_erstellen as svc

            depot = require_depot(depot_id)
            snapshot = svc(depot, name, notiz)
            return to_jsonable({"id": snapshot.id, "name": snapshot.name})

    @mcp.tool()
    def instrument_anlegen(fields: dict) -> dict:
        """Create an instrument. fields: isin, name, kategorie
        (AKTIE|ETF|OPTIONSSCHEIN|KNOCKOUT|FAKTOR|SONSTIGES), waehrung?, wkn?,
        referenzboerse?, symbol?, basiswert?"""
        with authorized():
            from services.instrumente import instrument_anlegen as svc, parse_instrument

            instrument = svc(_validiert(parse_instrument, fields))
            return to_jsonable({"id": instrument.id, "isin": instrument.isin})

    @mcp.tool()
    def kurse_aktualisieren(depot_id: int) -> list:
        """Fetch quotes for all instruments of the depot now (spec §6.8)."""
        with authorized():
            from services.kurse import depot_aktualisieren

            require_depot(depot_id)
            return to_jsonable(
                [
                    {"isin": e.instrument.isin, "status": e.status, "kurs": e.kurs}
                    for e in depot_aktualisieren(depot_id)
                ]
            )
