"""Mini-chart requirements (spec §6.9): forward filling and backfill."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.fixtures import fakes
from tests.fixtures.daten import (
    mach_depot,
    mach_einzahlung,
    mach_instrument,
    mach_kauf,
    tag,
)


@pytest.mark.requirement("REQ-CHART-FORWARD")
def test_schlusskurse_wachsen_ab_kaufdatum_und_sind_eindeutig(svc):
    from domain.entities import Schlusskurs
    from services.kurse import mini_chart, schlusskurs_schreiben

    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "10000", tag(0))
    mach_kauf(depot.id, instrument.id, "10", "100", tag(1))

    # The daily batch writes one close per day, starting at the buy date.
    schlusskurs_schreiben(instrument.id, tag(1).date(), Decimal("100"), "MANUELL")
    schlusskurs_schreiben(instrument.id, tag(2).date(), Decimal("101"), "MANUELL")
    # Idempotent per (instrument, date): rewriting the same day updates it.
    schlusskurs_schreiben(instrument.id, tag(2).date(), Decimal("102"), "MANUELL")
    svc.commit()

    assert svc.query(Schlusskurs).filter_by(instrument_id=instrument.id).count() == 2
    reihe = mini_chart(instrument.id, tag(1).date())
    assert reihe == [
        (tag(1).date(), Decimal("100")),
        (tag(2).date(), Decimal("102")),
    ]


@pytest.mark.requirement("REQ-CHART-BACKFILL")
def test_backfill_bei_kauf_in_der_vergangenheit(svc):
    """Buy in the past -> the app recommends asking (backfill flag). 'Ja'
    fills historical closes; missing history falls back cleanly."""
    from services.kaeufe import kauf_erfassen
    from services.kurse import mini_chart, schlusskurse_backfill

    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "10000", tag(0))

    kauf, backfill_empfohlen = kauf_erfassen(
        depot.id,
        {
            "instrument_id": instrument.id,
            "stueck": Decimal("10"),
            "kaufkurs": Decimal("100"),
            "kauf_zeitpunkt": tag(1),  # in the past
            "spesen": Decimal("0"),
            "boerse": None,
        },
    )
    assert backfill_empfohlen is True

    # Provider has history -> "Ja" stores the daily closes.
    fakes.fake_aktien.historie[instrument.isin] = [
        (tag(1).date(), Decimal("100")),
        (tag(2).date(), Decimal("103")),
    ]
    anzahl = schlusskurse_backfill(instrument.id, tag(1).date(), date.today())
    assert anzahl == 2
    assert len(mini_chart(instrument.id, tag(1).date())) == 2


@pytest.mark.requirement("REQ-CHART-BACKFILL")
def test_backfill_ohne_historie_faellt_sauber_zurueck(svc):
    from services.kurse import mini_chart, schlusskurse_backfill

    depot = mach_depot()
    # Leveraged product: pytr-style provider without history (spec §6.9).
    knockout = mach_instrument("DE000KB1234B", "KO DAX", "KNOCKOUT")
    mach_einzahlung(depot.id, "10000", tag(0))
    mach_kauf(depot.id, knockout.id, "100", "5", tag(1))

    anzahl = schlusskurse_backfill(knockout.id, tag(1).date(), date.today())
    assert anzahl == 0  # reported, no hard error
    assert mini_chart(knockout.id, tag(1).date()) == []


@pytest.mark.requirement("REQ-CHART-FORWARD")
def test_kauf_heute_empfiehlt_keinen_backfill(svc):
    from datetime import datetime

    from services.kaeufe import kauf_erfassen

    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "10000", datetime.now() - timedelta(hours=2))

    _, backfill_empfohlen = kauf_erfassen(
        depot.id,
        {
            "instrument_id": instrument.id,
            "stueck": Decimal("1"),
            "kaufkurs": Decimal("10"),
            "kauf_zeitpunkt": datetime.now() - timedelta(hours=1),
            "spesen": Decimal("0"),
            "boerse": None,
        },
    )
    assert backfill_empfohlen is False
