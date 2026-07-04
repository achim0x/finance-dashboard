"""Vertical-slice integration test ("Durchstich", spec §14 step 5):
deposit -> instrument -> buy -> holdings/KPIs, through the real web stack
(blueprint -> service -> repository -> template)."""
from decimal import Decimal

from tests.fixtures import fakes
from tests.fixtures.daten import tag


def _formular_zeit(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def test_kauf_bis_bestand_durch_alle_schichten(client, app):
    # Depot anlegen
    resp = client.post(
        "/depots/neu",
        data={
            "name": "Wachstum",
            "eroeffnet_am": tag(0).date().isoformat(),
            "basiswaehrung": "EUR",
            "default_zeitraum": "SEIT_EROEFFNUNG",
            "default_bezugsbasis": "INKL_BARBESTAND",
        },
    )
    assert resp.status_code == 302

    # Instrument anlegen
    resp = client.post(
        "/instrumente/neu",
        data={"isin": "DE0007164600", "name": "SAP SE", "kategorie": "AKTIE", "waehrung": "EUR"},
    )
    assert resp.status_code == 302

    # Einzahlung
    resp = client.post(
        "/depots/1/zahlungen/neu",
        data={"typ": "EINZAHLUNG", "betrag": "10.000,00", "zeitpunkt": _formular_zeit(tag(0))},
    )
    assert resp.status_code == 302

    # Kauf (German decimal notation) — past date triggers the backfill page.
    fakes.fake_aktien.set_quote("DE0007164600", "110", vortagesschluss="105")
    resp = client.post(
        "/depots/1/kaeufe/neu",
        data={
            "instrument_id": "1",
            "stueck": "10",
            "kaufkurs": "100,50",
            "kauf_zeitpunkt": _formular_zeit(tag(1)),
            "spesen": "9,90",
        },
    )
    assert resp.status_code == 302
    assert "/backfill" in resp.headers["Location"]

    # Answer the backfill question with "Nein" (forward filling).
    resp = client.post("/depots/1/kaeufe/1/backfill", data={"antwort": "nein"})
    assert resp.status_code == 302

    # Holdings page shows the position with figures.
    resp = client.get("/depots/1/bestand")
    text = resp.data.decode("utf-8")
    assert resp.status_code == 200
    assert "SAP SE" in text

    # Dashboard KPIs are consistent.
    resp = client.get("/depots/1")
    assert resp.status_code == 200
    with app.test_request_context():
        from flask import g

        g.db_session = app.config["SESSION_FACTORY"]()
        from services.depots import depot_kennzahlen, get_depot
        from services.zahlungen import barbestand

        depot = get_depot(1)
        kennzahlen, positionen = depot_kennzahlen(depot)
        # Cash: 10000 - (10 * 100.50 + 9.90)
        assert barbestand(1) == Decimal("10000") - Decimal("1014.90")
        assert kennzahlen.depotbestand == Decimal("1100")
        assert kennzahlen.gesamtgewinn == kennzahlen.realisierter_gewinn + kennzahlen.unrealisierter_gewinn
        assert positionen[0].kennzahlen.offene_stueck == Decimal("10")
        g.db_session.close()

    # Edit the buy through the web form and verify the recalculation.
    resp = client.post(
        "/depots/1/kaeufe/1/bearbeiten",
        data={
            "instrument_id": "1",
            "stueck": "10",
            "kaufkurs": "90",
            "kauf_zeitpunkt": _formular_zeit(tag(1)),
            "spesen": "0",
        },
    )
    assert resp.status_code == 302
    with app.test_request_context():
        from flask import g

        g.db_session = app.config["SESSION_FACTORY"]()
        from services.zahlungen import barbestand

        assert barbestand(1) == Decimal("10000") - Decimal("900")
        g.db_session.close()


def test_validierungsfehler_zeigt_uebersetzte_meldung(client):
    client.post(
        "/depots/neu",
        data={
            "name": "T",
            "eroeffnet_am": tag(0).date().isoformat(),
            "basiswaehrung": "EUR",
            "default_zeitraum": "SEIT_EROEFFNUNG",
            "default_bezugsbasis": "INKL_BARBESTAND",
        },
    )
    resp = client.post(
        "/depots/1/zahlungen/neu",
        data={"typ": "EINZAHLUNG", "betrag": "-5", "zeitpunkt": _formular_zeit(tag(0))},
        follow_redirects=True,
    )
    # Validation error is flashed as translated German text (REQ-I18N).
    assert "Der Betrag muss größer als 0 sein." in resp.data.decode("utf-8")
