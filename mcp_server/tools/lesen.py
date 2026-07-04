"""Read tools (spec §9, phase 1)."""
from __future__ import annotations

from mcp_server.auth import authorized
from mcp_server.serialize import to_jsonable
from mcp_server.tools._common import (
    depot_dict,
    kennzahlen_dict,
    position_dict,
    require_depot,
)


def register(mcp):
    @mcp.tool()
    def whoami() -> dict:
        """Connection test: returns the identity resolved from the API key."""
        with authorized() as identity:
            return to_jsonable(identity)

    @mcp.tool()
    def list_depots() -> list:
        """List all depots (id, name, opened, base currency)."""
        with authorized():
            from services.depots import alle_depots

            return to_jsonable([depot_dict(d) for d in alle_depots()])

    @mcp.tool()
    def uebersicht() -> dict:
        """Overview dashboard: KPIs of every depot plus totals."""
        with authorized():
            from services.depots import alle_depots_kennzahlen

            zeilen, summen = alle_depots_kennzahlen()
            return to_jsonable(
                {
                    "depots": [
                        {**depot_dict(z.depot), **kennzahlen_dict(z.kennzahlen)}
                        for z in zeilen
                    ],
                    "summen": kennzahlen_dict(summen),
                }
            )

    @mcp.tool()
    def get_depot(depot_id: int) -> dict:
        """One depot's KPIs incl. dividends/taxes (spec §5.4)."""
        with authorized():
            from services.depots import depot_kennzahlen

            depot = require_depot(depot_id)
            kennzahlen, _ = depot_kennzahlen(depot)
            return to_jsonable({**depot_dict(depot), **kennzahlen_dict(kennzahlen)})

    @mcp.tool()
    def list_positionen(depot_id: int) -> list:
        """Open positions of a depot with position KPIs (spec §5.1)."""
        with authorized():
            from services.positionen import positionen_fuer_depot

            depot = require_depot(depot_id)
            return to_jsonable([position_dict(p) for p in positionen_fuer_depot(depot)])

    @mcp.tool()
    def list_verkaeufe(depot_id: int) -> list:
        """All sales of a depot incl. realized gain and paid tax."""
        with authorized():
            from services.verkaeufe import verkaeufe_fuer_depot

            require_depot(depot_id)
            return to_jsonable(
                [
                    {
                        "id": v.id,
                        "instrument_id": v.instrument_id,
                        "isin": v.instrument.isin if v.instrument else None,
                        "stueck": v.stueck,
                        "verkaufskurs": v.verkaufskurs,
                        "verkauf_zeitpunkt": v.verkauf_zeitpunkt,
                        "spesen": v.spesen,
                        "steuer": v.steuer,
                        "realisierter_gewinn": v.realisierter_gewinn,
                    }
                    for v in verkaeufe_fuer_depot(depot_id)
                ]
            )

    @mcp.tool()
    def list_transaktionen(depot_id: int) -> list:
        """Chronological full ledger (buys, sells, payments, dividends, taxes)."""
        with authorized():
            from services.transaktionen import ledger

            require_depot(depot_id)
            return to_jsonable(
                [
                    {
                        "typ": z.typ,
                        "id": z.id,
                        "zeitpunkt": z.zeitpunkt,
                        "betrag": z.betrag,
                        "instrument": z.instrument_name,
                        "details": z.details,
                    }
                    for z in ledger(depot_id)
                ]
            )

    @mcp.tool()
    def list_dividenden(depot_id: int) -> list:
        """All dividends of a depot."""
        with authorized():
            from services.dividenden import dividenden_fuer_depot

            require_depot(depot_id)
            return to_jsonable(
                [
                    {
                        "id": d.id,
                        "instrument_id": d.instrument_id,
                        "isin": d.instrument.isin if d.instrument else None,
                        "betrag": d.betrag,
                        "zeitpunkt": d.zeitpunkt,
                        "notiz": d.notiz,
                    }
                    for d in dividenden_fuer_depot(depot_id)
                ]
            )

    @mcp.tool()
    def list_snapshots(depot_id: int) -> list:
        """All named snapshots of a depot."""
        with authorized():
            from services.snapshots import snapshots_fuer_depot

            require_depot(depot_id)
            return to_jsonable(
                [
                    {
                        "id": s.id,
                        "name": s.name,
                        "erstellt_am": s.erstellt_am,
                        "gesamtwert": s.gesamtwert,
                        "gesamtergebnis": s.gesamtergebnis,
                    }
                    for s in snapshots_fuer_depot(depot_id)
                ]
            )

    @mcp.tool()
    def get_kurs(isin: str) -> dict | None:
        """Latest stored quote of an instrument by ISIN."""
        with authorized():
            from services.instrumente import get_instrument_by_isin
            from services.kurse import aktueller_kurs, kurs_ist_veraltet

            instrument = get_instrument_by_isin(isin)
            if instrument is None:
                return None
            kurs = aktueller_kurs(instrument)
            if kurs is None:
                return None
            return to_jsonable(
                {
                    "isin": instrument.isin,
                    "kurs": kurs.kurs,
                    "waehrung": kurs.waehrung,
                    "boerse": kurs.boerse,
                    "zeitstempel": kurs.zeitstempel,
                    "quelle": kurs.quelle,
                    "veraltet": kurs_ist_veraltet(kurs, instrument),
                }
            )

    @mcp.tool()
    def get_wechselkurs(von: str, nach: str) -> dict | None:
        """Current FX rate von->nach (with cache/staleness status)."""
        with authorized():
            from services.waehrung import rate

            wert, status = rate(von.upper(), nach.upper())
            if wert is None:
                return None
            return to_jsonable({"von": von.upper(), "nach": nach.upper(), "kurs": wert, "status": status})
