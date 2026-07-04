"""Depot service: CRUD, dashboard KPIs (spec §5.4), value-history chart data
(spec §5.5) and the all-depots overview (spec §7, REQ-UEBERSICHT).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from flask import abort

from domain.berechnung import depot_kennzahlen as _kpi_berechnen
from domain.berechnung.kennzahlen import DepotKennzahlen
from domain.entities import Depot
from domain.enums import Bezugsbasis, Zeitraum
from infrastructure.persistence.sqlalchemy_repos import (
    SqlAlchemyDepotBewertungRepository,
    SqlAlchemyDepotRepository,
    SqlAlchemyDividendeRepository,
    SqlAlchemyKaufRepository,
    SqlAlchemySnapshotRepository,
    SqlAlchemySteuerverrechnungRepository,
    SqlAlchemyVerkaufRepository,
    SqlAlchemyZahlungRepository,
)
from utils.db import current_session
from utils.fehler import ValidierungsFehler

from .helpers import zeitraum_grenzen

ZERO = Decimal("0")


def _repo():
    return SqlAlchemyDepotRepository(current_session())


def alle_depots():
    return _repo().list_all()


def get_depot(depot_id: int) -> Depot | None:
    return _repo().get(depot_id)


def get_depot_or_404(depot_id: int) -> Depot:
    """Blueprint guard for depot-scoped routes (skill convention)."""
    depot = get_depot(depot_id)
    if depot is None:
        abort(404)
    return depot


def depot_anlegen(fields: dict) -> Depot:
    repo = _repo()
    if repo.get_by_name(fields["name"]) is not None:
        raise ValidierungsFehler("fehler.depotname_vorhanden")
    depot = Depot(**fields)
    repo.add(depot)
    current_session().commit()
    return depot


def depot_bearbeiten(depot_id: int, fields: dict) -> Depot:
    repo = _repo()
    depot = repo.get(depot_id)
    if depot is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    vorhanden = repo.get_by_name(fields["name"])
    if vorhanden is not None and vorhanden.id != depot_id:
        raise ValidierungsFehler("fehler.depotname_vorhanden")
    for schluessel, wert in fields.items():
        setattr(depot, schluessel, wert)
    current_session().commit()
    return depot


def depot_loeschen(depot_id: int) -> None:
    """Delete a depot including all of its bookings/series/snapshots."""
    session = current_session()
    depot = get_depot(depot_id)
    if depot is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    for repo_cls in (
        SqlAlchemyKaufRepository,
        SqlAlchemyVerkaufRepository,
        SqlAlchemyZahlungRepository,
        SqlAlchemyDividendeRepository,
        SqlAlchemySteuerverrechnungRepository,
        SqlAlchemySnapshotRepository,
    ):
        repo = repo_cls(session)
        for zeile in repo.list_for_depot(depot_id):
            repo.delete(zeile)
    bewertungen = SqlAlchemyDepotBewertungRepository(session)
    bewertungen.delete_from(depot_id, depot.eroeffnet_am)
    _repo().delete(depot)
    session.commit()


# --------------------------------------------------------------------------
# KPIs (spec §5.4)
# --------------------------------------------------------------------------

def depot_kennzahlen(depot: Depot, mit_kursen: bool = True):
    """Dashboard KPIs + position views for one depot. Returns
    (DepotKennzahlen, list[PositionAnsicht])."""
    from services.dividenden import dividenden_summe  # lazy: avoid cycle
    from services.positionen import positionen_fuer_depot  # lazy: avoid cycle
    from services.steuern.service import gezahlte_steuern, verrechnete_steuern
    from services.zahlungen import barbestand  # lazy: avoid cycle

    session = current_session()
    positionen = positionen_fuer_depot(depot, mit_kursen=mit_kursen)
    verkaeufe = SqlAlchemyVerkaufRepository(session).list_for_depot(depot.id)
    realisiert = sum((v.realisierter_gewinn for v in verkaeufe), ZERO)

    kennzahlen = _kpi_berechnen(
        positionen=[p.kennzahlen for p in positionen],
        barbestand=barbestand(depot.id),
        realisierter_gewinn=realisiert,
        dividenden=dividenden_summe(depot.id),
        gezahlte_steuern=gezahlte_steuern(depot.id),
        steuerverrechnungen=verrechnete_steuern(depot.id),
    )
    return kennzahlen, positionen


@dataclass
class DepotUebersichtZeile:
    depot: Depot
    kennzahlen: DepotKennzahlen


def alle_depots_kennzahlen(mit_kursen: bool = True):
    """Overview dashboard: KPIs per depot + totals (REQ-UEBERSICHT)."""
    zeilen = []
    summen = DepotKennzahlen()
    for depot in alle_depots():
        kennzahlen, _ = depot_kennzahlen(depot, mit_kursen=mit_kursen)
        zeilen.append(DepotUebersichtZeile(depot=depot, kennzahlen=kennzahlen))
        summen.depotbestand += kennzahlen.depotbestand
        summen.barbestand += kennzahlen.barbestand
        summen.gesamtwert += kennzahlen.gesamtwert
        summen.realisierter_gewinn += kennzahlen.realisierter_gewinn
        summen.unrealisierter_gewinn += kennzahlen.unrealisierter_gewinn
        summen.gesamtgewinn += kennzahlen.gesamtgewinn
        summen.dividenden += kennzahlen.dividenden
        summen.steuern += kennzahlen.steuern
        summen.gesamtergebnis += kennzahlen.gesamtergebnis
        summen.aktuell_eur += kennzahlen.aktuell_eur
    return zeilen, summen


# --------------------------------------------------------------------------
# Value history & range performance (spec §5.5, REQ-RANGE-BASIS)
# --------------------------------------------------------------------------

def verlauf(
    depot: Depot,
    zeitraum: Zeitraum,
    bezugsbasis: Bezugsbasis,
    von: str | None = None,
    bis: str | None = None,
) -> dict:
    """Chart data + range performance from the `DepotBewertung` series.

    The basis toggle only selects the stored series (depotbestand vs
    gesamtwert) — no recomputation needed (spec §4.7/§5.5).
    """
    start, ende = zeitraum_grenzen(zeitraum, depot.eroeffnet_am, von, bis)
    reihe = SqlAlchemyDepotBewertungRepository(current_session()).series(
        depot.id, ab=start, bis=ende
    )
    if bezugsbasis == Bezugsbasis.NUR_WERTPAPIERE:
        werte = [(b.datum, b.depotbestand) for b in reihe]
    else:
        werte = [(b.datum, b.gesamtwert) for b in reihe]

    performance_eur = None
    performance_pct = None
    if len(werte) >= 2:
        wert_start, wert_ende = werte[0][1], werte[-1][1]
        performance_eur = wert_ende - wert_start
        if wert_start != ZERO:
            performance_pct = wert_ende / wert_start - Decimal("1")

    return {
        "labels": [datum.isoformat() for datum, _ in werte],
        "werte": [wert for _, wert in werte],
        "von": start,
        "bis": ende,
        "performance_eur": performance_eur,
        "performance_pct": performance_pct,
        # Cashflows in the range distort the naive difference — shown as a
        # hint in the UI; TWR/MWR is a later expansion stage (spec §5.5/§13).
        "cashflow_hinweis": True,
    }
