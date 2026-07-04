"""FX requirements (spec §5.7/§6.10): pluggable provider, conversion into
the depot base currency, stale-rate fallback."""
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


@pytest.mark.requirement("REQ-FX-PROVIDER")
def test_fx_provider_ist_per_registry_austauschbar(svc):
    """A new FX provider = implementation + registry entry, selectable via
    the setup service — no service/UI changes (spec §6.10)."""
    from domain.kurse.price_provider import ProviderMetadaten
    from infrastructure.waehrung import registry
    from services.waehrung import einstellung_speichern, rate

    class NeuerFx:
        name = "fx_neu"

        def get_rate(self, von, nach, am=None):
            return Decimal("1.5")

        def get_rate_history(self, von, nach, ab, bis):
            return []

    registry.register(
        ProviderMetadaten(name="fx_neu", anzeigename="FX Neu", kursgruppen=()),
        lambda creds: NeuerFx(),
    )
    einstellung_speichern("fx_neu", {}, 60, True)

    wert, status = rate("USD", "EUR")
    assert wert == Decimal("1.5")
    assert status == "ok"


@pytest.mark.requirement("REQ-FX-CONVERT")
def test_fremdwaehrungsposition_wird_in_basiswaehrung_umgerechnet(svc):
    from services.positionen import position_fuer_instrument

    depot = mach_depot()  # base currency EUR
    usd_aktie = mach_instrument("US0378331005", "Apple", "AKTIE", waehrung="USD")
    mach_einzahlung(depot.id, "10000", tag(0))
    mach_kauf(depot.id, usd_aktie.id, "10", "100", tag(1))
    fakes.fake_aktien.set_quote(usd_aktie.isin, "110", vortagesschluss="105", waehrung="USD")
    fakes.fake_fx.rates[("USD", "EUR")] = Decimal("0.9")

    position = position_fuer_instrument(depot, usd_aktie)
    kz = position.kennzahlen
    assert position.unkonvertiert is False
    assert kz.positionswert == Decimal("1100") * Decimal("0.9")
    assert kz.einstandswert == Decimal("1000") * Decimal("0.9")
    assert kz.tagesveraenderung_eur == Decimal("50") * Decimal("0.9")
    # Percentages are rate-independent.
    assert kz.gesamtveraenderung_pct == Decimal("100") / Decimal("1000")


@pytest.mark.requirement("REQ-FX-CONVERT")
def test_fx_ausfall_letzter_kurs_veraltet_oder_unkonvertiert(svc):
    from infrastructure.persistence.sqlalchemy_repos import SqlAlchemyWechselkursRepository
    from services.positionen import position_fuer_instrument
    from services.waehrung import rate

    depot = mach_depot()
    usd_aktie = mach_instrument("US0378331005", "Apple", "AKTIE", waehrung="USD")
    mach_einzahlung(depot.id, "10000", tag(0))
    mach_kauf(depot.id, usd_aktie.id, "10", "100", tag(1))
    fakes.fake_aktien.set_quote(usd_aktie.isin, "110", waehrung="USD")

    # No rate at all -> value shown unconverted with a hint (spec §5.7).
    position = position_fuer_instrument(depot, usd_aktie)
    assert position.unkonvertiert is True
    assert position.kennzahlen.positionswert == Decimal("1100")

    # Historic daily rate: only an older cached rate exists -> carried
    # forward and flagged "veraltet".
    repo = SqlAlchemyWechselkursRepository(svc)
    repo.upsert("USD", "EUR", date.today() - timedelta(days=7), Decimal("0.8"), "test")
    svc.commit()
    wert, status = rate("USD", "EUR", am=date.today() - timedelta(days=1))
    assert wert == Decimal("0.8")
    assert status == "veraltet"
