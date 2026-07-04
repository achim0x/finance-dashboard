"""Recalculation after booking changes (spec §5.6).

Derived on-the-fly state (cash balance, open positions, KPIs) needs no
persistence-side recalculation. What HAS to be refreshed on any change:

1. `Verkauf.realisierter_gewinn` of the affected instrument — recomputed
   from scratch in booking order (FIFO order follows `*_zeitpunkt`).
2. The `DepotBewertung` series from the earliest affected day, rebuilt
   exclusively from daily closing prices (spec §5.6 / REQ-REVAL-CLOSE).

`DepotSnapshot` rows stay untouched (frozen comparison state).
"""
from __future__ import annotations

from datetime import datetime

from domain.berechnung import realisierte_gewinne
from domain.enums import Verrechnungsmethode
from infrastructure.persistence.sqlalchemy_repos import (
    SqlAlchemyKaufRepository,
    SqlAlchemyVerkaufRepository,
)
from utils.db import current_session, current_settings


def realisierte_gewinne_neu(depot_id: int, instrument_id: int) -> None:
    """Recompute + store realized gains for all sales of one instrument.

    Raises `UnzureichenderBestandError` if the (changed) bookings no longer
    cover a sale — callers translate that into a validation error and roll
    back.
    """
    session = current_session()
    kaeufe = SqlAlchemyKaufRepository(session).list_for_position(depot_id, instrument_id)
    verkaeufe = SqlAlchemyVerkaufRepository(session).list_for_position(depot_id, instrument_id)
    if not verkaeufe:
        return
    methode = Verrechnungsmethode(current_settings().verrechnungsmethode)
    gewinne = realisierte_gewinne(kaeufe, verkaeufe, methode)
    for verkauf in verkaeufe:
        verkauf.realisierter_gewinn = gewinne[verkauf.id]
    session.flush()


def nach_buchungsaenderung(
    depot_id: int,
    instrument_id: int | None = None,
    ab_zeitpunkt: datetime | None = None,
) -> None:
    """Entry point called by every booking service on create/edit/delete.

    Does NOT commit — the calling service owns the transaction.
    """
    if instrument_id is not None:
        realisierte_gewinne_neu(depot_id, instrument_id)
    if ab_zeitpunkt is not None:
        from services.kurse import bewertungen_neu_aufbauen  # lazy: avoid cycle

        bewertungen_neu_aufbauen(depot_id, ab=ab_zeitpunkt.date())
