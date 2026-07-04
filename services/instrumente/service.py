"""Instrument service: search/create, category -> price-group mapping."""
from __future__ import annotations

from domain.entities import Instrument
from infrastructure.persistence.sqlalchemy_repos import SqlAlchemyInstrumentRepository
from utils.db import current_session
from utils.fehler import ValidierungsFehler


def _repo():
    return SqlAlchemyInstrumentRepository(current_session())


def alle_instrumente():
    return _repo().list_all()


def get_instrument(instrument_id: int) -> Instrument | None:
    return _repo().get(instrument_id)


def get_instrument_by_isin(isin: str) -> Instrument | None:
    return _repo().get_by_isin(isin.strip().upper())


def suchen(begriff: str):
    """Search by ISIN/WKN/name (spec §7 'Wert hinzufügen')."""
    begriff = (begriff or "").strip()
    if not begriff:
        return []
    return _repo().search(begriff)


def instrumente_im_depot(depot_id: int):
    return _repo().list_in_depot(depot_id)


def instrument_anlegen(fields: dict) -> Instrument:
    repo = _repo()
    if repo.get_by_isin(fields["isin"]) is not None:
        raise ValidierungsFehler("fehler.isin_vorhanden")
    instrument = Instrument(**fields)
    repo.add(instrument)
    current_session().commit()
    return instrument
