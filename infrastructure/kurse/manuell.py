"""Manual price provider — the emergency fallback (spec §13).

Never fetches anything; quotes are maintained by hand through the UI/MCP
(`Kurs.quelle == MANUELL`). `get_quote` returns None so the service layer
keeps showing the latest stored quote flagged as manual.
"""
from __future__ import annotations

from datetime import date


class ManuellPriceProvider:
    name = "manuell"

    def get_quote(self, instrument):
        return None

    def get_history(self, instrument, von: date, bis: date):
        return []
