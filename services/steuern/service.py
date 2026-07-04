"""Tax service (spec §4.9/§5.4): settlements credit the cash balance; the
tax KPI is `paid sale taxes − settlements` (REQ-TAX-KPI).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from domain.entities import Steuerverrechnung
from infrastructure.persistence.sqlalchemy_repos import (
    SqlAlchemySteuerverrechnungRepository,
    SqlAlchemyVerkaufRepository,
)
from utils.db import current_session
from utils.fehler import ValidierungsFehler


def steuerverrechnungen_fuer_depot(depot_id: int):
    return SqlAlchemySteuerverrechnungRepository(current_session()).list_for_depot(depot_id)


def get_steuerverrechnung(id_: int) -> Steuerverrechnung | None:
    return SqlAlchemySteuerverrechnungRepository(current_session()).get(id_)


def gezahlte_steuern(depot_id: int) -> Decimal:
    """Sum of taxes paid on sales (spec §4.4)."""
    verkaeufe = SqlAlchemyVerkaufRepository(current_session()).list_for_depot(depot_id)
    return sum((v.steuer for v in verkaeufe), Decimal("0"))


def verrechnete_steuern(depot_id: int) -> Decimal:
    return sum((s.betrag for s in steuerverrechnungen_fuer_depot(depot_id)), Decimal("0"))


def steuern_saldo(depot_id: int) -> Decimal:
    """Tax KPI: paid − settled; positive = net paid (spec §5.4)."""
    return gezahlte_steuern(depot_id) - verrechnete_steuern(depot_id)


def _neuberechnen(depot_id: int, ab: datetime) -> None:
    from services.neuberechnung import nach_buchungsaenderung  # lazy: avoid cycle

    nach_buchungsaenderung(depot_id, ab_zeitpunkt=ab)


def steuerverrechnung_erfassen(depot_id: int, fields: dict) -> Steuerverrechnung:
    session = current_session()
    sv = Steuerverrechnung(depot_id=depot_id, **fields)
    SqlAlchemySteuerverrechnungRepository(session).add(sv)
    _neuberechnen(depot_id, sv.zeitpunkt)
    session.commit()
    return sv


def steuerverrechnung_bearbeiten(id_: int, fields: dict) -> Steuerverrechnung:
    session = current_session()
    sv = get_steuerverrechnung(id_)
    if sv is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    fruehester = min(sv.zeitpunkt, fields["zeitpunkt"])
    for schluessel, wert in fields.items():
        setattr(sv, schluessel, wert)
    sv.geaendert_am = datetime.now()
    session.flush()
    _neuberechnen(sv.depot_id, fruehester)
    session.commit()
    return sv


def steuerverrechnung_loeschen(id_: int) -> None:
    session = current_session()
    sv = get_steuerverrechnung(id_)
    if sv is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    depot_id, zeitpunkt = sv.depot_id, sv.zeitpunkt
    SqlAlchemySteuerverrechnungRepository(session).delete(sv)
    session.flush()
    from services.zahlungen import deckung_pruefen  # lazy: avoid cycle

    try:
        deckung_pruefen(depot_id)
    except ValidierungsFehler:
        session.rollback()
        raise
    _neuberechnen(depot_id, zeitpunkt)
    session.commit()
