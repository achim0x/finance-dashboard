"""Snapshot service (spec §4.10): freeze KPIs + positions, compare two
snapshots (REQ-SNAPSHOT). Snapshots are immutable once created — only
create/delete, never edit.
"""
from __future__ import annotations

import json
from decimal import Decimal

from domain.entities import Depot, DepotSnapshot
from infrastructure.persistence.sqlalchemy_repos import SqlAlchemySnapshotRepository
from utils.db import current_session
from utils.fehler import ValidierungsFehler

ZERO = Decimal("0")


def snapshots_fuer_depot(depot_id: int):
    return SqlAlchemySnapshotRepository(current_session()).list_for_depot(depot_id)


def get_snapshot(snapshot_id: int) -> DepotSnapshot | None:
    return SqlAlchemySnapshotRepository(current_session()).get(snapshot_id)


def snapshot_erstellen(depot: Depot, name: str, notiz: str | None = None) -> DepotSnapshot:
    """Freeze the current KPIs and position details of a depot."""
    from services.depots import depot_kennzahlen  # lazy: avoid cycle

    name = (name or "").strip()
    if not name:
        raise ValidierungsFehler("fehler.name_fehlt")

    kennzahlen, positionen = depot_kennzahlen(depot)
    positionen_json = json.dumps(
        [
            {
                "instrument_id": p.instrument.id,
                "isin": p.instrument.isin,
                "name": p.instrument.name,
                "stueck": str(p.kennzahlen.offene_stueck),
                "einstandswert": str(p.kennzahlen.einstandswert),
                "wert": str(p.kennzahlen.positionswert),
                "gewichtung": str(p.kennzahlen.gewichtung or ZERO),
            }
            for p in positionen
        ]
    )
    snapshot = DepotSnapshot(
        depot_id=depot.id,
        name=name,
        notiz=notiz or None,
        depotbestand=kennzahlen.depotbestand,
        barbestand=kennzahlen.barbestand,
        gesamtwert=kennzahlen.gesamtwert,
        realisierter_gewinn=kennzahlen.realisierter_gewinn,
        unrealisierter_gewinn=kennzahlen.unrealisierter_gewinn,
        dividenden=kennzahlen.dividenden,
        steuern=kennzahlen.steuern,
        gesamtgewinn=kennzahlen.gesamtgewinn,
        gesamtergebnis=kennzahlen.gesamtergebnis,
        positionen_json=positionen_json,
    )
    SqlAlchemySnapshotRepository(current_session()).add(snapshot)
    current_session().commit()
    return snapshot


def snapshot_loeschen(snapshot_id: int) -> None:
    session = current_session()
    snapshot = get_snapshot(snapshot_id)
    if snapshot is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    SqlAlchemySnapshotRepository(session).delete(snapshot)
    session.commit()


_KPI_FELDER = (
    "depotbestand",
    "barbestand",
    "gesamtwert",
    "realisierter_gewinn",
    "unrealisierter_gewinn",
    "dividenden",
    "steuern",
    "gesamtgewinn",
    "gesamtergebnis",
)


def vergleich(a_id: int, b_id: int) -> dict:
    """Compare two snapshots: KPI differences and per-position differences."""
    a = get_snapshot(a_id)
    b = get_snapshot(b_id)
    if a is None or b is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    if a.depot_id != b.depot_id:
        raise ValidierungsFehler("fehler.snapshot_depot")

    kpis = []
    for feld in _KPI_FELDER:
        wert_a = getattr(a, feld)
        wert_b = getattr(b, feld)
        kpis.append({"feld": feld, "a": wert_a, "b": wert_b, "differenz": wert_b - wert_a})

    pos_a = {p["isin"]: p for p in json.loads(a.positionen_json)}
    pos_b = {p["isin"]: p for p in json.loads(b.positionen_json)}
    positionen = []
    for isin in sorted(set(pos_a) | set(pos_b)):
        za, zb = pos_a.get(isin), pos_b.get(isin)
        wert_a = Decimal(za["wert"]) if za else ZERO
        wert_b = Decimal(zb["wert"]) if zb else ZERO
        positionen.append(
            {
                "isin": isin,
                "name": (zb or za)["name"],
                "stueck_a": Decimal(za["stueck"]) if za else ZERO,
                "stueck_b": Decimal(zb["stueck"]) if zb else ZERO,
                "wert_a": wert_a,
                "wert_b": wert_b,
                "differenz": wert_b - wert_a,
            }
        )
    return {"a": a, "b": b, "kpis": kpis, "positionen": positionen}
