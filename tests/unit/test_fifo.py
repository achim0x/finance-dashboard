"""Unit tests for the FIFO/average-cost matching engine (spec §5.3)."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

import pytest

from domain.berechnung import (
    UnzureichenderBestandError,
    offene_tranchen,
    realisierte_gewinne,
    verrechne,
)
from domain.enums import Verrechnungsmethode

_zaehler = iter(range(1, 10_000))


@dataclass
class KaufStub:
    stueck: Decimal
    kaufkurs: Decimal
    kauf_zeitpunkt: datetime
    spesen: Decimal = Decimal("0")
    id: int = field(default_factory=lambda: next(_zaehler))


@dataclass
class VerkaufStub:
    stueck: Decimal
    verkaufskurs: Decimal
    verkauf_zeitpunkt: datetime
    spesen: Decimal = Decimal("0")
    steuer: Decimal = Decimal("0")
    id: int = field(default_factory=lambda: next(_zaehler))


def _t(tag: int) -> datetime:
    return datetime(2025, 1, tag, 10, 0)


def test_fifo_konsumiert_aelteste_tranche_zuerst():
    kaeufe = [
        KaufStub(Decimal("10"), Decimal("100"), _t(1)),
        KaufStub(Decimal("10"), Decimal("200"), _t(2)),
    ]
    verkaeufe = [VerkaufStub(Decimal("10"), Decimal("150"), _t(3))]
    offen, ergebnisse = verrechne(kaeufe, verkaeufe)
    # The full first (cheap) tranche is consumed, the second stays open.
    assert len(offen) == 1
    assert offen[0].kauf.kaufkurs == Decimal("200")
    assert ergebnisse[0].realisierter_gewinn == Decimal("500")  # 1500 - 1000


def test_teilverkauf_ueber_tranchen_mit_spesen():
    kaeufe = [
        KaufStub(Decimal("10"), Decimal("100"), _t(1), spesen=Decimal("10")),
        KaufStub(Decimal("10"), Decimal("120"), _t(2), spesen=Decimal("20")),
    ]
    verkaeufe = [VerkaufStub(Decimal("15"), Decimal("150"), _t(3), spesen=Decimal("5"))]
    _, ergebnisse = verrechne(kaeufe, verkaeufe)
    # Cost: full tranche 1 (1000 + 10 fees) + 5/10 of tranche 2 (600 + 10 fees).
    erwartete_kosten = Decimal("1010") + Decimal("610")
    assert ergebnisse[0].einstandskosten == erwartete_kosten
    # Gain: 15*150 - costs - sale fees.
    assert ergebnisse[0].realisierter_gewinn == Decimal("2250") - erwartete_kosten - Decimal("5")


def test_verkauf_vor_kauf_zaehlt_nicht():
    kaeufe = [KaufStub(Decimal("10"), Decimal("100"), _t(5))]
    verkaeufe = [VerkaufStub(Decimal("5"), Decimal("100"), _t(2))]
    with pytest.raises(UnzureichenderBestandError):
        verrechne(kaeufe, verkaeufe)


def test_ueberverkauf_wirft_fehler():
    kaeufe = [KaufStub(Decimal("5"), Decimal("100"), _t(1))]
    verkaeufe = [VerkaufStub(Decimal("6"), Decimal("100"), _t(2))]
    with pytest.raises(UnzureichenderBestandError):
        verrechne(kaeufe, verkaeufe)


def test_kauf_zeitpunkt_bestimmt_fifo_reihenfolge():
    """Editing the buy timestamp reorders FIFO (spec §4.3)."""
    kauf_a = KaufStub(Decimal("10"), Decimal("100"), _t(1))
    kauf_b = KaufStub(Decimal("10"), Decimal("200"), _t(2))
    verkauf = VerkaufStub(Decimal("10"), Decimal("150"), _t(3))
    gewinn_vorher = realisierte_gewinne([kauf_a, kauf_b], [verkauf])[verkauf.id]
    assert gewinn_vorher == Decimal("500")

    # Move the expensive tranche before the cheap one -> it is consumed first.
    kauf_b.kauf_zeitpunkt = _t(1).replace(hour=8)
    gewinn_nachher = realisierte_gewinne([kauf_a, kauf_b], [verkauf])[verkauf.id]
    assert gewinn_nachher == Decimal("-500")


def test_offene_tranchen_nach_mehreren_verkaeufen():
    kaeufe = [
        KaufStub(Decimal("10"), Decimal("100"), _t(1)),
        KaufStub(Decimal("10"), Decimal("110"), _t(2)),
    ]
    verkaeufe = [
        VerkaufStub(Decimal("4"), Decimal("120"), _t(3)),
        VerkaufStub(Decimal("8"), Decimal("130"), _t(4)),
    ]
    offen = offene_tranchen(kaeufe, verkaeufe)
    assert sum(t.offene_stueck for t in offen) == Decimal("8")
    assert offen[0].kauf.kaufkurs == Decimal("110")


def test_durchschnittsmethode():
    kaeufe = [
        KaufStub(Decimal("10"), Decimal("100"), _t(1)),
        KaufStub(Decimal("10"), Decimal("200"), _t(2)),
    ]
    verkaeufe = [VerkaufStub(Decimal("10"), Decimal("150"), _t(3))]
    _, ergebnisse = verrechne(kaeufe, verkaeufe, Verrechnungsmethode.DURCHSCHNITT)
    # Average cost 150/share -> zero gain.
    assert ergebnisse[0].realisierter_gewinn == Decimal("0")
