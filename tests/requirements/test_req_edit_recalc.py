"""REQ-EDIT-RECALC (spec §4.11/§5.6): editing/deleting any booking — incl.
its timestamp — recomputes cash balance, FIFO and realized gains."""
from decimal import Decimal

import pytest

from utils.fehler import ValidierungsFehler
from tests.fixtures.daten import (
    mach_depot,
    mach_einzahlung,
    mach_instrument,
    mach_kauf,
    mach_verkauf,
    tag,
)


@pytest.mark.requirement("REQ-EDIT-RECALC")
def test_zeitpunkt_aenderung_ordnet_fifo_neu_und_berechnet_gewinn(svc):
    from services.kaeufe import kauf_bearbeiten
    from services.verkaeufe import verkaeufe_fuer_depot

    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "10000", tag(0))
    mach_kauf(depot.id, instrument.id, "10", "100", tag(1))
    kauf_teuer = mach_kauf(depot.id, instrument.id, "10", "200", tag(2))
    mach_verkauf(depot.id, instrument.id, "10", "150", tag(3))

    assert verkaeufe_fuer_depot(depot.id)[0].realisierter_gewinn == Decimal("500")

    # Move the expensive tranche to the front -> FIFO consumes it first.
    kauf_bearbeiten(
        kauf_teuer.id,
        {
            "instrument_id": instrument.id,
            "stueck": Decimal("10"),
            "kaufkurs": Decimal("200"),
            "kauf_zeitpunkt": tag(1).replace(hour=8),
            "spesen": Decimal("0"),
            "boerse": None,
        },
    )
    assert verkaeufe_fuer_depot(depot.id)[0].realisierter_gewinn == Decimal("-500")


@pytest.mark.requirement("REQ-EDIT-RECALC")
def test_verkauf_bearbeiten_und_loeschen_berechnet_neu(svc):
    from services.verkaeufe import verkauf_bearbeiten, verkauf_loeschen, verkaeufe_fuer_depot
    from services.zahlungen import barbestand

    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "10000", tag(0))
    mach_kauf(depot.id, instrument.id, "10", "100", tag(1))
    verkauf = mach_verkauf(depot.id, instrument.id, "5", "120", tag(2))
    assert verkauf.realisierter_gewinn == Decimal("100")

    verkauf_bearbeiten(
        verkauf.id,
        {
            "instrument_id": instrument.id,
            "stueck": Decimal("5"),
            "verkaufskurs": Decimal("90"),
            "verkauf_zeitpunkt": tag(2),
            "spesen": Decimal("0"),
            "steuer": Decimal("0"),
            "boerse": None,
        },
    )
    assert verkaeufe_fuer_depot(depot.id)[0].realisierter_gewinn == Decimal("-50")
    assert barbestand(depot.id) == Decimal("10000") - 1000 + 450

    verkauf_loeschen(verkauf.id)
    assert verkaeufe_fuer_depot(depot.id) == []
    assert barbestand(depot.id) == Decimal("9000")


@pytest.mark.requirement("REQ-EDIT-RECALC")
def test_kauf_loeschen_wird_abgelehnt_wenn_verkaeufe_ungedeckt(svc):
    from services.kaeufe import kauf_loeschen
    from services.verkaeufe import verkaeufe_fuer_depot

    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "10000", tag(0))
    kauf = mach_kauf(depot.id, instrument.id, "10", "100", tag(1))
    mach_verkauf(depot.id, instrument.id, "8", "120", tag(2))

    with pytest.raises(ValidierungsFehler) as fehler:
        kauf_loeschen(kauf.id)
    assert "fehler.bestand_verkaeufe" in fehler.value.meldungen
    # Rolled back: sale and its gain are unchanged.
    assert verkaeufe_fuer_depot(depot.id)[0].realisierter_gewinn == Decimal("160")


@pytest.mark.requirement("REQ-EDIT-RECALC")
def test_zahlung_loeschen_aktualisiert_barbestand_oder_wird_abgelehnt(svc):
    from services.zahlungen import barbestand, zahlung_loeschen

    depot = mach_depot()
    instrument = mach_instrument()
    einzahlung_a = mach_einzahlung(depot.id, "1000", tag(0))
    mach_einzahlung(depot.id, "500", tag(1))
    assert barbestand(depot.id) == Decimal("1500")

    zahlung_loeschen(einzahlung_a.id)
    assert barbestand(depot.id) == Decimal("500")

    # Deleting the remaining deposit would strand an existing buy -> rejected.
    einzahlung_b = mach_einzahlung(depot.id, "1000", tag(1))
    mach_kauf(depot.id, instrument.id, "10", "100", tag(2))
    with pytest.raises(ValidierungsFehler):
        zahlung_loeschen(einzahlung_b.id)
