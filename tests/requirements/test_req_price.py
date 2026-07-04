"""Price-provider requirements (spec §6, §10): routing, fallback,
extensibility, setup persistence, availability test, manual refresh."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from domain.enums import Kursgruppe
from tests.fixtures import fakes
from tests.fixtures.daten import (
    mach_depot,
    mach_einzahlung,
    mach_instrument,
    mach_kauf,
    tag,
)


def _bestand_anlegen(depot, *instrumente):
    mach_einzahlung(depot.id, "100000", tag(0))
    for instrument in instrumente:
        mach_kauf(depot.id, instrument.id, "10", "100", tag(1))


@pytest.mark.requirement("REQ-PRICE-ROUTING")
def test_kategorie_steuert_provider_routing(svc):
    """Stocks/ETF go to the AKTIEN_ETF provider, leveraged products to the
    HEBELPRODUKT provider (spec §6.2)."""
    from services.kurse import aktueller_kurs

    aktie = mach_instrument("DE0007164600", "SAP", "AKTIE")
    knockout = mach_instrument("DE000KB1234B", "KO DAX", "KNOCKOUT")
    fakes.fake_aktien.set_quote(aktie.isin, "100")
    fakes.fake_hebel.set_quote(knockout.isin, "5")

    kurs_aktie = aktueller_kurs(aktie)
    kurs_ko = aktueller_kurs(knockout)

    assert kurs_aktie.kurs == Decimal("100")
    assert kurs_ko.kurs == Decimal("5")
    assert fakes.fake_aktien.aufrufe == [aktie.isin]
    assert fakes.fake_hebel.aufrufe == [knockout.isin]


@pytest.mark.requirement("REQ-PRICE-FALLBACK")
def test_provider_ausfall_liefert_letzten_kurs_als_veraltet(svc):
    from services.kurse import aktueller_kurs, kurs_ist_veraltet

    instrument = mach_instrument()
    fakes.fake_aktien.set_quote(instrument.isin, "100")
    erster = aktueller_kurs(instrument)
    assert erster.kurs == Decimal("100")

    # Provider goes down; age the stored quote past the staleness limit.
    fakes.fake_aktien.reset()
    erster.zeitstempel = datetime.now() - timedelta(hours=2)
    svc.commit()

    zweiter = aktueller_kurs(instrument)  # no crash, no exception
    assert zweiter is not None
    assert zweiter.kurs == Decimal("100")
    assert kurs_ist_veraltet(zweiter, instrument) is True


@pytest.mark.requirement("REQ-PRICE-EXT")
def test_neuer_provider_nur_ueber_registry_registrierbar(svc):
    """A brand-new provider becomes usable via registry entry + setup save —
    zero changes in services or UI (spec §6.2)."""
    from domain.kurse.price_provider import ProviderMetadaten, Quote
    from infrastructure.kurse import registry
    from services.kurse import aktueller_kurs, einstellung_speichern

    class NeuerProvider:
        name = "brandneu"

        def get_quote(self, instrument):
            return Quote(Decimal("42"), "EUR", "NEU", datetime.now(), None)

        def get_history(self, instrument, von, bis):
            return []

    registry.register(
        ProviderMetadaten(
            name="brandneu", anzeigename="Brandneu", kursgruppen=(Kursgruppe.AKTIEN_ETF,)
        ),
        lambda creds: NeuerProvider(),
    )
    einstellung_speichern(Kursgruppe.AKTIEN_ETF, "brandneu", {}, 60, True)

    instrument = mach_instrument()
    assert aktueller_kurs(instrument).kurs == Decimal("42")


@pytest.mark.requirement("REQ-KURS-SETUP")
def test_setup_persistiert_und_verschluesselt_credentials(svc):
    from infrastructure.crypto import decrypt_credentials
    from infrastructure.persistence.sqlalchemy_repos import SqlAlchemyKursEinstellungRepository
    from services.kurse import einstellung_lesen, einstellung_speichern

    einstellung_speichern(
        Kursgruppe.AKTIEN_ETF, "fake_aktien", {"api_key": "super-geheim-123"}, 120, True
    )
    row = SqlAlchemyKursEinstellungRepository(svc).get_for_gruppe("AKTIEN_ETF")
    assert row.provider_name == "fake_aktien"
    assert row.abfrage_intervall_sekunden == 120
    # Encrypted at rest: the cleartext never appears in the DB column.
    assert "super-geheim-123" not in (row.credentials_verschluesselt or "")
    entschluesselt = decrypt_credentials(
        row.credentials_verschluesselt, "test-verschluesselungs-schluessel"
    )
    assert entschluesselt["api_key"] == "super-geheim-123"

    # Secret fields are never returned in cleartext — only masked.
    ansicht = einstellung_lesen(Kursgruppe.AKTIEN_ETF)
    feld = next(f for f in ansicht["felder"] if f["schluessel"] == "api_key")
    assert feld["wert"] == "••••"

    # Saving the masked placeholder keeps the stored secret (spec §6.6).
    einstellung_speichern(
        Kursgruppe.AKTIEN_ETF, "fake_aktien", {"api_key": "••••"}, 300, True
    )
    row = SqlAlchemyKursEinstellungRepository(svc).get_for_gruppe("AKTIEN_ETF")
    entschluesselt = decrypt_credentials(
        row.credentials_verschluesselt, "test-verschluesselungs-schluessel"
    )
    assert entschluesselt["api_key"] == "super-geheim-123"


@pytest.mark.requirement("REQ-KURS-TEST")
def test_verfuegbarkeitstest_meldet_status_und_schreibt_nichts(svc):
    from domain.entities import DepotBewertung, Kurs
    from services.kurse import depot_testen

    depot = mach_depot()
    verfuegbar = mach_instrument("DE0007164600", "SAP", "AKTIE")
    fehlend = mach_instrument("DE0008404005", "Allianz", "AKTIE")
    _bestand_anlegen(depot, verfuegbar, fehlend)
    fakes.fake_aktien.set_quote(verfuegbar.isin, "100")

    kurse_vorher = svc.query(Kurs).count()
    bewertungen_vorher = svc.query(DepotBewertung).count()

    ergebnisse = {e.instrument.isin: e for e in depot_testen(depot.id)}
    assert ergebnisse[verfuegbar.isin].status == "OK"
    assert ergebnisse[verfuegbar.isin].kurs == Decimal("100")
    assert ergebnisse[fehlend.isin].status == "NICHT_VERFUEGBAR"
    assert ergebnisse[fehlend.isin].meldung == "kurse.test.kein_kurs"

    # The test writes NO quotes and NO valuations (spec §6.7).
    assert svc.query(Kurs).count() == kurse_vorher
    assert svc.query(DepotBewertung).count() == bewertungen_vorher


@pytest.mark.requirement("REQ-KURS-MANUELL")
def test_manueller_refresh_aktualisiert_sofort_und_teilfehler_blockieren_nicht(svc):
    from infrastructure.persistence.sqlalchemy_repos import SqlAlchemyKursRepository
    from services.kurse import depot_aktualisieren

    depot = mach_depot()
    ok_instrument = mach_instrument("DE0007164600", "SAP", "AKTIE")
    defekt = mach_instrument("DE0008404005", "Allianz", "AKTIE")
    _bestand_anlegen(depot, ok_instrument, defekt)
    fakes.fake_aktien.set_quote(ok_instrument.isin, "111")

    ergebnisse = {e.instrument.isin: e for e in depot_aktualisieren(depot.id)}
    # The failing instrument does not stop the successful one.
    assert ergebnisse[ok_instrument.isin].status == "OK"
    assert ergebnisse[defekt.isin].status == "NICHT_VERFUEGBAR"

    repo = SqlAlchemyKursRepository(svc)
    assert repo.latest(ok_instrument.id).kurs == Decimal("111")
    assert repo.latest(defekt.id) is None
