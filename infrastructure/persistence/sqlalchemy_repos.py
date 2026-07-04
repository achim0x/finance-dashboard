"""Concrete SQLAlchemy repositories implementing `domain.repositories`.

All DB access of the app goes through these classes — parametrized queries
only, no string-built SQL anywhere.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.entities import (
    Depot,
    DepotBewertung,
    DepotSnapshot,
    Dividende,
    Instrument,
    Kauf,
    Kurs,
    KursEinstellung,
    Schlusskurs,
    Steuerverrechnung,
    Verkauf,
    WaehrungsEinstellung,
    Wechselkurs,
    Zahlung,
)


class _Repo:
    def __init__(self, session: Session):
        self._s = session


class SqlAlchemyDepotRepository(_Repo):
    def list_all(self):
        return self._s.scalars(select(Depot).order_by(Depot.name)).all()

    def get(self, depot_id):
        return self._s.get(Depot, depot_id)

    def get_by_name(self, name):
        return self._s.scalar(select(Depot).where(Depot.name == name))

    def add(self, depot):
        self._s.add(depot)
        self._s.flush()
        return depot

    def delete(self, depot):
        self._s.delete(depot)


class SqlAlchemyInstrumentRepository(_Repo):
    def list_all(self):
        return self._s.scalars(select(Instrument).order_by(Instrument.name)).all()

    def get(self, instrument_id):
        return self._s.get(Instrument, instrument_id)

    def get_by_isin(self, isin):
        return self._s.scalar(select(Instrument).where(Instrument.isin == isin))

    def search(self, begriff):
        muster = f"%{begriff}%"
        stmt = (
            select(Instrument)
            .where(
                Instrument.isin.ilike(muster)
                | Instrument.wkn.ilike(muster)
                | Instrument.name.ilike(muster)
            )
            .order_by(Instrument.name)
        )
        return self._s.scalars(stmt).all()

    def add(self, instrument):
        self._s.add(instrument)
        self._s.flush()
        return instrument

    def list_in_depot(self, depot_id):
        """Instruments that have at least one buy in the depot."""
        stmt = (
            select(Instrument)
            .join(Kauf, Kauf.instrument_id == Instrument.id)
            .where(Kauf.depot_id == depot_id)
            .distinct()
            .order_by(Instrument.name)
        )
        return self._s.scalars(stmt).all()


class _BuchungRepo(_Repo):
    """Shared list/get/add/delete for booking entities."""

    entity = None
    zeit_attr = "zeitpunkt"

    def get(self, id_):
        return self._s.get(self.entity, id_)

    def list_for_depot(self, depot_id):
        zeit = getattr(self.entity, self.zeit_attr)
        stmt = (
            select(self.entity)
            .where(self.entity.depot_id == depot_id)
            .order_by(zeit, self.entity.id)
        )
        return self._s.scalars(stmt).all()

    def add(self, obj):
        self._s.add(obj)
        self._s.flush()
        return obj

    def delete(self, obj):
        self._s.delete(obj)


class SqlAlchemyKaufRepository(_BuchungRepo):
    entity = Kauf
    zeit_attr = "kauf_zeitpunkt"

    def list_for_position(self, depot_id, instrument_id):
        stmt = (
            select(Kauf)
            .where(Kauf.depot_id == depot_id, Kauf.instrument_id == instrument_id)
            .order_by(Kauf.kauf_zeitpunkt, Kauf.id)
        )
        return self._s.scalars(stmt).all()


class SqlAlchemyVerkaufRepository(_BuchungRepo):
    entity = Verkauf
    zeit_attr = "verkauf_zeitpunkt"

    def list_for_position(self, depot_id, instrument_id):
        stmt = (
            select(Verkauf)
            .where(Verkauf.depot_id == depot_id, Verkauf.instrument_id == instrument_id)
            .order_by(Verkauf.verkauf_zeitpunkt, Verkauf.id)
        )
        return self._s.scalars(stmt).all()


class SqlAlchemyZahlungRepository(_BuchungRepo):
    entity = Zahlung


class SqlAlchemyDividendeRepository(_BuchungRepo):
    entity = Dividende


class SqlAlchemySteuerverrechnungRepository(_BuchungRepo):
    entity = Steuerverrechnung


class SqlAlchemyKursRepository(_Repo):
    def latest(self, instrument_id):
        stmt = (
            select(Kurs)
            .where(Kurs.instrument_id == instrument_id)
            .order_by(Kurs.zeitstempel.desc(), Kurs.id.desc())
            .limit(1)
        )
        return self._s.scalar(stmt)

    def add(self, kurs):
        self._s.add(kurs)
        self._s.flush()
        return kurs

    def history(self, instrument_id, ab: datetime):
        stmt = (
            select(Kurs)
            .where(Kurs.instrument_id == instrument_id, Kurs.zeitstempel >= ab)
            .order_by(Kurs.zeitstempel)
        )
        return self._s.scalars(stmt).all()


class SqlAlchemySchlusskursRepository(_Repo):
    def get(self, instrument_id, datum: date):
        stmt = select(Schlusskurs).where(
            Schlusskurs.instrument_id == instrument_id, Schlusskurs.datum == datum
        )
        return self._s.scalar(stmt)

    def upsert(self, instrument_id, datum, kurs: Decimal, quelle: str):
        """Idempotent per (instrument, date) — spec §6.9."""
        vorhanden = self.get(instrument_id, datum)
        if vorhanden is not None:
            vorhanden.schlusskurs = kurs
            vorhanden.quelle = quelle
            self._s.flush()
            return vorhanden
        neu = Schlusskurs(
            instrument_id=instrument_id, datum=datum, schlusskurs=kurs, quelle=quelle
        )
        self._s.add(neu)
        self._s.flush()
        return neu

    def series(self, instrument_id, ab: date, bis: date | None = None):
        stmt = select(Schlusskurs).where(
            Schlusskurs.instrument_id == instrument_id, Schlusskurs.datum >= ab
        )
        if bis is not None:
            stmt = stmt.where(Schlusskurs.datum <= bis)
        return self._s.scalars(stmt.order_by(Schlusskurs.datum)).all()

    def latest_before(self, instrument_id, datum: date):
        stmt = (
            select(Schlusskurs)
            .where(
                Schlusskurs.instrument_id == instrument_id,
                Schlusskurs.datum <= datum,
            )
            .order_by(Schlusskurs.datum.desc())
            .limit(1)
        )
        return self._s.scalar(stmt)


class SqlAlchemyDepotBewertungRepository(_Repo):
    def series(self, depot_id, ab=None, bis=None):
        stmt = select(DepotBewertung).where(DepotBewertung.depot_id == depot_id)
        if ab is not None:
            stmt = stmt.where(DepotBewertung.datum >= ab)
        if bis is not None:
            stmt = stmt.where(DepotBewertung.datum <= bis)
        return self._s.scalars(stmt.order_by(DepotBewertung.datum)).all()

    def upsert(self, depot_id, datum, depotbestand, barbestand, gesamtwert):
        stmt = select(DepotBewertung).where(
            DepotBewertung.depot_id == depot_id, DepotBewertung.datum == datum
        )
        vorhanden = self._s.scalar(stmt)
        if vorhanden is not None:
            vorhanden.depotbestand = depotbestand
            vorhanden.barbestand = barbestand
            vorhanden.gesamtwert = gesamtwert
            self._s.flush()
            return vorhanden
        neu = DepotBewertung(
            depot_id=depot_id,
            datum=datum,
            depotbestand=depotbestand,
            barbestand=barbestand,
            gesamtwert=gesamtwert,
        )
        self._s.add(neu)
        self._s.flush()
        return neu

    def delete_from(self, depot_id, ab: date):
        for row in self.series(depot_id, ab=ab):
            self._s.delete(row)
        self._s.flush()


class SqlAlchemySnapshotRepository(_Repo):
    def get(self, snapshot_id):
        return self._s.get(DepotSnapshot, snapshot_id)

    def list_for_depot(self, depot_id):
        stmt = (
            select(DepotSnapshot)
            .where(DepotSnapshot.depot_id == depot_id)
            .order_by(DepotSnapshot.erstellt_am.desc())
        )
        return self._s.scalars(stmt).all()

    def add(self, snapshot):
        self._s.add(snapshot)
        self._s.flush()
        return snapshot

    def delete(self, snapshot):
        self._s.delete(snapshot)


class SqlAlchemyKursEinstellungRepository(_Repo):
    def get_for_gruppe(self, kursgruppe: str):
        stmt = select(KursEinstellung).where(KursEinstellung.kursgruppe == kursgruppe)
        return self._s.scalar(stmt)

    def list_all(self):
        return self._s.scalars(select(KursEinstellung)).all()

    def add(self, einstellung):
        self._s.add(einstellung)
        self._s.flush()
        return einstellung


class SqlAlchemyWaehrungsEinstellungRepository(_Repo):
    def get_single(self):
        return self._s.scalar(select(WaehrungsEinstellung).limit(1))

    def add(self, einstellung):
        self._s.add(einstellung)
        self._s.flush()
        return einstellung


class SqlAlchemyWechselkursRepository(_Repo):
    def latest(self, von, nach):
        stmt = (
            select(Wechselkurs)
            .where(Wechselkurs.von == von, Wechselkurs.nach == nach)
            .order_by(Wechselkurs.datum.desc())
            .limit(1)
        )
        return self._s.scalar(stmt)

    def get_am(self, von, nach, datum):
        stmt = select(Wechselkurs).where(
            Wechselkurs.von == von, Wechselkurs.nach == nach, Wechselkurs.datum == datum
        )
        return self._s.scalar(stmt)

    def latest_before(self, von, nach, datum):
        stmt = (
            select(Wechselkurs)
            .where(
                Wechselkurs.von == von,
                Wechselkurs.nach == nach,
                Wechselkurs.datum <= datum,
            )
            .order_by(Wechselkurs.datum.desc())
            .limit(1)
        )
        return self._s.scalar(stmt)

    def upsert(self, von, nach, datum, kurs, quelle):
        vorhanden = self.get_am(von, nach, datum)
        if vorhanden is not None:
            vorhanden.kurs = kurs
            vorhanden.quelle = quelle
            vorhanden.zeitstempel = datetime.now()
            self._s.flush()
            return vorhanden
        neu = Wechselkurs(von=von, nach=nach, datum=datum, kurs=kurs, quelle=quelle)
        self._s.add(neu)
        self._s.flush()
        return neu
