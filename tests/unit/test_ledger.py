"""Unit tests for the cash ledger (spec §5.2)."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from domain.berechnung.ledger import barbestand, min_laufender_saldo


@dataclass
class Z:
    typ: str
    betrag: Decimal
    zeitpunkt: datetime


@dataclass
class K:
    stueck: Decimal
    kaufkurs: Decimal
    spesen: Decimal
    kauf_zeitpunkt: datetime


@dataclass
class V:
    stueck: Decimal
    verkaufskurs: Decimal
    spesen: Decimal
    steuer: Decimal
    verkauf_zeitpunkt: datetime


@dataclass
class D:
    betrag: Decimal
    zeitpunkt: datetime


def _t(tag: int) -> datetime:
    return datetime(2025, 1, tag, 12, 0)


def test_barbestand_formel():
    saldo = barbestand(
        zahlungen=[
            Z("EINZAHLUNG", Decimal("1000"), _t(1)),
            Z("AUSZAHLUNG", Decimal("100"), _t(2)),
        ],
        kaeufe=[K(Decimal("5"), Decimal("50"), Decimal("10"), _t(3))],       # -260
        verkaeufe=[V(Decimal("2"), Decimal("60"), Decimal("5"), Decimal("15"), _t(4))],  # +100
        dividenden=[D(Decimal("30"), _t(5))],
        steuerverrechnungen=[D(Decimal("20"), _t(6))],
    )
    assert saldo == Decimal("1000") - 100 - 260 + 100 + 30 + 20


def test_barbestand_bis_zeitpunkt():
    zahlungen = [
        Z("EINZAHLUNG", Decimal("1000"), _t(1)),
        Z("AUSZAHLUNG", Decimal("400"), _t(5)),
    ]
    assert barbestand(zahlungen=zahlungen, bis=_t(2)) == Decimal("1000")
    assert barbestand(zahlungen=zahlungen) == Decimal("600")


def test_min_laufender_saldo_erkennt_zwischenzeitliche_unterdeckung():
    # Deposit arrives AFTER the buy -> the running balance dips negative.
    zahlungen = [Z("EINZAHLUNG", Decimal("1000"), _t(5))]
    kaeufe = [K(Decimal("1"), Decimal("500"), Decimal("0"), _t(2))]
    assert min_laufender_saldo(zahlungen=zahlungen, kaeufe=kaeufe) == Decimal("-500")
    assert barbestand(zahlungen=zahlungen, kaeufe=kaeufe) == Decimal("500")
