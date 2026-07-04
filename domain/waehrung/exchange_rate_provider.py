"""ExchangeRateProvider abstraction (spec §6.10), analogous to PriceProvider.

Concrete providers live in `infrastructure/waehrung/`; the registry mirrors
the price-provider registry (name, display name, credential descriptors).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable


@runtime_checkable
class ExchangeRateProvider(Protocol):
    """Interface every FX provider implements (spec §6.10)."""

    name: str  # "fmp", ...

    def get_rate(self, von: str, nach: str, am: date | None = None) -> Decimal | None:
        """Rate von->nach (for `am` if given, else current); None if unavailable."""
        ...

    def get_rate_history(
        self, von: str, nach: str, ab: date, bis: date
    ) -> list[tuple[date, Decimal]]:
        """Daily rates in [ab, bis]; empty list if unavailable."""
        ...
