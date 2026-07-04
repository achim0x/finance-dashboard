"""FX service (spec §5.7/§6.10): provider routing, caching, conversion.

Failure philosophy: FX provider down -> last known rate flagged "veraltet";
no rate at all -> unconverted with a hint. Never a hard error in the UI.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from domain.entities import WaehrungsEinstellung
from infrastructure.crypto import decrypt_credentials, encrypt_credentials
from infrastructure.persistence.sqlalchemy_repos import (
    SqlAlchemyWaehrungsEinstellungRepository,
    SqlAlchemyWechselkursRepository,
)
from infrastructure.waehrung import registry
from utils.db import current_session, current_settings

MASKE = "••••"

#: Conversion status values returned by `rate`/`umrechnen`.
OK = "ok"
VERALTET = "veraltet"
UNKONVERTIERT = "unkonvertiert"


def _einstellung_row() -> WaehrungsEinstellung | None:
    return SqlAlchemyWaehrungsEinstellungRepository(current_session()).get_single()


def _konfiguration() -> tuple[str, dict, int, bool]:
    """(provider_name, credentials, interval, active) — DB row first, env
    bootstrap as fallback (spec §6.10/§11)."""
    settings = current_settings()
    row = _einstellung_row()
    if row is not None:
        creds = decrypt_credentials(row.credentials_verschluesselt, settings.credentials_enc_key) \
            if row.credentials_verschluesselt else {}
        if not creds.get("api_key") and settings.fmp_api_key:
            creds.setdefault("api_key", settings.fmp_api_key)
        return row.provider_name, creds, row.abfrage_intervall_sekunden, row.aktiv
    creds = {"api_key": settings.fmp_api_key} if settings.fmp_api_key else {}
    return settings.fx_provider, creds, 3600, True


def _provider():
    name, creds, _, aktiv = _konfiguration()
    if not aktiv:
        return None
    return registry.build_provider(name, creds)


def rate(von: str, nach: str, am: date | None = None) -> tuple[Decimal | None, str]:
    """FX rate von->nach with cache; returns (rate, status).

    status: OK (fresh/exact), VERALTET (fell back to the last known rate),
    UNKONVERTIERT (no rate available at all — rate is None).
    """
    if von == nach:
        return Decimal("1"), OK

    repo = SqlAlchemyWechselkursRepository(current_session())
    _, _, intervall, _ = _konfiguration()

    if am is not None:
        # Historical daily rate (spec §5.7): exact day, else provider, else
        # carry forward the last known rate.
        exakt = repo.get_am(von, nach, am)
        if exakt is not None:
            return exakt.kurs, OK
        provider = _provider()
        if provider is not None:
            wert = provider.get_rate(von, nach, am=am)
            if wert is not None:
                repo.upsert(von, nach, am, wert, provider.name)
                return wert, OK
        vorher = repo.latest_before(von, nach, am)
        if vorher is not None:
            return vorher.kurs, VERALTET
        return None, UNKONVERTIERT

    # Current rate: cached value younger than the configured interval wins.
    juengster = repo.latest(von, nach)
    if juengster is not None:
        alter = datetime.now() - juengster.zeitstempel
        if alter <= timedelta(seconds=intervall):
            return juengster.kurs, OK
    provider = _provider()
    if provider is not None:
        wert = provider.get_rate(von, nach)
        if wert is not None:
            repo.upsert(von, nach, date.today(), wert, provider.name)
            return wert, OK
    if juengster is not None:
        return juengster.kurs, VERALTET
    return None, UNKONVERTIERT


def umrechnen(betrag: Decimal, von: str, nach: str, am: date | None = None) -> tuple[Decimal, str]:
    """Convert an amount; on UNKONVERTIERT the amount is returned unchanged
    (the caller shows a hint, spec §5.7)."""
    wert, status = rate(von, nach, am=am)
    if wert is None:
        return betrag, UNKONVERTIERT
    return betrag * wert, status


def verfuegbare_provider():
    """Registry metadata for the setup page dropdown."""
    return registry.alle_metadaten()


def einstellung_lesen() -> dict:
    """Setup-page view of the FX configuration; secret fields only masked."""
    settings = current_settings()
    name, creds, intervall, aktiv = _konfiguration()
    meta = registry.get_metadaten(name)
    felder = []
    for feld in (meta.benoetigte_credentials if meta else ()):
        wert = creds.get(feld.schluessel, "")
        felder.append(
            {
                "schluessel": feld.schluessel,
                "label": feld.label,
                "geheim": feld.geheim,
                # Secrets are never returned in cleartext (REQ-KURS-SETUP).
                "wert": (MASKE if wert else "") if feld.geheim else wert,
            }
        )
    return {
        "provider_name": name,
        "abfrage_intervall_sekunden": intervall,
        "aktiv": aktiv,
        "felder": felder,
        "verfuegbare_provider": verfuegbare_provider(),
        "verschluesselung_ok": bool(settings.credentials_enc_key),
    }


def einstellung_speichern(provider_name: str, credentials: dict, intervall: int, aktiv: bool) -> None:
    """Persist FX config; secret fields keep their old value unless a new
    one was entered (spec §6.6). Credentials are encrypted at rest."""
    settings = current_settings()
    session = current_session()
    repo = SqlAlchemyWaehrungsEinstellungRepository(session)
    row = repo.get_single()

    alt = {}
    if row is not None and row.credentials_verschluesselt:
        alt = decrypt_credentials(row.credentials_verschluesselt, settings.credentials_enc_key)

    meta = registry.get_metadaten(provider_name)
    zusammengefuehrt = dict(alt) if (row is not None and row.provider_name == provider_name) else {}
    for feld in (meta.benoetigte_credentials if meta else ()):
        neu = (credentials.get(feld.schluessel) or "").strip()
        if neu and neu != MASKE:
            zusammengefuehrt[feld.schluessel] = neu
        elif not feld.geheim and feld.schluessel in credentials:
            zusammengefuehrt[feld.schluessel] = neu

    token = (
        encrypt_credentials(zusammengefuehrt, settings.credentials_enc_key)
        if zusammengefuehrt
        else None
    )
    if row is None:
        row = WaehrungsEinstellung(provider_name=provider_name)
        session.add(row)
    row.provider_name = provider_name
    row.credentials_verschluesselt = token
    row.abfrage_intervall_sekunden = intervall
    row.aktiv = aktiv
    row.geaendert_am = datetime.now()
    session.commit()
