"""Position and depot KPIs (spec §5.1/§5.4). Pure functions.

All monetary inputs are expected in the depot's base currency — FX
conversion happens in the service layer before calling these functions
(spec §5.7). Percentages are returned as fractions (0.05 = 5 %); display
rounding happens in the formatting layer only.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .fifo import OffeneTranche

ZERO = Decimal("0")


@dataclass
class PositionsKennzahlen:
    """KPIs of one aggregated position (spec §5.1)."""

    offene_stueck: Decimal = ZERO
    einstandswert: Decimal = ZERO
    positionswert: Decimal = ZERO           # "Wert in EUR"
    tagesveraenderung_eur: Decimal = ZERO   # "akt. EUR"
    tagesveraenderung_pct: Decimal | None = None
    gesamtveraenderung_eur: Decimal = ZERO  # "ges. EUR"
    gesamtveraenderung_pct: Decimal | None = None
    gewichtung: Decimal | None = None       # filled in by depot_kennzahlen
    kurs_vorhanden: bool = False


def positions_kennzahlen(
    tranchen: list[OffeneTranche],
    aktueller_kurs: Decimal | None,
    vortagesschluss: Decimal | None,
) -> PositionsKennzahlen:
    """KPIs for one (depot, instrument) position from its open tranches.

    `aktueller_kurs`/`vortagesschluss` must already be converted to the
    depot's base currency. If no current quote exists, value-dependent
    figures stay at zero/None and `kurs_vorhanden` is False.
    """
    kz = PositionsKennzahlen()
    kz.offene_stueck = sum((t.offene_stueck for t in tranchen), ZERO)
    kz.einstandswert = sum((t.einstandswert for t in tranchen), ZERO)

    if aktueller_kurs is None or kz.offene_stueck == ZERO:
        return kz

    kz.kurs_vorhanden = True
    kz.positionswert = kz.offene_stueck * aktueller_kurs
    kz.gesamtveraenderung_eur = kz.positionswert - kz.einstandswert
    if kz.einstandswert != ZERO:
        kz.gesamtveraenderung_pct = kz.gesamtveraenderung_eur / kz.einstandswert

    if vortagesschluss not in (None, ZERO):
        kz.tagesveraenderung_eur = kz.offene_stueck * (aktueller_kurs - vortagesschluss)
        kz.tagesveraenderung_pct = aktueller_kurs / vortagesschluss - Decimal("1")

    return kz


@dataclass
class DepotKennzahlen:
    """Dashboard KPIs of a depot (spec §5.4)."""

    depotbestand: Decimal = ZERO
    barbestand: Decimal = ZERO
    gesamtwert: Decimal = ZERO
    realisierter_gewinn: Decimal = ZERO
    unrealisierter_gewinn: Decimal = ZERO      # "Performance"
    unrealisierter_gewinn_pct: Decimal | None = None
    gesamtgewinn: Decimal = ZERO               # realized + unrealized (pure price gain)
    dividenden: Decimal = ZERO
    steuern: Decimal = ZERO                    # paid − settled (net)
    gesamtergebnis: Decimal = ZERO             # gesamtgewinn + dividenden − steuern
    aktuell_eur: Decimal = ZERO                # Σ daily changes
    aktuell_pct: Decimal | None = None


def depot_kennzahlen(
    positionen: list[PositionsKennzahlen],
    barbestand: Decimal,
    realisierter_gewinn: Decimal,
    dividenden: Decimal,
    gezahlte_steuern: Decimal,
    steuerverrechnungen: Decimal,
) -> DepotKennzahlen:
    """Aggregate depot KPIs from position KPIs and booking sums (spec §5.4).

    Also fills each position's `gewichtung` (weight relative to
    depotbestand) in place.
    """
    kz = DepotKennzahlen()
    kz.barbestand = barbestand
    kz.depotbestand = sum((p.positionswert for p in positionen), ZERO)
    kz.gesamtwert = kz.depotbestand + kz.barbestand

    kz.realisierter_gewinn = realisierter_gewinn
    kz.unrealisierter_gewinn = sum((p.gesamtveraenderung_eur for p in positionen), ZERO)
    einstand_summe = sum((p.einstandswert for p in positionen), ZERO)
    if einstand_summe != ZERO:
        kz.unrealisierter_gewinn_pct = kz.unrealisierter_gewinn / einstand_summe

    # Consistency identity (REQ-CALC-GESAMT): Gesamtgewinn = realized + unrealized.
    kz.gesamtgewinn = kz.realisierter_gewinn + kz.unrealisierter_gewinn

    kz.dividenden = dividenden
    # Net taxes: positive = paid on balance, negative = refunded on balance.
    kz.steuern = gezahlte_steuern - steuerverrechnungen
    # Net total return (REQ-CALC-ERGEBNIS).
    kz.gesamtergebnis = kz.gesamtgewinn + kz.dividenden - kz.steuern

    kz.aktuell_eur = sum((p.tagesveraenderung_eur for p in positionen), ZERO)
    basis = kz.depotbestand - kz.aktuell_eur
    if basis != ZERO:
        kz.aktuell_pct = kz.aktuell_eur / basis

    for p in positionen:
        if kz.depotbestand != ZERO:
            p.gewichtung = p.positionswert / kz.depotbestand

    return kz
