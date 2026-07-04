"""Dividend service (spec §4.8): credited to cash, own KPI (REQ-DIV-KPI)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from domain.entities import Dividende
from infrastructure.persistence.sqlalchemy_repos import SqlAlchemyDividendeRepository
from utils.db import current_session
from utils.fehler import ValidierungsFehler


def dividenden_fuer_depot(depot_id: int):
    return SqlAlchemyDividendeRepository(current_session()).list_for_depot(depot_id)


def get_dividende(dividende_id: int) -> Dividende | None:
    return SqlAlchemyDividendeRepository(current_session()).get(dividende_id)


def dividenden_summe(depot_id: int) -> Decimal:
    """Dividends KPI (spec §5.4)."""
    return sum((d.betrag for d in dividenden_fuer_depot(depot_id)), Decimal("0"))


def _neuberechnen(depot_id: int, ab: datetime) -> None:
    from services.neuberechnung import nach_buchungsaenderung  # lazy: avoid cycle

    nach_buchungsaenderung(depot_id, ab_zeitpunkt=ab)


def dividende_erfassen(depot_id: int, fields: dict) -> Dividende:
    session = current_session()
    dividende = Dividende(depot_id=depot_id, **fields)
    SqlAlchemyDividendeRepository(session).add(dividende)
    _neuberechnen(depot_id, dividende.zeitpunkt)
    session.commit()
    return dividende


def dividende_bearbeiten(dividende_id: int, fields: dict) -> Dividende:
    session = current_session()
    dividende = get_dividende(dividende_id)
    if dividende is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    fruehester = min(dividende.zeitpunkt, fields["zeitpunkt"])
    for schluessel, wert in fields.items():
        setattr(dividende, schluessel, wert)
    dividende.geaendert_am = datetime.now()
    session.flush()
    _neuberechnen(dividende.depot_id, fruehester)
    session.commit()
    return dividende


def dividende_loeschen(dividende_id: int) -> None:
    session = current_session()
    dividende = get_dividende(dividende_id)
    if dividende is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    depot_id, zeitpunkt = dividende.depot_id, dividende.zeitpunkt
    SqlAlchemyDividendeRepository(session).delete(dividende)
    session.flush()
    from services.zahlungen import deckung_pruefen  # lazy: avoid cycle

    try:
        deckung_pruefen(depot_id)
    except ValidierungsFehler:
        session.rollback()
        raise
    _neuberechnen(depot_id, zeitpunkt)
    session.commit()
