"""Cash bookings and the derived cash balance (spec §5.2).

`deckung_pruefen` is the coverage check shared with the buy service: after a
booking is flushed (but before commit) the running balance must never dip
below zero unless overdrawing is enabled.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from domain.berechnung.ledger import barbestand as _barbestand_berechnen
from domain.berechnung.ledger import min_laufender_saldo
from domain.entities import Zahlung
from domain.enums import ZahlungTyp
from infrastructure.persistence.sqlalchemy_repos import (
    SqlAlchemyDividendeRepository,
    SqlAlchemyKaufRepository,
    SqlAlchemySteuerverrechnungRepository,
    SqlAlchemyVerkaufRepository,
    SqlAlchemyZahlungRepository,
)
from utils.db import current_session, current_settings
from utils.fehler import ValidierungsFehler


def _alle_cash_quellen(depot_id: int):
    s = current_session()
    return {
        "zahlungen": SqlAlchemyZahlungRepository(s).list_for_depot(depot_id),
        "kaeufe": SqlAlchemyKaufRepository(s).list_for_depot(depot_id),
        "verkaeufe": SqlAlchemyVerkaufRepository(s).list_for_depot(depot_id),
        "dividenden": SqlAlchemyDividendeRepository(s).list_for_depot(depot_id),
        "steuerverrechnungen": SqlAlchemySteuerverrechnungRepository(s).list_for_depot(depot_id),
    }


def barbestand(depot_id: int, bis: datetime | None = None) -> Decimal:
    """Derived cash balance (spec §5.2) — never stored, always recomputed."""
    return _barbestand_berechnen(bis=bis, **_alle_cash_quellen(depot_id))


def deckung_pruefen(depot_id: int) -> None:
    """Raise if the running balance would dip below zero (spec §5.2).

    Called after flush so pending changes are visible to the queries; the
    caller rolls back on error. Skipped entirely when overdrawing is enabled.
    """
    if current_settings().barbestand_ueberziehen_erlauben:
        return
    if min_laufender_saldo(**_alle_cash_quellen(depot_id)) < Decimal("0"):
        raise ValidierungsFehler("fehler.deckung")


def zahlungen_fuer_depot(depot_id: int):
    return SqlAlchemyZahlungRepository(current_session()).list_for_depot(depot_id)


def get_zahlung(zahlung_id: int) -> Zahlung | None:
    return SqlAlchemyZahlungRepository(current_session()).get(zahlung_id)


def _neuberechnen(depot_id: int, ab: datetime) -> None:
    from services.neuberechnung import nach_buchungsaenderung  # lazy: avoid cycle

    nach_buchungsaenderung(depot_id, ab_zeitpunkt=ab)


def zahlung_erfassen(depot_id: int, fields: dict) -> Zahlung:
    session = current_session()
    zahlung = Zahlung(depot_id=depot_id, **fields)
    SqlAlchemyZahlungRepository(session).add(zahlung)
    try:
        if fields["typ"] == ZahlungTyp.AUSZAHLUNG.value:
            deckung_pruefen(depot_id)
    except ValidierungsFehler:
        session.rollback()
        raise
    _neuberechnen(depot_id, zahlung.zeitpunkt)
    session.commit()
    return zahlung


def zahlung_bearbeiten(zahlung_id: int, fields: dict) -> Zahlung:
    session = current_session()
    zahlung = get_zahlung(zahlung_id)
    if zahlung is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    fruehester = min(zahlung.zeitpunkt, fields["zeitpunkt"])
    for schluessel, wert in fields.items():
        setattr(zahlung, schluessel, wert)
    zahlung.geaendert_am = datetime.now()
    session.flush()
    try:
        deckung_pruefen(zahlung.depot_id)
    except ValidierungsFehler:
        session.rollback()
        raise
    _neuberechnen(zahlung.depot_id, fruehester)
    session.commit()
    return zahlung


def zahlung_loeschen(zahlung_id: int) -> None:
    session = current_session()
    zahlung = get_zahlung(zahlung_id)
    if zahlung is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    depot_id, zeitpunkt = zahlung.depot_id, zahlung.zeitpunkt
    SqlAlchemyZahlungRepository(session).delete(zahlung)
    session.flush()
    try:
        deckung_pruefen(depot_id)
    except ValidierungsFehler:
        session.rollback()
        raise
    _neuberechnen(depot_id, zeitpunkt)
    session.commit()
