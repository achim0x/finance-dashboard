"""KursService (spec §6): provider routing per price group, quote cache,
setup-page configuration, availability test, manual refresh, closing-price
series (mini charts) and the daily/historical valuation series.

Failure philosophy (spec §6.5): a provider failure is never a hard UI error —
the last known quote stays visible, flagged as "veraltet".
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from domain.entities import Instrument, Kurs, KursEinstellung
from domain.enums import KursQuelle, Kursgruppe
from infrastructure.crypto import decrypt_credentials, encrypt_credentials
from infrastructure.kurse import registry
from infrastructure.persistence.sqlalchemy_repos import (
    SqlAlchemyDepotBewertungRepository,
    SqlAlchemyDividendeRepository,
    SqlAlchemyInstrumentRepository,
    SqlAlchemyKaufRepository,
    SqlAlchemyKursEinstellungRepository,
    SqlAlchemyKursRepository,
    SqlAlchemySchlusskursRepository,
    SqlAlchemySteuerverrechnungRepository,
    SqlAlchemyVerkaufRepository,
    SqlAlchemyWechselkursRepository,
    SqlAlchemyZahlungRepository,
)
from utils.db import current_session, current_settings
from utils.fehler import ValidierungsFehler

logger = logging.getLogger(__name__)

MASKE = "••••"
ZERO = Decimal("0")

_QUELLE_JE_PROVIDER = {"fmp": KursQuelle.FMP.value, "pytr": KursQuelle.PYTR.value}


# --------------------------------------------------------------------------
# Configuration (setup page, spec §6.6)
# --------------------------------------------------------------------------

def _einstellung_row(kursgruppe: Kursgruppe) -> KursEinstellung | None:
    repo = SqlAlchemyKursEinstellungRepository(current_session())
    return repo.get_for_gruppe(kursgruppe.value)


def _env_defaults(kursgruppe: Kursgruppe) -> tuple[str, dict]:
    """Bootstrap/fallback provider + credentials from the env (spec §11)."""
    settings = current_settings()
    if kursgruppe == Kursgruppe.AKTIEN_ETF:
        creds = {"api_key": settings.fmp_api_key} if settings.fmp_api_key else {}
        return settings.provider_aktien_etf, creds
    creds = {}
    if settings.pytr_phone_no:
        creds["telefonnummer"] = settings.pytr_phone_no
    if settings.pytr_pin:
        creds["pin"] = settings.pytr_pin
    return settings.provider_hebelprodukt, creds


def _konfiguration(kursgruppe: Kursgruppe) -> tuple[str, dict, int, bool]:
    """(provider_name, credentials, interval_seconds, active)."""
    settings = current_settings()
    row = _einstellung_row(kursgruppe)
    if row is not None:
        creds = (
            decrypt_credentials(row.credentials_verschluesselt, settings.credentials_enc_key)
            if row.credentials_verschluesselt
            else {}
        )
        env_name, env_creds = _env_defaults(kursgruppe)
        if row.provider_name == env_name:
            for schluessel, wert in env_creds.items():
                creds.setdefault(schluessel, wert)
        return row.provider_name, creds, row.abfrage_intervall_sekunden, row.aktiv
    name, creds = _env_defaults(kursgruppe)
    return name, creds, 300, True


def _provider_fuer_gruppe(kursgruppe: Kursgruppe):
    name, creds, _, aktiv = _konfiguration(kursgruppe)
    if not aktiv:
        return None
    if name == "pytr" and current_settings().pytr_keyfile:
        creds.setdefault("keyfile", current_settings().pytr_keyfile)
    return registry.build_provider(name, creds)


def einstellung_lesen(kursgruppe: Kursgruppe) -> dict:
    """Setup-page view of one price group's configuration. Secret fields are
    only ever returned masked (REQ-KURS-SETUP)."""
    name, creds, intervall, aktiv = _konfiguration(kursgruppe)
    meta = registry.get_metadaten(name)
    felder = []
    for feld in (meta.benoetigte_credentials if meta else ()):
        wert = creds.get(feld.schluessel, "")
        felder.append(
            {
                "schluessel": feld.schluessel,
                "label": feld.label,
                "geheim": feld.geheim,
                "wert": (MASKE if wert else "") if feld.geheim else wert,
            }
        )
    return {
        "kursgruppe": kursgruppe.value,
        "provider_name": name,
        "abfrage_intervall_sekunden": intervall,
        "aktiv": aktiv,
        "felder": felder,
        "verfuegbare_provider": registry.list_for_kursgruppe(kursgruppe),
        "interaktive_anmeldung": bool(meta and meta.interaktive_anmeldung),
        "verschluesselung_ok": bool(current_settings().credentials_enc_key),
    }


def einstellung_speichern(
    kursgruppe: Kursgruppe,
    provider_name: str,
    credentials: dict,
    intervall: int,
    aktiv: bool,
) -> None:
    """Persist provider/credentials/interval per price group (spec §6.6).

    Secrets: an empty or masked input keeps the previously stored value;
    everything is encrypted with `CREDENTIALS_ENC_KEY` before storage.
    """
    settings = current_settings()
    session = current_session()
    meta = registry.get_metadaten(provider_name)
    if meta is None or kursgruppe not in meta.kursgruppen:
        raise ValidierungsFehler("fehler.provider_ungueltig")
    if intervall < 10:
        raise ValidierungsFehler("fehler.intervall_ungueltig")

    row = _einstellung_row(kursgruppe)
    alt: dict = {}
    if row is not None and row.credentials_verschluesselt:
        alt = decrypt_credentials(row.credentials_verschluesselt, settings.credentials_enc_key)

    zusammengefuehrt = dict(alt) if (row is not None and row.provider_name == provider_name) else {}
    for feld in meta.benoetigte_credentials:
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
        row = KursEinstellung(kursgruppe=kursgruppe.value, provider_name=provider_name)
        session.add(row)
    row.provider_name = provider_name
    row.credentials_verschluesselt = token
    row.abfrage_intervall_sekunden = intervall
    row.aktiv = aktiv
    row.geaendert_am = datetime.now()
    session.commit()


# --------------------------------------------------------------------------
# Quotes: cache + fetch (spec §6.5)
# --------------------------------------------------------------------------

def _symbol_cachen(instrument: Instrument, provider) -> None:
    """Resolve+cache the provider symbol on the instrument (spec §6.3)."""
    if instrument.symbol or not hasattr(provider, "resolve_symbol"):
        return
    symbol = provider.resolve_symbol(instrument.isin)
    if symbol:
        instrument.symbol = symbol
        current_session().flush()


def _quote_speichern(instrument: Instrument, provider) -> Kurs | None:
    quote = provider.get_quote(instrument)
    if quote is None:
        return None
    kurs = Kurs(
        instrument_id=instrument.id,
        kurs=quote.kurs,
        waehrung=quote.waehrung,
        boerse=quote.boerse,
        zeitstempel=quote.zeitstempel,
        quelle=_QUELLE_JE_PROVIDER.get(provider.name, KursQuelle.MANUELL.value),
        vortagesschluss=quote.vortagesschluss,
    )
    SqlAlchemyKursRepository(current_session()).add(kurs)
    return kurs


def aktueller_kurs(instrument: Instrument, erzwingen: bool = False) -> Kurs | None:
    """Latest quote of an instrument, refreshed through the configured
    provider when older than `KURS_CACHE_TTL` (or when forced).

    Provider failure -> the last stored quote is returned unchanged (the
    caller flags it via `kurs_ist_veraltet`, REQ-PRICE-FALLBACK).
    """
    repo = SqlAlchemyKursRepository(current_session())
    juengster = repo.latest(instrument.id)
    ttl = timedelta(seconds=current_settings().kurs_cache_ttl)
    if not erzwingen and juengster is not None and datetime.now() - juengster.zeitstempel <= ttl:
        return juengster

    provider = _provider_fuer_gruppe(instrument.kursgruppe)
    if provider is not None:
        _symbol_cachen(instrument, provider)
        neu = _quote_speichern(instrument, provider)
        if neu is not None:
            return neu
    return juengster


def kurs_ist_veraltet(kurs: Kurs, instrument: Instrument) -> bool:
    """A quote is stale when older than twice the configured polling
    interval (at least 10 minutes) — display hint per spec §6.5."""
    _, _, intervall, _ = _konfiguration(instrument.kursgruppe)
    grenze = max(2 * intervall, 600)
    return datetime.now() - kurs.zeitstempel > timedelta(seconds=grenze)


def manuellen_kurs_erfassen(
    instrument_id: int, wert: Decimal, waehrung: str = "EUR"
) -> Kurs:
    """Manual quote entry — the emergency fallback (Kurs.quelle MANUELL)."""
    vorheriger = SqlAlchemyKursRepository(current_session()).latest(instrument_id)
    kurs = Kurs(
        instrument_id=instrument_id,
        kurs=wert,
        waehrung=waehrung,
        boerse=None,
        zeitstempel=datetime.now(),
        quelle=KursQuelle.MANUELL.value,
        vortagesschluss=vorheriger.kurs if vorheriger is not None else None,
    )
    SqlAlchemyKursRepository(current_session()).add(kurs)
    current_session().commit()
    return kurs


# --------------------------------------------------------------------------
# Availability test & manual refresh (spec §6.7/§6.8)
# --------------------------------------------------------------------------

@dataclass
class Testergebnis:
    """Per-instrument result of the availability test / manual refresh."""

    instrument: Instrument
    status: str  # "OK" | "FEHLER" | "NICHT_VERFUEGBAR"
    kurs: Decimal | None = None
    waehrung: str | None = None
    zeitstempel: datetime | None = None
    quelle: str | None = None
    meldung: str | None = None  # i18n key of the failure cause


def _instrumente_mit_position(depot_id: int) -> list[Instrument]:
    """Instruments with an open position in the depot."""
    session = current_session()
    instrumente = SqlAlchemyInstrumentRepository(session).list_in_depot(depot_id)
    offen = []
    for instrument in instrumente:
        kaeufe = SqlAlchemyKaufRepository(session).list_for_position(depot_id, instrument.id)
        verkaeufe = SqlAlchemyVerkaufRepository(session).list_for_position(depot_id, instrument.id)
        gekauft = sum((k.stueck for k in kaeufe), ZERO)
        verkauft = sum((v.stueck for v in verkaeufe), ZERO)
        if gekauft - verkauft > ZERO:
            offen.append(instrument)
    return offen


def depot_testen(depot_id: int) -> list[Testergebnis]:
    """Availability test (spec §6.7): query ALL instruments of the depot via
    their configured providers and report per-instrument results. Writes
    NOTHING — no quotes, no valuations (REQ-KURS-TEST)."""
    ergebnisse = []
    for instrument in _instrumente_mit_position(depot_id):
        provider = _provider_fuer_gruppe(instrument.kursgruppe)
        if provider is None:
            ergebnisse.append(
                Testergebnis(instrument, "FEHLER", meldung="kurse.test.kein_provider")
            )
            continue
        try:
            quote = provider.get_quote(instrument)
        except Exception:  # noqa: BLE001 — a single failure must not stop the test
            quote = None
        if quote is None:
            ergebnisse.append(
                Testergebnis(instrument, "NICHT_VERFUEGBAR", meldung="kurse.test.kein_kurs")
            )
        else:
            ergebnisse.append(
                Testergebnis(
                    instrument,
                    "OK",
                    kurs=quote.kurs,
                    waehrung=quote.waehrung,
                    zeitstempel=quote.zeitstempel,
                    quelle=provider.name,
                )
            )
    return ergebnisse


def depot_aktualisieren(depot_id: int) -> list[Testergebnis]:
    """Manual refresh (spec §6.8): fetch quotes for all instruments of the
    depot now, independent of the polling interval. Individual failures are
    reported but never stop the remaining instruments (REQ-KURS-MANUELL)."""
    session = current_session()
    ergebnisse = []
    for instrument in _instrumente_mit_position(depot_id):
        provider = _provider_fuer_gruppe(instrument.kursgruppe)
        if provider is None:
            ergebnisse.append(
                Testergebnis(instrument, "FEHLER", meldung="kurse.test.kein_provider")
            )
            continue
        try:
            _symbol_cachen(instrument, provider)
            kurs = _quote_speichern(instrument, provider)
        except Exception:  # noqa: BLE001
            kurs = None
        if kurs is None:
            ergebnisse.append(
                Testergebnis(instrument, "NICHT_VERFUEGBAR", meldung="kurse.test.kein_kurs")
            )
        else:
            ergebnisse.append(
                Testergebnis(
                    instrument,
                    "OK",
                    kurs=kurs.kurs,
                    waehrung=kurs.waehrung,
                    zeitstempel=kurs.zeitstempel,
                    quelle=kurs.quelle,
                )
            )
    session.commit()
    return ergebnisse


def veraltete_kurse(depot_id: int) -> int:
    """Badge convention: number of open positions with a stale/missing quote."""
    zaehler = 0
    repo = SqlAlchemyKursRepository(current_session())
    for instrument in _instrumente_mit_position(depot_id):
        kurs = repo.latest(instrument.id)
        if kurs is None or kurs_ist_veraltet(kurs, instrument):
            zaehler += 1
    return zaehler


# --------------------------------------------------------------------------
# Closing prices: mini charts & backfill (spec §6.9)
# --------------------------------------------------------------------------

def schlusskurse_backfill(instrument_id: int, von: date, bis: date) -> int:
    """Backfill the daily closing series via the provider history.

    Returns the number of stored days; 0 means "no history available" — the
    caller falls back to forward filling (REQ-CHART-BACKFILL). Idempotent
    per (instrument, date)."""
    session = current_session()
    instrument = SqlAlchemyInstrumentRepository(session).get(instrument_id)
    if instrument is None:
        raise ValidierungsFehler("fehler.nicht_gefunden")
    provider = _provider_fuer_gruppe(instrument.kursgruppe)
    if provider is None:
        return 0
    try:
        historie = provider.get_history(instrument, von, bis)
    except Exception:  # noqa: BLE001
        historie = []
    if not historie:
        return 0
    repo = SqlAlchemySchlusskursRepository(session)
    quelle = _QUELLE_JE_PROVIDER.get(provider.name, KursQuelle.MANUELL.value)
    for datum, wert in historie:
        if von <= datum <= bis:
            repo.upsert(instrument_id, datum, wert, quelle)
    session.commit()
    return len(historie)


def schlusskurs_schreiben(
    instrument_id: int, datum: date, wert: Decimal, quelle: str
) -> None:
    """Store one daily close (used by the batch job); idempotent."""
    SqlAlchemySchlusskursRepository(current_session()).upsert(
        instrument_id, datum, wert, quelle
    )


def mini_chart(instrument_id: int, ab_datum: date) -> list[tuple[date, Decimal]]:
    """Closing-price series since the (oldest open) buy date (spec §6.9)."""
    reihe = SqlAlchemySchlusskursRepository(current_session()).series(instrument_id, ab_datum)
    return [(s.datum, s.schlusskurs) for s in reihe]


# --------------------------------------------------------------------------
# Valuation series (spec §4.7/§5.6)
# --------------------------------------------------------------------------

def bewertung_schreiben(depot_id: int, datum: date | None = None) -> None:
    """Write today's `DepotBewertung` from the current KPIs (daily job /
    manual refresh). Flushes only — callers own the transaction."""
    from services.depots import get_depot  # lazy: avoid cycle
    from services.positionen import positionen_fuer_depot  # lazy: avoid cycle
    from services.zahlungen import barbestand  # lazy: avoid cycle

    depot = get_depot(depot_id)
    if depot is None:
        return
    datum = datum or date.today()
    positionen = positionen_fuer_depot(depot, mit_kursen=True)
    depotbestand = sum((p.kennzahlen.positionswert for p in positionen), ZERO)
    bar = barbestand(depot_id)
    SqlAlchemyDepotBewertungRepository(current_session()).upsert(
        depot_id, datum, depotbestand, bar, depotbestand + bar
    )


def bewertungen_neu_aufbauen(depot_id: int, ab: date) -> None:
    """Rebuild the valuation series from `ab` until today — exclusively from
    daily closing prices (`Schlusskurs`) plus daily FX rates; never intraday
    quotes (spec §5.6, REQ-REVAL-CLOSE). Missing days carry the last known
    close/rate forward. Flushes only; the caller owns the transaction.

    All data is preloaded once so the day loop runs without further queries
    (this executes on every booking change, spec §4.11).
    """
    from domain.berechnung import offene_tranchen
    from domain.berechnung.ledger import barbestand as _bar
    from services.depots import get_depot  # lazy: avoid cycle

    session = current_session()
    depot = get_depot(depot_id)
    if depot is None:
        return
    ab = max(ab, depot.eroeffnet_am)
    heute = date.today()
    if ab > heute:
        return

    kauf_repo = SqlAlchemyKaufRepository(session)
    verkauf_repo = SqlAlchemyVerkaufRepository(session)
    schluss_repo = SqlAlchemySchlusskursRepository(session)
    fx_repo = SqlAlchemyWechselkursRepository(session)
    bewertung_repo = SqlAlchemyDepotBewertungRepository(session)

    instrumente = SqlAlchemyInstrumentRepository(session).list_in_depot(depot_id)
    kaeufe_je_instrument = {
        i.id: kauf_repo.list_for_position(depot_id, i.id) for i in instrumente
    }
    verkaeufe_je_instrument = {
        i.id: verkauf_repo.list_for_position(depot_id, i.id) for i in instrumente
    }
    cash_quellen = {
        "zahlungen": SqlAlchemyZahlungRepository(session).list_for_depot(depot_id),
        "kaeufe": kauf_repo.list_for_depot(depot_id),
        "verkaeufe": verkauf_repo.list_for_depot(depot_id),
        "dividenden": SqlAlchemyDividendeRepository(session).list_for_depot(depot_id),
        "steuerverrechnungen": SqlAlchemySteuerverrechnungRepository(session).list_for_depot(depot_id),
    }
    # Closing series per instrument, incl. the last close before `ab` as the
    # carry-forward seed.
    schluss_je_instrument: dict[int, list] = {}
    for instrument in instrumente:
        reihe = list(schluss_repo.series(instrument.id, ab))
        vorher = schluss_repo.latest_before(instrument.id, ab - timedelta(days=1))
        if vorher is not None:
            reihe.insert(0, vorher)
        schluss_je_instrument[instrument.id] = reihe
    # Daily FX rates per needed currency pair (carry-forward likewise).
    fx_reihen: dict[str, list] = {}
    for instrument in instrumente:
        if instrument.waehrung != depot.basiswaehrung:
            paar = f"{instrument.waehrung}/{depot.basiswaehrung}"
            if paar not in fx_reihen:
                fx_reihen[paar] = [
                    fx
                    for fx in _fx_alle(fx_repo, instrument.waehrung, depot.basiswaehrung)
                ]

    schluss_zeiger = {iid: 0 for iid in schluss_je_instrument}
    fx_zeiger = {paar: 0 for paar in fx_reihen}

    def _fortgeschrieben(reihe, zeiger_map, schluessel, tag, datum_attr):
        """Advance the pointer to the last entry <= tag; None if before all."""
        reihe_liste = reihe[schluessel]
        z = zeiger_map[schluessel]
        while z + 1 < len(reihe_liste) and getattr(reihe_liste[z + 1], datum_attr) <= tag:
            z += 1
        zeiger_map[schluessel] = z
        if not reihe_liste or getattr(reihe_liste[z], datum_attr) > tag:
            return None
        return reihe_liste[z]

    tag = ab
    while tag <= heute:
        tagesende = datetime(tag.year, tag.month, tag.day, 23, 59, 59)
        depotbestand = ZERO
        for instrument in instrumente:
            kaeufe = [
                k for k in kaeufe_je_instrument[instrument.id] if k.kauf_zeitpunkt <= tagesende
            ]
            if not kaeufe:
                continue
            verkaeufe = [
                v
                for v in verkaeufe_je_instrument[instrument.id]
                if v.verkauf_zeitpunkt <= tagesende
            ]
            tranchen = offene_tranchen(kaeufe, verkaeufe)
            stueck = sum((t.offene_stueck for t in tranchen), ZERO)
            if stueck == ZERO:
                continue
            schluss = _fortgeschrieben(
                schluss_je_instrument, schluss_zeiger, instrument.id, tag, "datum"
            )
            if schluss is None:
                continue  # no close known at all -> instrument not valuable yet
            wert = stueck * schluss.schlusskurs
            if instrument.waehrung != depot.basiswaehrung:
                paar = f"{instrument.waehrung}/{depot.basiswaehrung}"
                fx = _fortgeschrieben(fx_reihen, fx_zeiger, paar, tag, "datum")
                if fx is not None:
                    wert *= fx.kurs
                # No known rate at all -> unconverted (documented limitation).
            depotbestand += wert
        bar = _bar(bis=tagesende, **cash_quellen)
        bewertung_repo.upsert(depot_id, tag, depotbestand, bar, depotbestand + bar)
        tag += timedelta(days=1)


def _fx_alle(fx_repo, von: str, nach: str):
    """All cached daily rates for a pair, ordered by date (for the rebuild)."""
    from sqlalchemy import select

    from domain.entities import Wechselkurs

    stmt = (
        select(Wechselkurs)
        .where(Wechselkurs.von == von, Wechselkurs.nach == nach)
        .order_by(Wechselkurs.datum)
    )
    return fx_repo._s.scalars(stmt).all()  # noqa: SLF001 — module-internal helper


# --------------------------------------------------------------------------
# pytr login flow (setup page, spec §6.6)
# --------------------------------------------------------------------------

def _pytr_provider():
    provider = _provider_fuer_gruppe(Kursgruppe.HEBELPRODUKT)
    if provider is None or provider.name != "pytr":
        raise ValidierungsFehler("kurse.setup.pytr_nicht_konfiguriert")
    return provider


def pytr_login_starten() -> bool:
    """Step 1: trigger the TR login; TR sends the 4-digit code (app/SMS)."""
    return _pytr_provider().login_starten()


def pytr_login_abschliessen(code: str) -> bool:
    """Step 2: complete the login with the 2FA code. The code itself is
    never persisted (spec §6.6)."""
    code = (code or "").strip()
    if not code:
        raise ValidierungsFehler("fehler.code_fehlt")
    return _pytr_provider().login_abschliessen(code)


def pytr_session_status() -> str:
    """'angemeldet' | 'abgelaufen' | 'nicht_konfiguriert' for the status display."""
    try:
        return _pytr_provider().session_status()
    except ValidierungsFehler:
        return "nicht_konfiguriert"
