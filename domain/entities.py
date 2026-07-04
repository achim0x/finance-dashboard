"""SQLAlchemy 2.0 entities (spec §4).

Column names are German domain terms by design. Monetary amounts and prices
are `Decimal` (`Numeric`), never floats. Derived state (cash balance, open
positions, KPIs) is intentionally NOT stored — it is recomputed from the
bookings (spec §4.11/§5.6). Only `Verkauf.realisierter_gewinn`, the daily
`DepotBewertung` series and frozen `DepotSnapshot` rows are persisted.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from domain.enums import (
    Bezugsbasis,
    Kategorie,
    KursQuelle,
    Kursgruppe,
    KURSGRUPPE_JE_KATEGORIE,
    ZahlungTyp,
    Zeitraum,
)

# Numeric precision for money/prices: 18 digits, 6 decimal places. Display
# rounding to 2 places happens only in the formatting layer (spec §5).
GELD = Numeric(18, 6)


class Base(DeclarativeBase):
    pass


class Depot(Base):
    """A paper portfolio (spec §4.1). The cash balance is derived, not stored."""

    __tablename__ = "depots"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    eroeffnet_am: Mapped[date] = mapped_column(Date)
    basiswaehrung: Mapped[str] = mapped_column(String(3), default="EUR")
    notiz: Mapped[str | None] = mapped_column(Text, default=None)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Display defaults for chart & performance (spec §4.1/§5.5)
    default_zeitraum: Mapped[str] = mapped_column(
        String(30), default=Zeitraum.SEIT_EROEFFNUNG.value
    )
    default_bezugsbasis: Mapped[str] = mapped_column(
        String(30), default=Bezugsbasis.INKL_BARBESTAND.value
    )

    kaeufe: Mapped[list["Kauf"]] = relationship(back_populates="depot")
    verkaeufe: Mapped[list["Verkauf"]] = relationship(back_populates="depot")


class Instrument(Base):
    """A tradable security identified by ISIN/WKN (spec §4.2)."""

    __tablename__ = "instrumente"

    id: Mapped[int] = mapped_column(primary_key=True)
    isin: Mapped[str] = mapped_column(String(12), unique=True)
    wkn: Mapped[str | None] = mapped_column(String(10), default=None)
    name: Mapped[str] = mapped_column(String(200))
    kategorie: Mapped[str] = mapped_column(String(30))
    waehrung: Mapped[str] = mapped_column(String(3), default="EUR")
    referenzboerse: Mapped[str | None] = mapped_column(String(50), default=None)
    # Provider ticker mapping (e.g. FMP symbol); resolved lazily and cached.
    symbol: Mapped[str | None] = mapped_column(String(50), default=None)
    # Underlying, for leveraged products.
    basiswert: Mapped[str | None] = mapped_column(String(200), default=None)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    @property
    def kursgruppe(self) -> Kursgruppe:
        """Price group derived from the category; drives provider routing."""
        return KURSGRUPPE_JE_KATEGORIE[Kategorie(self.kategorie)]


class Kauf(Base):
    """A single buy (tranche, spec §4.3). FIFO order follows kauf_zeitpunkt."""

    __tablename__ = "kaeufe"

    id: Mapped[int] = mapped_column(primary_key=True)
    depot_id: Mapped[int] = mapped_column(ForeignKey("depots.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instrumente.id"), index=True)
    stueck: Mapped[Decimal] = mapped_column(GELD)
    kaufkurs: Mapped[Decimal] = mapped_column(GELD)
    kauf_zeitpunkt: Mapped[datetime] = mapped_column(DateTime)  # editable
    spesen: Mapped[Decimal] = mapped_column(GELD, default=Decimal("0"))
    boerse: Mapped[str | None] = mapped_column(String(50), default=None)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    geaendert_am: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    depot: Mapped["Depot"] = relationship(back_populates="kaeufe")
    instrument: Mapped["Instrument"] = relationship()

    @property
    def kaufwert(self) -> Decimal:
        """Derived: stueck * kaufkurs + spesen (spec §4.3)."""
        return self.stueck * self.kaufkurs + self.spesen


class Verkauf(Base):
    """A sale (spec §4.4). realisierter_gewinn is stored for traceability."""

    __tablename__ = "verkaeufe"

    id: Mapped[int] = mapped_column(primary_key=True)
    depot_id: Mapped[int] = mapped_column(ForeignKey("depots.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instrumente.id"), index=True)
    stueck: Mapped[Decimal] = mapped_column(GELD)
    verkaufskurs: Mapped[Decimal] = mapped_column(GELD)
    verkauf_zeitpunkt: Mapped[datetime] = mapped_column(DateTime)  # editable
    spesen: Mapped[Decimal] = mapped_column(GELD, default=Decimal("0"))
    # Tax paid on the sale; reduces the cash balance but is NOT part of
    # realisierter_gewinn (spec §4.4/§5.4).
    steuer: Mapped[Decimal] = mapped_column(GELD, default=Decimal("0"))
    boerse: Mapped[str | None] = mapped_column(String(50), default=None)
    realisierter_gewinn: Mapped[Decimal] = mapped_column(GELD, default=Decimal("0"))
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    geaendert_am: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    depot: Mapped["Depot"] = relationship(back_populates="verkaeufe")
    instrument: Mapped["Instrument"] = relationship()

    @property
    def erloes(self) -> Decimal:
        """Gross proceeds: stueck * verkaufskurs (spec §5.3)."""
        return self.stueck * self.verkaufskurs


class Zahlung(Base):
    """Cash deposit/withdrawal (spec §4.5)."""

    __tablename__ = "zahlungen"

    id: Mapped[int] = mapped_column(primary_key=True)
    depot_id: Mapped[int] = mapped_column(ForeignKey("depots.id"), index=True)
    typ: Mapped[str] = mapped_column(String(20))  # ZahlungTyp
    betrag: Mapped[Decimal] = mapped_column(GELD)  # > 0
    zeitpunkt: Mapped[datetime] = mapped_column(DateTime)  # editable
    notiz: Mapped[str | None] = mapped_column(Text, default=None)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    geaendert_am: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    @property
    def typ_enum(self) -> ZahlungTyp:
        return ZahlungTyp(self.typ)


class Kurs(Base):
    """A timestamped quote of an instrument (spec §4.6). History is kept."""

    __tablename__ = "kurse"

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instrumente.id"), index=True)
    kurs: Mapped[Decimal] = mapped_column(GELD)
    waehrung: Mapped[str] = mapped_column(String(3), default="EUR")
    boerse: Mapped[str | None] = mapped_column(String(50), default=None)
    zeitstempel: Mapped[datetime] = mapped_column(DateTime, index=True)
    quelle: Mapped[str] = mapped_column(String(20))  # KursQuelle
    # Previous close — basis of the daily change (spec §5.1).
    vortagesschluss: Mapped[Decimal | None] = mapped_column(GELD, default=None)


class Schlusskurs(Base):
    """Daily closing price per instrument (spec §6.9), feeds the mini charts
    and the historical revaluation (§5.6)."""

    __tablename__ = "schlusskurse"
    __table_args__ = (UniqueConstraint("instrument_id", "datum"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instrumente.id"), index=True)
    datum: Mapped[date] = mapped_column(Date)
    schlusskurs: Mapped[Decimal] = mapped_column(GELD)
    quelle: Mapped[str] = mapped_column(String(20), default=KursQuelle.MANUELL.value)


class DepotBewertung(Base):
    """Automatic daily valuation snapshot (spec §4.7). Holds BOTH series so
    the reference-basis toggle needs no recomputation (§5.5)."""

    __tablename__ = "depot_bewertungen"
    __table_args__ = (UniqueConstraint("depot_id", "datum"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    depot_id: Mapped[int] = mapped_column(ForeignKey("depots.id"), index=True)
    datum: Mapped[date] = mapped_column(Date)
    depotbestand: Mapped[Decimal] = mapped_column(GELD)
    barbestand: Mapped[Decimal] = mapped_column(GELD)
    gesamtwert: Mapped[Decimal] = mapped_column(GELD)


class Dividende(Base):
    """Received dividend, credited to the cash balance (spec §4.8)."""

    __tablename__ = "dividenden"

    id: Mapped[int] = mapped_column(primary_key=True)
    depot_id: Mapped[int] = mapped_column(ForeignKey("depots.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instrumente.id"), index=True)
    betrag: Mapped[Decimal] = mapped_column(GELD)  # > 0, credited amount
    zeitpunkt: Mapped[datetime] = mapped_column(DateTime)  # editable
    notiz: Mapped[str | None] = mapped_column(Text, default=None)
    # Informational only; `betrag` is authoritative (spec §4.8).
    betrag_je_anteil: Mapped[Decimal | None] = mapped_column(GELD, default=None)
    stueck_zum_zeitpunkt: Mapped[Decimal | None] = mapped_column(GELD, default=None)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    geaendert_am: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    instrument: Mapped["Instrument"] = relationship()


class Steuerverrechnung(Base):
    """Portfolio-wide tax refund/settlement credited to cash (spec §4.9)."""

    __tablename__ = "steuerverrechnungen"

    id: Mapped[int] = mapped_column(primary_key=True)
    depot_id: Mapped[int] = mapped_column(ForeignKey("depots.id"), index=True)
    betrag: Mapped[Decimal] = mapped_column(GELD)  # > 0, credited amount
    zeitpunkt: Mapped[datetime] = mapped_column(DateTime)  # editable
    notiz: Mapped[str | None] = mapped_column(Text, default=None)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    geaendert_am: Mapped[datetime | None] = mapped_column(DateTime, default=None)


class DepotSnapshot(Base):
    """Manually created, named snapshot for comparisons (spec §4.10).
    Deliberately immutable once created (§4.11)."""

    __tablename__ = "depot_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    depot_id: Mapped[int] = mapped_column(ForeignKey("depots.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    notiz: Mapped[str | None] = mapped_column(Text, default=None)

    # Frozen KPIs at creation time.
    depotbestand: Mapped[Decimal] = mapped_column(GELD)
    barbestand: Mapped[Decimal] = mapped_column(GELD)
    gesamtwert: Mapped[Decimal] = mapped_column(GELD)
    realisierter_gewinn: Mapped[Decimal] = mapped_column(GELD)
    unrealisierter_gewinn: Mapped[Decimal] = mapped_column(GELD)
    dividenden: Mapped[Decimal] = mapped_column(GELD)
    steuern: Mapped[Decimal] = mapped_column(GELD)
    gesamtgewinn: Mapped[Decimal] = mapped_column(GELD)
    gesamtergebnis: Mapped[Decimal] = mapped_column(GELD)

    # Frozen position details (instrument, stueck, einstandswert, wert,
    # gewichtung) as JSON for the detailed comparison.
    positionen_json: Mapped[str] = mapped_column(Text, default="[]")


class KursEinstellung(Base):
    """Runtime price-provider configuration per price group (spec §6.6).
    Exactly one row per Kursgruppe; credentials are encrypted at rest."""

    __tablename__ = "kurs_einstellungen"

    id: Mapped[int] = mapped_column(primary_key=True)
    kursgruppe: Mapped[str] = mapped_column(String(30), unique=True)  # Kursgruppe
    provider_name: Mapped[str] = mapped_column(String(50))
    credentials_verschluesselt: Mapped[str | None] = mapped_column(Text, default=None)
    abfrage_intervall_sekunden: Mapped[int] = mapped_column(default=300)
    aktiv: Mapped[bool] = mapped_column(default=True)
    geaendert_am: Mapped[datetime | None] = mapped_column(DateTime, default=None)


class WaehrungsEinstellung(Base):
    """Runtime FX-provider configuration (spec §6.10). Exactly one row."""

    __tablename__ = "waehrungs_einstellungen"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(50))
    credentials_verschluesselt: Mapped[str | None] = mapped_column(Text, default=None)
    abfrage_intervall_sekunden: Mapped[int] = mapped_column(default=3600)
    aktiv: Mapped[bool] = mapped_column(default=True)
    geaendert_am: Mapped[datetime | None] = mapped_column(DateTime, default=None)


class Wechselkurs(Base):
    """Cached FX rate (current and daily-historical, spec §5.7/§6.10)."""

    __tablename__ = "wechselkurse"
    __table_args__ = (UniqueConstraint("von", "nach", "datum"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    von: Mapped[str] = mapped_column(String(3))
    nach: Mapped[str] = mapped_column(String(3))
    # Rate date; the row with the latest datum is the "current" rate.
    datum: Mapped[date] = mapped_column(Date)
    kurs: Mapped[Decimal] = mapped_column(GELD)
    zeitstempel: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    quelle: Mapped[str] = mapped_column(String(20), default="fmp")
