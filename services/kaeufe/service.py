"""Buy (tranche) service: create/edit/delete incl. coverage check,
recalculation trigger and the backfill recommendation (spec §4.3/§6.9).
"""
from __future__ import annotations

from datetime import date, datetime

from domain.berechnung import UnzureichenderBestandError
from domain.entities import Kauf
from infrastructure.persistence.sqlalchemy_repos import (
    SqlAlchemyKaufRepository,
    SqlAlchemySchlusskursRepository,
)
from utils.db import current_session
from utils.fehler import ValidierungsFehler


def kaeufe_fuer_depot(depot_id: int):
    return SqlAlchemyKaufRepository(current_session()).list_for_depot(depot_id)


def get_kauf(kauf_id: int) -> Kauf | None:
    return SqlAlchemyKaufRepository(current_session()).get(kauf_id)


def _neuberechnen(depot_id: int, instrument_id: int, ab: datetime) -> None:
    from services.neuberechnung import nach_buchungsaenderung  # lazy: avoid cycle

    nach_buchungsaenderung(depot_id, instrument_id=instrument_id, ab_zeitpunkt=ab)


def _deckung(depot_id: int) -> None:
    from services.zahlungen import deckung_pruefen  # lazy: avoid cycle

    session = current_session()
    try:
        deckung_pruefen(depot_id)
    except ValidierungsFehler:
        session.rollback()
        raise


def backfill_empfohlen(instrument_id: int, kauf_zeitpunkt: datetime) -> bool:
    """True if the buy lies in the past and no closing-price history exists
    back to the buy date — the UI then asks whether to backfill (spec §6.9)."""
    kaufdatum = kauf_zeitpunkt.date()
    if kaufdatum >= date.today():
        return False
    repo = SqlAlchemySchlusskursRepository(current_session())
    return repo.get(instrument_id, kaufdatum) is None


def kauf_erfassen(depot_id: int, fields: dict) -> tuple[Kauf, bool]:
    """Create a buy. Returns (kauf, backfill_recommended)."""
    session = current_session()
    kauf = Kauf(depot_id=depot_id, **fields)
    SqlAlchemyKaufRepository(session).add(kauf)
    _deckung(depot_id)
    _neuberechnen(depot_id, kauf.instrument_id, kauf.kauf_zeitpunkt)
    session.commit()
    return kauf, backfill_empfohlen(kauf.instrument_id, kauf.kauf_zeitpunkt)


def kauf_bearbeiten(kauf_id: int, fields: dict) -> tuple[Kauf, bool]:
    """Edit a buy (incl. timestamp — changes FIFO order, spec §4.3)."""
    session = current_session()
    kauf = get_kauf(kauf_id)
    if kauf is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    fruehester = min(kauf.kauf_zeitpunkt, fields["kauf_zeitpunkt"])
    altes_instrument = kauf.instrument_id
    for schluessel, wert in fields.items():
        setattr(kauf, schluessel, wert)
    kauf.geaendert_am = datetime.now()
    session.flush()
    _deckung(kauf.depot_id)
    try:
        _neuberechnen(kauf.depot_id, altes_instrument, fruehester)
        if kauf.instrument_id != altes_instrument:
            _neuberechnen(kauf.depot_id, kauf.instrument_id, fruehester)
    except UnzureichenderBestandError:
        session.rollback()
        raise ValidierungsFehler("fehler.bestand_verkaeufe") from None
    session.commit()
    return kauf, backfill_empfohlen(kauf.instrument_id, kauf.kauf_zeitpunkt)


def kauf_loeschen(kauf_id: int) -> None:
    """Delete a buy; rejected if sales would exceed the remaining quantity."""
    session = current_session()
    kauf = get_kauf(kauf_id)
    if kauf is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    depot_id, instrument_id, zeitpunkt = kauf.depot_id, kauf.instrument_id, kauf.kauf_zeitpunkt
    SqlAlchemyKaufRepository(session).delete(kauf)
    session.flush()
    _deckung(depot_id)
    try:
        _neuberechnen(depot_id, instrument_id, zeitpunkt)
    except UnzureichenderBestandError:
        session.rollback()
        raise ValidierungsFehler("fehler.bestand_verkaeufe") from None
    session.commit()
