"""REQ-RANGE-BASIS and REQ-REVAL-CLOSE (spec §5.5/§5.6): time-range/basis
toggle on the valuation series; rebuild uses closing prices only."""
from datetime import timedelta
from decimal import Decimal

import pytest

from domain.enums import Bezugsbasis, Zeitraum
from tests.fixtures.daten import T0, mach_depot, mach_einzahlung, mach_instrument, mach_kauf, tag


def _serie_aufbauen(depot, instrument):
    """Deposit 1000 at T0, buy 10@50 on day 1; closes on day 1 (50) and
    day 3 (60) — day 2 must be carried forward."""
    from services.kurse import bewertungen_neu_aufbauen, schlusskurs_schreiben

    mach_einzahlung(depot.id, "1000", tag(0))
    mach_kauf(depot.id, instrument.id, "10", "50", tag(1))
    schlusskurs_schreiben(instrument.id, tag(1).date(), Decimal("50"), "MANUELL")
    schlusskurs_schreiben(instrument.id, tag(3).date(), Decimal("60"), "MANUELL")
    bewertungen_neu_aufbauen(depot.id, ab=T0.date())


@pytest.mark.requirement("REQ-RANGE-BASIS")
def test_bezugsbasis_waehlt_die_richtige_reihe(svc):
    from services.depots import verlauf

    depot = mach_depot()
    instrument = mach_instrument()
    _serie_aufbauen(depot, instrument)

    nur_wp = verlauf(depot, Zeitraum.SEIT_EROEFFNUNG, Bezugsbasis.NUR_WERTPAPIERE)
    inkl = verlauf(depot, Zeitraum.SEIT_EROEFFNUNG, Bezugsbasis.INKL_BARBESTAND)

    # Securities-only series: 0 at opening -> 600 today (10 * 60).
    assert nur_wp["werte"][0] == Decimal("0")
    assert nur_wp["werte"][-1] == Decimal("600")
    # Incl. cash: 1000 at opening -> 1100 today (600 + 500 cash).
    assert inkl["werte"][0] == Decimal("1000")
    assert inkl["werte"][-1] == Decimal("1100")
    assert inkl["performance_eur"] == Decimal("100")
    assert inkl["performance_pct"] == Decimal("100") / Decimal("1000")


@pytest.mark.requirement("REQ-RANGE-BASIS")
def test_benutzerdefinierter_zeitraum_grenzt_die_reihe_ein(svc):
    from services.depots import verlauf

    depot = mach_depot()
    instrument = mach_instrument()
    _serie_aufbauen(depot, instrument)

    von = tag(1).date().isoformat()
    bis = tag(3).date().isoformat()
    daten = verlauf(
        depot, Zeitraum.BENUTZERDEFINIERT, Bezugsbasis.INKL_BARBESTAND, von=von, bis=bis
    )
    assert daten["labels"][0] == von
    assert daten["labels"][-1] == bis
    # Day 1: 10*50 + 500 cash = 1000; day 3: 10*60 + 500 = 1100.
    assert daten["werte"][0] == Decimal("1000")
    assert daten["werte"][-1] == Decimal("1100")


@pytest.mark.requirement("REQ-REVAL-CLOSE")
def test_neuaufbau_nutzt_nur_schlusskurse_und_schreibt_fort(svc):
    """Intraday quotes must NOT influence the rebuild; missing days carry the
    last close forward (spec §5.6)."""
    from services.kurse import bewertungen_neu_aufbauen, manuellen_kurs_erfassen, schlusskurs_schreiben
    from infrastructure.persistence.sqlalchemy_repos import SqlAlchemyDepotBewertungRepository

    depot = mach_depot()
    instrument = mach_instrument()
    mach_einzahlung(depot.id, "1000", tag(0))
    mach_kauf(depot.id, instrument.id, "10", "50", tag(1))
    schlusskurs_schreiben(instrument.id, tag(1).date(), Decimal("50"), "MANUELL")
    schlusskurs_schreiben(instrument.id, tag(3).date(), Decimal("60"), "MANUELL")
    # A wildly different intraday quote that must be ignored by the rebuild.
    manuellen_kurs_erfassen(instrument.id, Decimal("999"))

    bewertungen_neu_aufbauen(depot.id, ab=T0.date())

    reihe = SqlAlchemyDepotBewertungRepository(svc).series(depot.id)
    je_datum = {b.datum: b for b in reihe}
    # Day 1 and the carried-forward day 2 use close 50; day 3 uses 60.
    assert je_datum[tag(1).date()].depotbestand == Decimal("500")
    assert je_datum[tag(2).date()].depotbestand == Decimal("500")   # forward fill
    assert je_datum[tag(3).date()].depotbestand == Decimal("600")
    # Today also carries the last close (60), NOT the intraday 999.
    assert reihe[-1].depotbestand == Decimal("600")
    # Cash series is tracked alongside (both series stored, spec §4.7).
    assert je_datum[tag(1).date()].barbestand == Decimal("500")
    assert je_datum[tag(1).date()].gesamtwert == Decimal("1000")
