"""Sale service: create/edit/delete with FIFO matching (spec §5.3) and the
stored realized gain (spec §4.4). Every change triggers recomputation of the
realized gains of the affected instrument (spec §5.6).
"""
from __future__ import annotations

from datetime import datetime

from domain.berechnung import UnzureichenderBestandError
from domain.entities import Verkauf
from infrastructure.persistence.sqlalchemy_repos import SqlAlchemyVerkaufRepository
from utils.db import current_session
from utils.fehler import ValidierungsFehler


def verkaeufe_fuer_depot(depot_id: int):
    return SqlAlchemyVerkaufRepository(current_session()).list_for_depot(depot_id)


def get_verkauf(verkauf_id: int) -> Verkauf | None:
    return SqlAlchemyVerkaufRepository(current_session()).get(verkauf_id)


def _neuberechnen(depot_id: int, instrument_id: int, ab: datetime) -> None:
    """Recompute realized gains + valuation series; translate an oversell
    into a validation error and roll back."""
    from services.neuberechnung import nach_buchungsaenderung  # lazy: avoid cycle

    session = current_session()
    try:
        nach_buchungsaenderung(depot_id, instrument_id=instrument_id, ab_zeitpunkt=ab)
    except UnzureichenderBestandError:
        session.rollback()
        raise ValidierungsFehler("fehler.bestand_unzureichend") from None


def verkauf_erfassen(depot_id: int, fields: dict) -> Verkauf:
    session = current_session()
    verkauf = Verkauf(depot_id=depot_id, **fields)
    SqlAlchemyVerkaufRepository(session).add(verkauf)
    _neuberechnen(depot_id, verkauf.instrument_id, verkauf.verkauf_zeitpunkt)
    session.commit()
    return verkauf


def verkauf_bearbeiten(verkauf_id: int, fields: dict) -> Verkauf:
    session = current_session()
    verkauf = get_verkauf(verkauf_id)
    if verkauf is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    fruehester = min(verkauf.verkauf_zeitpunkt, fields["verkauf_zeitpunkt"])
    altes_instrument = verkauf.instrument_id
    for schluessel, wert in fields.items():
        setattr(verkauf, schluessel, wert)
    verkauf.geaendert_am = datetime.now()
    session.flush()
    _neuberechnen(verkauf.depot_id, altes_instrument, fruehester)
    if verkauf.instrument_id != altes_instrument:
        _neuberechnen(verkauf.depot_id, verkauf.instrument_id, fruehester)
    session.commit()
    return verkauf


def verkauf_loeschen(verkauf_id: int) -> None:
    session = current_session()
    verkauf = get_verkauf(verkauf_id)
    if verkauf is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    depot_id, instrument_id, zeitpunkt = (
        verkauf.depot_id,
        verkauf.instrument_id,
        verkauf.verkauf_zeitpunkt,
    )
    SqlAlchemyVerkaufRepository(session).delete(verkauf)
    session.flush()
    _neuberechnen(depot_id, instrument_id, zeitpunkt)
    session.commit()
