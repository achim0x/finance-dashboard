"""Calculation requirements (spec §5, §10): FIFO, position KPIs and the two
KPI identities."""
from decimal import Decimal

import pytest

from tests.fixtures import fakes
from tests.fixtures.daten import (
    mach_depot,
    mach_dividende,
    mach_einzahlung,
    mach_instrument,
    mach_kauf,
    mach_steuerverrechnung,
    mach_verkauf,
    tag,
)


@pytest.mark.requirement("REQ-CALC-FIFO")
def test_realisierter_gewinn_fifo_mit_teilverkauf_und_spesen(svc):
    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "10000")
    mach_kauf(depot.id, instrument.id, "10", "100", tag(1), spesen="10")
    mach_kauf(depot.id, instrument.id, "10", "120", tag(2), spesen="20")
    verkauf = mach_verkauf(depot.id, instrument.id, "15", "150", tag(3), spesen="5")

    # FIFO: full tranche 1 (1000+10) + half of tranche 2 (600+10); gain =
    # 2250 - 1620 - 5 = 625. Stored on the sale for traceability (spec §4.4).
    assert verkauf.realisierter_gewinn == Decimal("625")

    # Partial sell leaves 5 pieces of tranche 2 open.
    from services.positionen import position_fuer_instrument

    position = position_fuer_instrument(depot, instrument, mit_kursen=False)
    assert position.kennzahlen.offene_stueck == Decimal("5")


@pytest.mark.requirement("REQ-CALC-POS")
def test_positionskennzahlen_mit_kurs(svc):
    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "10000")
    mach_kauf(depot.id, instrument.id, "10", "100", tag(1), spesen="10")
    fakes.fake_aktien.set_quote(instrument.isin, "110", vortagesschluss="105")

    from services.depots import depot_kennzahlen

    kennzahlen, positionen = depot_kennzahlen(depot)
    kz = positionen[0].kennzahlen
    assert kz.positionswert == Decimal("1100")
    assert kz.tagesveraenderung_eur == Decimal("50")
    assert kz.tagesveraenderung_pct == Decimal("110") / Decimal("105") - 1
    assert kz.gesamtveraenderung_eur == Decimal("90")
    assert kz.gesamtveraenderung_pct == Decimal("90") / Decimal("1010")
    assert kz.gewichtung == Decimal("1")  # only position


@pytest.mark.requirement("REQ-CALC-GESAMT")
def test_gesamtgewinn_ist_realisiert_plus_unrealisiert(svc):
    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "10000")
    mach_kauf(depot.id, instrument.id, "10", "100", tag(1))
    mach_verkauf(depot.id, instrument.id, "4", "120", tag(2))
    fakes.fake_aktien.set_quote(instrument.isin, "95")

    from services.depots import depot_kennzahlen

    kennzahlen, _ = depot_kennzahlen(depot)
    assert kennzahlen.realisierter_gewinn == Decimal("80")   # 4 * (120-100)
    assert kennzahlen.unrealisierter_gewinn == Decimal("-30")  # 6 * (95-100)
    assert kennzahlen.gesamtgewinn == kennzahlen.realisierter_gewinn + kennzahlen.unrealisierter_gewinn
    assert kennzahlen.gesamtgewinn == Decimal("50")


@pytest.mark.requirement("REQ-CALC-ERGEBNIS")
def test_gesamtergebnis_ist_gesamtgewinn_plus_dividenden_minus_steuern(svc):
    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "10000")
    mach_kauf(depot.id, instrument.id, "10", "100", tag(1))
    mach_verkauf(depot.id, instrument.id, "5", "120", tag(2), steuer="25")
    mach_dividende(depot.id, instrument.id, "40", tag(3))
    mach_steuerverrechnung(depot.id, "5", tag(4))
    fakes.fake_aktien.set_quote(instrument.isin, "100")

    from services.depots import depot_kennzahlen

    kennzahlen, _ = depot_kennzahlen(depot)
    assert kennzahlen.dividenden == Decimal("40")
    assert kennzahlen.steuern == Decimal("20")  # 25 paid - 5 settled
    assert kennzahlen.gesamtergebnis == kennzahlen.gesamtgewinn + Decimal("40") - Decimal("20")
    # Dividends/taxes do NOT change the pure price gain (spec §5.4).
    assert kennzahlen.gesamtgewinn == Decimal("100")
