"""FIFO / average-cost matching of sales against buy tranches (spec §5.3).

Pure functions operating on `Kauf`/`Verkauf` entities (or anything with the
same attributes). The buy timestamp determines FIFO order; editing a
timestamp therefore changes the matching, which is why callers recompute
after every booking change (spec §4.11/§5.6).

Cost basis of a consumed slice includes the proportional share of the buy
fees (spec §5.1: einstandswert includes proportional fees).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from domain.enums import Verrechnungsmethode

ZERO = Decimal("0")


class UnzureichenderBestandError(ValueError):
    """Raised when a sale exceeds the open quantity at its point in time."""

    def __init__(self, verkauf, fehlmenge: Decimal):
        self.verkauf = verkauf
        self.fehlmenge = fehlmenge
        super().__init__(
            f"Sale of {verkauf.stueck} exceeds open quantity by {fehlmenge}"
        )


@dataclass
class OffeneTranche:
    """A buy tranche with its remaining open quantity."""

    kauf: object  # Kauf entity (duck-typed)
    offene_stueck: Decimal

    @property
    def anteilige_spesen(self) -> Decimal:
        """Fees attributable to the still-open part of the tranche."""
        if self.kauf.stueck == ZERO:
            return ZERO
        return self.kauf.spesen * self.offene_stueck / self.kauf.stueck

    @property
    def einstandswert(self) -> Decimal:
        """Open quantity * buy price + proportional fees (spec §5.1)."""
        return self.offene_stueck * self.kauf.kaufkurs + self.anteilige_spesen


@dataclass
class Verrechnung:
    """Matching result for one sale: which cost basis it consumed."""

    verkauf: object  # Verkauf entity (duck-typed)
    einstandskosten: Decimal = ZERO
    # (kauf, consumed quantity) pairs — for traceability/tests.
    konsum: list[tuple[object, Decimal]] = field(default_factory=list)

    @property
    def realisierter_gewinn(self) -> Decimal:
        """erloes − matched cost basis − sale fees (spec §5.3).

        The sale tax is deliberately NOT part of the realized gain; it only
        affects the cash balance and the tax KPI (spec §4.4/§5.4).
        """
        v = self.verkauf
        erloes = v.stueck * v.verkaufskurs
        return erloes - self.einstandskosten - v.spesen


def _sortiert(kaeufe, verkaeufe):
    kaeufe = sorted(kaeufe, key=lambda k: (k.kauf_zeitpunkt, k.id or 0))
    verkaeufe = sorted(verkaeufe, key=lambda v: (v.verkauf_zeitpunkt, v.id or 0))
    return kaeufe, verkaeufe


def verrechne(
    kaeufe,
    verkaeufe,
    methode: Verrechnungsmethode = Verrechnungsmethode.FIFO,
) -> tuple[list[OffeneTranche], list[Verrechnung]]:
    """Match all sales of one (depot, instrument) against its buy tranches.

    Replays buys and sales in chronological order. Sales only consume
    tranches bought before the sale timestamp. Returns the remaining open
    tranches and one `Verrechnung` per sale.

    Raises `UnzureichenderBestandError` if a sale exceeds the quantity open
    at its point in time.
    """
    kaeufe, verkaeufe = _sortiert(kaeufe, verkaeufe)
    offen: list[OffeneTranche] = []
    ergebnisse: list[Verrechnung] = []
    kauf_iter = iter(kaeufe)
    naechster_kauf = next(kauf_iter, None)

    def _nachziehen(bis_zeitpunkt):
        """Move buys that happened up to `bis_zeitpunkt` into the open list."""
        nonlocal naechster_kauf
        while naechster_kauf is not None and naechster_kauf.kauf_zeitpunkt <= bis_zeitpunkt:
            offen.append(OffeneTranche(naechster_kauf, naechster_kauf.stueck))
            naechster_kauf = next(kauf_iter, None)

    for verkauf in verkaeufe:
        _nachziehen(verkauf.verkauf_zeitpunkt)
        rest = verkauf.stueck
        ergebnis = Verrechnung(verkauf)

        if methode == Verrechnungsmethode.DURCHSCHNITT:
            # Average cost of everything open at the sale time.
            gesamt_stueck = sum((t.offene_stueck for t in offen), ZERO)
            if gesamt_stueck < rest:
                raise UnzureichenderBestandError(verkauf, rest - gesamt_stueck)
            gesamt_kosten = sum((t.einstandswert for t in offen), ZERO)
            durchschnitt = gesamt_kosten / gesamt_stueck if gesamt_stueck else ZERO
            ergebnis.einstandskosten = durchschnitt * rest
            # Reduce tranches proportionally (front to back for determinism).
            for tranche in offen:
                if rest <= ZERO:
                    break
                anteil = min(tranche.offene_stueck, rest)
                tranche.offene_stueck -= anteil
                ergebnis.konsum.append((tranche.kauf, anteil))
                rest -= anteil
        else:  # FIFO (default)
            for tranche in offen:
                if rest <= ZERO:
                    break
                if tranche.offene_stueck <= ZERO:
                    continue
                anteil = min(tranche.offene_stueck, rest)
                # Cost basis: buy price + proportional share of the buy fees.
                kosten = anteil * tranche.kauf.kaufkurs
                if tranche.kauf.stueck:
                    kosten += tranche.kauf.spesen * anteil / tranche.kauf.stueck
                tranche.offene_stueck -= anteil
                ergebnis.einstandskosten += kosten
                ergebnis.konsum.append((tranche.kauf, anteil))
                rest -= anteil
            if rest > ZERO:
                raise UnzureichenderBestandError(verkauf, rest)

        ergebnisse.append(ergebnis)

    # Move any buys after the last sale into the open list.
    while naechster_kauf is not None:
        offen.append(OffeneTranche(naechster_kauf, naechster_kauf.stueck))
        naechster_kauf = next(kauf_iter, None)

    offen = [t for t in offen if t.offene_stueck > ZERO]
    return offen, ergebnisse


def offene_tranchen(
    kaeufe, verkaeufe, methode: Verrechnungsmethode = Verrechnungsmethode.FIFO
) -> list[OffeneTranche]:
    """Remaining open tranches of one (depot, instrument)."""
    offen, _ = verrechne(kaeufe, verkaeufe, methode)
    return offen


def realisierte_gewinne(
    kaeufe, verkaeufe, methode: Verrechnungsmethode = Verrechnungsmethode.FIFO
) -> dict[int, Decimal]:
    """Realized gain per sale id, recomputed from scratch (spec §5.6)."""
    _, ergebnisse = verrechne(kaeufe, verkaeufe, methode)
    return {e.verkauf.id: e.realisierter_gewinn for e in ergebnisse}
