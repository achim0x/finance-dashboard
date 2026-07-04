"""REQ-SNAPSHOT and REQ-UEBERSICHT (spec §4.10/§7)."""
from decimal import Decimal

import pytest

from tests.fixtures import fakes
from tests.fixtures.daten import (
    mach_depot,
    mach_einzahlung,
    mach_instrument,
    mach_kauf,
    mach_verkauf,
    tag,
)


@pytest.mark.requirement("REQ-SNAPSHOT")
def test_snapshot_friert_ein_und_vergleich_liefert_differenzen(svc):
    from services.snapshots import snapshot_erstellen, vergleich

    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "10000", tag(0))
    mach_kauf(depot.id, instrument.id, "10", "100", tag(1))
    fakes.fake_aktien.set_quote(instrument.isin, "100")

    a = snapshot_erstellen(depot, "Vorher")
    assert a.gesamtwert == Decimal("10000")  # 1000 position + 9000 cash

    # Data changes afterwards — the snapshot must stay frozen.
    fakes.fake_aktien.set_quote(instrument.isin, "150")
    mach_verkauf(depot.id, instrument.id, "5", "150", tag(2))
    b = snapshot_erstellen(depot, "Nachher")

    from services.snapshots import get_snapshot

    assert get_snapshot(a.id).gesamtwert == Decimal("10000")
    assert get_snapshot(a.id).realisierter_gewinn == Decimal("0")

    daten = vergleich(a.id, b.id)
    kpis = {k["feld"]: k for k in daten["kpis"]}
    # b: position 5*150=750, cash 9000+750=9750 -> total 10500.
    assert kpis["gesamtwert"]["b"] == Decimal("10500")
    assert kpis["gesamtwert"]["differenz"] == Decimal("500")
    assert kpis["realisierter_gewinn"]["differenz"] == Decimal("250")
    position = daten["positionen"][0]
    assert position["stueck_a"] == Decimal("10")
    assert position["stueck_b"] == Decimal("5")


@pytest.mark.requirement("REQ-SNAPSHOT")
def test_snapshots_verschiedener_depots_nicht_vergleichbar(svc):
    from services.snapshots import snapshot_erstellen, vergleich
    from utils.fehler import ValidierungsFehler

    depot_a = mach_depot("Depot A")
    depot_b = mach_depot("Depot B")
    a = snapshot_erstellen(depot_a, "A1")
    b = snapshot_erstellen(depot_b, "B1")
    with pytest.raises(ValidierungsFehler):
        vergleich(a.id, b.id)


@pytest.mark.requirement("REQ-UEBERSICHT")
def test_uebersicht_summiert_kennzahlen_je_depot_und_gesamt(svc):
    from services.depots import alle_depots_kennzahlen

    depot_a = mach_depot("Depot A")
    depot_b = mach_depot("Depot B")
    instrument = mach_instrument()
    mach_einzahlung(depot_a.id, "1000", tag(0))
    mach_einzahlung(depot_b.id, "2000", tag(0))
    mach_kauf(depot_b.id, instrument.id, "10", "100", tag(1))
    fakes.fake_aktien.set_quote(instrument.isin, "120")

    zeilen, summen = alle_depots_kennzahlen()
    je_name = {z.depot.name: z.kennzahlen for z in zeilen}
    assert je_name["Depot A"].gesamtwert == Decimal("1000")
    assert je_name["Depot B"].gesamtwert == Decimal("2200")  # 1200 + 1000 cash
    assert summen.gesamtwert == Decimal("3200")
    assert summen.barbestand == Decimal("2000")
    assert summen.gesamtgewinn == Decimal("200")
