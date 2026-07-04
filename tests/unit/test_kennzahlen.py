"""Unit tests for position/depot KPIs (spec §5.1/§5.4)."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from domain.berechnung import depot_kennzahlen, positions_kennzahlen
from domain.berechnung.fifo import OffeneTranche

_zaehler = iter(range(1, 10_000))


@dataclass
class KaufStub:
    stueck: Decimal
    kaufkurs: Decimal
    kauf_zeitpunkt: datetime = datetime(2025, 1, 1)
    spesen: Decimal = Decimal("0")
    id: int = field(default_factory=lambda: next(_zaehler))


def _tranche(stueck: str, kurs: str, spesen: str = "0") -> OffeneTranche:
    kauf = KaufStub(Decimal(stueck), Decimal(kurs), spesen=Decimal(spesen))
    return OffeneTranche(kauf, Decimal(stueck))


def test_positions_kennzahlen_formeln():
    tranchen = [_tranche("10", "100", "10")]
    kz = positions_kennzahlen(tranchen, Decimal("110"), Decimal("105"))
    assert kz.offene_stueck == Decimal("10")
    assert kz.einstandswert == Decimal("1010")
    assert kz.positionswert == Decimal("1100")
    assert kz.tagesveraenderung_eur == Decimal("50")            # 10 * (110-105)
    assert kz.tagesveraenderung_pct == Decimal("110") / Decimal("105") - 1
    assert kz.gesamtveraenderung_eur == Decimal("90")           # 1100 - 1010
    assert kz.gesamtveraenderung_pct == Decimal("90") / Decimal("1010")


def test_positions_kennzahlen_ohne_kurs():
    kz = positions_kennzahlen([_tranche("10", "100")], None, None)
    assert kz.kurs_vorhanden is False
    assert kz.positionswert == Decimal("0")
    assert kz.einstandswert == Decimal("1000")


def test_depot_kennzahlen_identitaeten_und_gewichtung():
    p1 = positions_kennzahlen([_tranche("10", "100")], Decimal("120"), Decimal("110"))
    p2 = positions_kennzahlen([_tranche("5", "200")], Decimal("160"), None)
    kz = depot_kennzahlen(
        positionen=[p1, p2],
        barbestand=Decimal("500"),
        realisierter_gewinn=Decimal("100"),
        dividenden=Decimal("40"),
        gezahlte_steuern=Decimal("30"),
        steuerverrechnungen=Decimal("10"),
    )
    assert kz.depotbestand == Decimal("2000")   # 1200 + 800
    assert kz.gesamtwert == Decimal("2500")
    # Identity: Gesamtgewinn = realized + unrealized (REQ-CALC-GESAMT core).
    assert kz.gesamtgewinn == kz.realisierter_gewinn + kz.unrealisierter_gewinn
    # Identity: Gesamtergebnis = Gesamtgewinn + Dividenden - Steuern.
    assert kz.steuern == Decimal("20")
    assert kz.gesamtergebnis == kz.gesamtgewinn + Decimal("40") - Decimal("20")
    # Weights relative to depotbestand.
    assert p1.gewichtung == Decimal("1200") / Decimal("2000")
    assert p2.gewichtung == Decimal("800") / Decimal("2000")
    # Daily change percentage basis: value minus today's change.
    assert kz.aktuell_eur == Decimal("100")
    assert kz.aktuell_pct == Decimal("100") / (Decimal("2000") - Decimal("100"))
