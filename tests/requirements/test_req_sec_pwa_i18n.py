"""Security, PWA and i18n requirements (spec §10)."""
import json
import logging

import pytest

from domain.enums import Kursgruppe


@pytest.mark.requirement("REQ-SEC-CREDS")
def test_credentials_nie_im_log_und_nur_verschluesselt_in_db(svc, caplog):
    from infrastructure.persistence.sqlalchemy_repos import SqlAlchemyKursEinstellungRepository
    from services.kurse import aktueller_kurs, einstellung_lesen, einstellung_speichern
    from tests.fixtures import fakes
    from tests.fixtures.daten import mach_instrument

    geheimnis = "tr-pin-9876-super-geheim"
    with caplog.at_level(logging.DEBUG):
        einstellung_speichern(
            Kursgruppe.HEBELPRODUKT, "fake_hebel", {"pin": geheimnis}, 300, True
        )
        instrument = mach_instrument("DE000KB1234B", "KO", "KNOCKOUT")
        fakes.fake_hebel.set_quote(instrument.isin, "5")
        aktueller_kurs(instrument)
        einstellung_lesen(Kursgruppe.HEBELPRODUKT)

    # Never in logs (spec §6.4/§6.6).
    assert geheimnis not in caplog.text
    # In the DB only encrypted.
    row = SqlAlchemyKursEinstellungRepository(svc).get_for_gruppe("HEBELPRODUKT")
    assert geheimnis not in (row.credentials_verschluesselt or "")
    # Never returned in cleartext to the UI.
    ansicht = einstellung_lesen(Kursgruppe.HEBELPRODUKT)
    assert geheimnis not in json.dumps(ansicht["felder"])


@pytest.mark.requirement("REQ-SEC-CREDS")
def test_verschluesselung_erfordert_env_schluessel():
    from infrastructure.crypto import (
        VerschluesselungFehltError,
        decrypt_credentials,
        encrypt_credentials,
    )

    token = encrypt_credentials({"api_key": "x"}, "irgendein-schluessel")
    assert decrypt_credentials(token, "irgendein-schluessel") == {"api_key": "x"}
    with pytest.raises(VerschluesselungFehltError):
        encrypt_credentials({"api_key": "x"}, "")


@pytest.mark.requirement("REQ-PWA-01")
def test_manifest_erreichbar_und_gueltig(client):
    resp = client.get("/static/manifest.webmanifest")
    assert resp.status_code == 200
    manifest = json.loads(resp.data)
    for pflichtfeld in ("name", "start_url", "scope", "display", "icons"):
        assert pflichtfeld in manifest
    assert manifest["display"] == "standalone"


@pytest.mark.requirement("REQ-PWA-02")
def test_service_worker_mit_headers(client):
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert "application/javascript" in resp.headers["Content-Type"]
    assert resp.headers["Service-Worker-Allowed"] == "/"
    assert "no-cache" in resp.headers["Cache-Control"]


@pytest.mark.requirement("REQ-PWA-03")
def test_offline_seite_erreichbar(client):
    resp = client.get("/offline")
    assert resp.status_code == 200


@pytest.mark.requirement("REQ-I18N")
def test_deutsch_ist_vollstaendig_implementierte_erstsprache(client):
    resp = client.get("/")
    text = resp.data.decode("utf-8")
    assert "Depot-Übersicht" in text  # translated, not the raw key
    assert "uebersicht.titel" not in text


@pytest.mark.requirement("REQ-I18N")
def test_neue_sprache_nur_per_uebersetzungsdatei(app, tmp_path, monkeypatch):
    """Adding a language = adding one JSON file; lookup falls back to German
    and finally to the key itself (spec §2/§10)."""
    from utils import i18n

    (tmp_path / "de.json").write_text(
        json.dumps({"nav": {"uebersicht": "Übersicht", "nur_deutsch": "Nur DE"}}),
        encoding="utf-8",
    )
    (tmp_path / "en.json").write_text(
        json.dumps({"nav": {"uebersicht": "Overview"}}), encoding="utf-8"
    )
    monkeypatch.setattr(i18n, "_VERZEICHNIS", tmp_path)
    i18n.cache_leeren()
    try:
        assert i18n.verfuegbare_sprachen() == ["de", "en"]
        assert i18n.uebersetze("nav.uebersicht", "en") == "Overview"
        # Missing key in the new language -> German fallback.
        assert i18n.uebersetze("nav.nur_deutsch", "en") == "Nur DE"
        # Unknown key -> the key itself as a visible marker.
        assert i18n.uebersetze("gibt.es.nicht", "en") == "gibt.es.nicht"
    finally:
        i18n.cache_leeren()


@pytest.mark.requirement("REQ-I18N")
def test_sprachumschaltung_wird_in_session_gespeichert(client):
    resp = client.post("/einstellungen/sprache", data={"sprache": "de"})
    assert resp.status_code == 302
    with client.session_transaction() as session:
        assert session["sprache"] == "de"
