"""PytrPriceProvider — quotes for leveraged products via pytr / Trade
Republic (spec §6.4).

Design notes:
- pytr is an UNOFFICIAL Trade Republic client (websocket API). Hardening
  points (documented in the README): ToS questions, breaking changes,
  rate limits. Poll moderately; on failure the last known quote stays
  visible flagged as "veraltet" — no hard errors (spec §6.5).
- Auth needs real TR credentials (phone number + PIN) and a 2FA code once;
  the session/keyfile is persisted server-side (`PYTR_KEYFILE`). Credentials
  come only from the encrypted settings/env and are NEVER logged.
- pytr is async (websockets). This provider encapsulates the event loop and
  exposes plain synchronous `get_quote`/`get_history` to the service layer.
  Connections are reused per provider instance, not opened per quote.
- pytr is imported lazily so the app runs without it installed until the
  provider is actually used.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

logger = logging.getLogger(__name__)


class PytrPriceProvider:
    name = "pytr"

    def __init__(self, telefonnummer: str, pin: str, keyfile: str = "", timeout: float = 10.0):
        self._telefonnummer = telefonnummer
        self._pin = pin
        self._keyfile = keyfile
        self._timeout = timeout
        self._api = None  # cached TradeRepublicApi (bundled connection)

    # -- session handling (spec §6.6 login flow) ---------------------------
    def _tr_api(self):
        """Build/reuse a TradeRepublicApi with the persisted session keyfile."""
        if self._api is not None:
            return self._api
        from pytr.api import TradeRepublicApi  # lazy import

        kwargs = {}
        if self._keyfile:
            pfad = Path(self._keyfile)
            kwargs["credentials_file"] = pfad
        self._api = TradeRepublicApi(
            phone_no=self._telefonnummer, pin=self._pin, **kwargs
        )
        return self._api

    def login_starten(self) -> bool:
        """Step 1 of the setup login: request the 4-digit 2FA code
        (TR sends it via app/SMS). Returns True if the request went out."""
        try:
            api = self._tr_api()
            api.initiate_device_reset()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("pytr: login initiation failed: %s", type(exc).__name__)
            return False

    def login_abschliessen(self, code: str) -> bool:
        """Step 2: complete the device reset with the 2FA code; pytr persists
        the keypair server-side. The code itself is never stored (spec §6.6)."""
        try:
            api = self._tr_api()
            api.complete_device_reset(code)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("pytr: login completion failed: %s", type(exc).__name__)
            return False

    def session_status(self) -> str:
        """'angemeldet' | 'abgelaufen' — for the setup page status display."""
        try:
            api = self._tr_api()
            api.login()  # weblogin with persisted keyfile; raises if expired
            return "angemeldet"
        except Exception:  # noqa: BLE001
            return "abgelaufen"

    # -- async bridge -------------------------------------------------------
    def _run(self, coro):
        """Run a pytr coroutine from the synchronous service layer."""
        try:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(asyncio.wait_for(coro, self._timeout))
            finally:
                loop.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("pytr call failed: %s", type(exc).__name__)
            return None

    async def _ticker_snapshot(self, isin: str):
        """Subscribe to the ticker for one ISIN, take a snapshot, unsubscribe."""
        api = self._tr_api()
        await api._ensure_ws_connection()  # noqa: SLF001 — pytr has no public helper
        sub_id = await api.ticker(isin, exchange="LSX")
        try:
            _sub_id, _sub, antwort = await api.recv()
            return antwort
        finally:
            await api.unsubscribe(sub_id)

    # -- PriceProvider ------------------------------------------------------
    def get_quote(self, instrument):
        from domain.kurse.price_provider import Quote

        antwort = self._run(self._ticker_snapshot(instrument.isin))
        if not antwort:
            return None
        try:
            letzter = antwort.get("last", {})
            preis = letzter.get("price")
            if preis is None:
                return None
            vortag = antwort.get("pre", {}).get("price")
            return Quote(
                kurs=Decimal(str(preis)),
                waehrung=getattr(instrument, "waehrung", "EUR") or "EUR",
                boerse="LSX",
                zeitstempel=datetime.now(),
                vortagesschluss=Decimal(str(vortag)) if vortag is not None else None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("pytr: unexpected ticker payload: %s", type(exc).__name__)
            return None

    def get_history(self, instrument, von: date, bis: date):
        """History for warrants/knock-outs is usually unavailable via pytr
        (spec §6.9) — report 'no history' and let the caller fall back to
        forward filling."""
        return []
