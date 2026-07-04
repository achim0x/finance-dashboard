"""Cash-ledger requirements (spec §5.2, §10): derivation, coverage check,
dividend and tax KPIs."""
from decimal import Decimal

import pytest

from utils.fehler import ValidierungsFehler
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


@pytest.mark.requirement("REQ-CASH-LEDGER")
def test_barbestand_wird_aus_allen_buchungsarten_abgeleitet(svc):
    from services.zahlungen import barbestand, zahlung_erfassen

    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "10000", tag(0))
    zahlung_erfassen(
        depot.id,
        {"typ": "AUSZAHLUNG", "betrag": Decimal("500"), "zeitpunkt": tag(1), "notiz": None},
    )
    mach_kauf(depot.id, instrument.id, "10", "100", tag(2), spesen="10")   # -1010
    mach_verkauf(depot.id, instrument.id, "5", "120", tag(3), spesen="5", steuer="15")  # +580
    mach_dividende(depot.id, instrument.id, "30", tag(4))
    mach_steuerverrechnung(depot.id, "20", tag(5))

    assert barbestand(depot.id) == (
        Decimal("10000") - 500 - 1010 + (600 - 5 - 15) + 30 + 20
    )


@pytest.mark.requirement("REQ-CASH-LEDGER")
def test_deckungspruefung_verhindert_ueberziehung(svc):
    from services.zahlungen import barbestand, zahlung_erfassen

    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "1000", tag(0))

    # Buy exceeding the balance -> rejected, nothing booked.
    with pytest.raises(ValidierungsFehler) as fehler:
        mach_kauf(depot.id, instrument.id, "20", "100", tag(1))
    assert "fehler.deckung" in fehler.value.meldungen
    assert barbestand(depot.id) == Decimal("1000")

    # Withdrawal exceeding the balance -> rejected likewise.
    with pytest.raises(ValidierungsFehler):
        zahlung_erfassen(
            depot.id,
            {"typ": "AUSZAHLUNG", "betrag": Decimal("2000"), "zeitpunkt": tag(1), "notiz": None},
        )
    assert barbestand(depot.id) == Decimal("1000")


@pytest.mark.requirement("REQ-DIV-KPI")
def test_dividende_erhoeht_barbestand_und_eigene_kpi(svc):
    from services.dividenden import dividenden_summe
    from services.zahlungen import barbestand

    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "1000", tag(0))
    mach_dividende(depot.id, instrument.id, "75", tag(1))

    assert barbestand(depot.id) == Decimal("1075")
    assert dividenden_summe(depot.id) == Decimal("75")

    from services.depots import depot_kennzahlen

    kennzahlen, _ = depot_kennzahlen(depot, mit_kursen=False)
    assert kennzahlen.dividenden == Decimal("75")


@pytest.mark.requirement("REQ-TAX-KPI")
def test_steuern_kpi_gezahlt_minus_verrechnet(svc):
    from services.steuern import steuern_saldo
    from services.zahlungen import barbestand

    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "10000", tag(0))
    mach_kauf(depot.id, instrument.id, "10", "100", tag(1))
    # Sale tax reduces the cash balance...
    mach_verkauf(depot.id, instrument.id, "5", "100", tag(2), steuer="30")
    saldo_nach_verkauf = barbestand(depot.id)
    assert saldo_nach_verkauf == Decimal("10000") - 1000 + (500 - 30)
    # ...the settlement credits it back.
    mach_steuerverrechnung(depot.id, "12", tag(3))
    assert barbestand(depot.id) == saldo_nach_verkauf + 12
    # KPI: paid - settled (positive = net paid).
    assert steuern_saldo(depot.id) == Decimal("18")
