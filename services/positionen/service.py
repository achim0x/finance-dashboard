"""Position service (spec §5.1): aggregates open tranches per instrument and
computes the position KPIs, incl. FX conversion into the depot's base
currency (spec §5.7).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from domain.berechnung import OffeneTranche, offene_tranchen, positions_kennzahlen
from domain.berechnung.kennzahlen import PositionsKennzahlen
from domain.entities import Depot, Instrument, Kurs
from domain.enums import Verrechnungsmethode
from infrastructure.persistence.sqlalchemy_repos import (
    SqlAlchemyInstrumentRepository,
    SqlAlchemyKaufRepository,
    SqlAlchemyVerkaufRepository,
)
from utils.db import current_session, current_settings

ZERO = Decimal("0")


@dataclass
class PositionAnsicht:
    """One aggregated position, ready for display/serialization."""

    instrument: Instrument
    tranchen: list[OffeneTranche] = field(default_factory=list)
    kennzahlen: PositionsKennzahlen = field(default_factory=PositionsKennzahlen)
    kurs: Kurs | None = None
    kurs_veraltet: bool = False
    unkonvertiert: bool = False  # FX conversion unavailable (spec §5.7)
    fx_veraltet: bool = False    # converted with a stale FX rate


def _methode() -> Verrechnungsmethode:
    return Verrechnungsmethode(current_settings().verrechnungsmethode)


def _konvertiere(kz: PositionsKennzahlen, kurswert: Decimal) -> None:
    """Scale all monetary KPI fields by the FX rate (percentages stay)."""
    kz.einstandswert *= kurswert
    kz.positionswert *= kurswert
    kz.tagesveraenderung_eur *= kurswert
    kz.gesamtveraenderung_eur *= kurswert


def position_fuer_instrument(
    depot: Depot, instrument: Instrument, mit_kursen: bool = True
) -> PositionAnsicht | None:
    """Build the position view for one (depot, instrument); None if flat."""
    session = current_session()
    kaeufe = SqlAlchemyKaufRepository(session).list_for_position(depot.id, instrument.id)
    verkaeufe = SqlAlchemyVerkaufRepository(session).list_for_position(depot.id, instrument.id)
    tranchen = offene_tranchen(kaeufe, verkaeufe, _methode())
    if not tranchen:
        return None

    ansicht = PositionAnsicht(instrument=instrument, tranchen=tranchen)

    kurs = None
    if mit_kursen:
        from services.kurse import aktueller_kurs, kurs_ist_veraltet  # lazy: avoid cycle

        kurs = aktueller_kurs(instrument)
        ansicht.kurs = kurs
        if kurs is not None:
            ansicht.kurs_veraltet = kurs_ist_veraltet(kurs, instrument)

    ansicht.kennzahlen = positions_kennzahlen(
        tranchen,
        kurs.kurs if kurs is not None else None,
        kurs.vortagesschluss if kurs is not None else None,
    )

    # FX: current values are converted with the most recent rate (spec §5.7).
    if kurs is not None and instrument.waehrung != depot.basiswaehrung:
        from services.waehrung import rate  # lazy: avoid cycle
        from services.waehrung.service import UNKONVERTIERT, VERALTET

        wert, status = rate(instrument.waehrung, depot.basiswaehrung)
        if status == UNKONVERTIERT or wert is None:
            ansicht.unkonvertiert = True
        else:
            _konvertiere(ansicht.kennzahlen, wert)
            ansicht.fx_veraltet = status == VERALTET

    return ansicht


def positionen_fuer_depot(depot: Depot, mit_kursen: bool = True) -> list[PositionAnsicht]:
    """All open positions of a depot (spec §5.1), ordered by instrument name."""
    instrumente = SqlAlchemyInstrumentRepository(current_session()).list_in_depot(depot.id)
    ansichten = []
    for instrument in instrumente:
        ansicht = position_fuer_instrument(depot, instrument, mit_kursen=mit_kursen)
        if ansicht is not None:
            ansichten.append(ansicht)
    return ansichten
