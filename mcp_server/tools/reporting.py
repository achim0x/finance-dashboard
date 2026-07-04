"""Reporting tools (spec §9, phase 2)."""
from __future__ import annotations

from mcp_server.auth import authorized
from mcp_server.serialize import to_jsonable
from mcp_server.tools._common import kennzahlen_dict, position_dict, require_depot


def register(mcp):
    @mcp.tool()
    def depot_zusammenfassung(depot_id: int) -> dict:
        """Depot summary: KPIs plus all open positions."""
        with authorized():
            from services.depots import depot_kennzahlen

            depot = require_depot(depot_id)
            kennzahlen, positionen = depot_kennzahlen(depot)
            return to_jsonable(
                {
                    "depot": {"id": depot.id, "name": depot.name},
                    "kennzahlen": kennzahlen_dict(kennzahlen),
                    "positionen": [position_dict(p) for p in positionen],
                }
            )

    @mcp.tool()
    def gewichtung(depot_id: int) -> list:
        """Position weights (share of the securities value) of a depot."""
        with authorized():
            from services.positionen import positionen_fuer_depot

            depot = require_depot(depot_id)
            return to_jsonable(
                [
                    {
                        "isin": p.instrument.isin,
                        "name": p.instrument.name,
                        "positionswert": p.kennzahlen.positionswert,
                        "gewichtung": p.kennzahlen.gewichtung,
                    }
                    for p in positionen_fuer_depot(depot)
                ]
            )

    @mcp.tool()
    def performance(depot_id: int, zeitraum: str = "SEIT_EROEFFNUNG",
                    bezugsbasis: str = "INKL_BARBESTAND",
                    von: str | None = None, bis: str | None = None) -> dict:
        """Range performance from the valuation series (spec §5.5).

        zeitraum: SEIT_EROEFFNUNG|1M|3M|6M|YTD|1J|BENUTZERDEFINIERT
        bezugsbasis: NUR_WERTPAPIERE|INKL_BARBESTAND
        """
        with authorized():
            from domain.enums import Bezugsbasis, Zeitraum
            from services.depots import verlauf

            depot = require_depot(depot_id)
            daten = verlauf(depot, Zeitraum(zeitraum), Bezugsbasis(bezugsbasis), von=von, bis=bis)
            return to_jsonable(
                {
                    "von": daten["von"],
                    "bis": daten["bis"],
                    "performance_eur": daten["performance_eur"],
                    "performance_pct": daten["performance_pct"],
                    "punkte": len(daten["labels"]),
                }
            )

    @mcp.tool()
    def snapshot_vergleich(a_id: int, b_id: int) -> dict:
        """Compare two snapshots: KPI and per-position differences."""
        with authorized():
            from services.snapshots import vergleich

            daten = vergleich(a_id, b_id)
            return to_jsonable(
                {
                    "a": {"id": daten["a"].id, "name": daten["a"].name, "erstellt_am": daten["a"].erstellt_am},
                    "b": {"id": daten["b"].id, "name": daten["b"].name, "erstellt_am": daten["b"].erstellt_am},
                    "kpis": daten["kpis"],
                    "positionen": daten["positionen"],
                }
            )

    @mcp.tool()
    def kurse_testen(depot_id: int) -> list:
        """Availability test (spec §6.7): per-instrument provider status;
        writes nothing."""
        with authorized():
            from services.kurse import depot_testen

            require_depot(depot_id)
            return to_jsonable(
                [
                    {
                        "isin": e.instrument.isin,
                        "name": e.instrument.name,
                        "status": e.status,
                        "kurs": e.kurs,
                        "zeitstempel": e.zeitstempel,
                        "quelle": e.quelle,
                        "meldung": e.meldung,
                    }
                    for e in depot_testen(depot_id)
                ]
            )
