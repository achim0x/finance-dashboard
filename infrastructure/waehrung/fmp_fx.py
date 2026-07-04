"""FmpExchangeRateProvider — FX rates via the FMP API (spec §6.10, initial
FX provider). Same failure philosophy as the price providers: never raise,
return None/[] and let the service layer fall back to the last known rate.
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

logger = logging.getLogger(__name__)

_BASE = "https://financialmodelingprep.com/api/v3"


class FmpExchangeRateProvider:
    name = "fmp"

    def __init__(self, api_key: str, timeout: float = 10.0):
        self._api_key = api_key
        self._timeout = timeout

    def _get(self, path: str, **params):
        if not self._api_key:
            # No credentials configured -> no network calls (see fmp.py).
            return None
        import httpx  # lazy import

        params["apikey"] = self._api_key
        try:
            resp = httpx.get(f"{_BASE}/{path}", params=params, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("FMP FX request failed (%s): %s", path, type(exc).__name__)
            return None

    def get_rate(self, von: str, nach: str, am: date | None = None) -> Decimal | None:
        paar = f"{von}{nach}"
        if am is not None:
            verlauf = self.get_rate_history(von, nach, am, am)
            return verlauf[0][1] if verlauf else None
        daten = self._get(f"quote/{paar}")
        if isinstance(daten, list) and daten and daten[0].get("price") is not None:
            return Decimal(str(daten[0]["price"]))
        return None

    def get_rate_history(self, von: str, nach: str, ab: date, bis: date):
        paar = f"{von}{nach}"
        daten = self._get(
            f"historical-price-full/{paar}",
            **{"from": ab.isoformat(), "to": bis.isoformat()},
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
