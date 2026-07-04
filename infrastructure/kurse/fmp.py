"""FmpPriceProvider — quotes/history for stocks & ETFs via the FMP API
(spec §6.3).

Known limitation: the free FMP tier covers US listings/OTC; native German
exchanges (`*.DE`) require FMP premium (HTTP 402). Strategy: prefer the
available (OTC/US) symbol; the premium requirement is documented in the
README as an operations/cost note.

The provider resolves ISIN -> symbol once and the service layer caches the
result on `Instrument.symbol`. Errors never raise into the caller: failures
return None/[] so the UI can fall back to the last known quote ("veraltet",
spec §6.5). The API key is never logged.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

_BASE = "https://financialmodelingprep.com/api/v3"


class FmpPriceProvider:
    name = "fmp"

    def __init__(self, api_key: str, timeout: float = 10.0):
        self._api_key = api_key
        self._timeout = timeout

    # -- internal ---------------------------------------------------------
    def _get(self, path: str, **params):
        """GET helper; returns parsed JSON or None on any failure."""
        if not self._api_key:
            # No credentials configured -> stay offline instead of producing
            # guaranteed 401s (also keeps tests/CI free of network calls).
            return None
        import httpx  # lazy import — keeps the app importable without httpx

        params["apikey"] = self._api_key
        try:
            resp = httpx.get(f"{_BASE}/{path}", params=params, timeout=self._timeout)
            if resp.status_code == 402:
                logger.warning("FMP: premium required for %s (HTTP 402)", path)
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001 — provider must never crash callers
            logger.warning("FMP request failed (%s): %s", path, type(exc).__name__)
            return None

    def resolve_symbol(self, isin: str) -> str | None:
        """ISIN -> FMP symbol via the ISIN search endpoint (spec §6.3)."""
        daten = self._get("search-isin", isin=isin)
        if isinstance(daten, list) and daten:
            return daten[0].get("symbol")
        return None

    def _symbol(self, instrument) -> str | None:
        if getattr(instrument, "symbol", None):
            return instrument.symbol
        return self.resolve_symbol(instrument.isin)

    # -- PriceProvider ----------------------------------------------------
    def get_quote(self, instrument):
        from domain.kurse.price_provider import Quote

        symbol = self._symbol(instrument)
        if not symbol:
            return None
        daten = self._get(f"quote/{symbol}")
        if not isinstance(daten, list) or not daten:
            return None
        zeile = daten[0]
        preis = zeile.get("price")
        if preis is None:
            return None
        ts = zeile.get("timestamp")
        zeitstempel = datetime.fromtimestamp(ts) if ts else datetime.now()
        vortag = zeile.get("previousClose")
        return Quote(
            kurs=Decimal(str(preis)),
            waehrung=getattr(instrument, "waehrung", "EUR") or "EUR",
            boerse=zeile.get("exchange"),
            zeitstempel=zeitstempel,
            vortagesschluss=Decimal(str(vortag)) if vortag is not None else None,
        )

    def get_history(self, instrument, von: date, bis: date):
        symbol = self._symbol(instrument)
        if not symbol:
            return []
        daten = self._get(
            f"historical-price-full/{symbol}",
            **{"from": von.isoformat(), "to": bis.isoformat()},
        )
        if not isinstance(daten, dict):
            return []
        punkte = []
        for zeile in daten.get("historical", []):
            try:
                punkte.append(
                    (date.fromisoformat(zeile["date"]), Decimal(str(zeile["close"])))
                )
            except (KeyError, ValueError):
                continue
        punkte.sort(key=lambda p: p[0])
        return punkte
