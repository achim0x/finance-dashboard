"""PriceProvider abstraction (spec §6.1) — core of the price architecture.

Concrete providers live in `infrastructure/kurse/` and register themselves
with the registry (`infrastructure/kurse/registry.py`). Adding a provider
means: new implementation + registry entry — nothing else changes
(REQ-PRICE-EXT).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from domain.enums import Kursgruppe


@dataclass(frozen=True)
class Quote:
    """A single quote as returned by a provider (spec §6.1)."""

    kurs: Decimal
    waehrung: str
    boerse: str | None
    zeitstempel: datetime
    vortagesschluss: Decimal | None


@dataclass(frozen=True)
class CredentialFeld:
    """Descriptor of one credential field a provider needs; the setup page
    renders its input fields from these descriptors (spec §6.6)."""

    schluessel: str
    label: str
    geheim: bool = False


@dataclass(frozen=True)
class ProviderMetadaten:
    """Registry metadata a provider declares for the setup page (spec §6.6)."""

    name: str
    anzeigename: str
    kursgruppen: tuple[Kursgruppe, ...]
    benoetigte_credentials: tuple[CredentialFeld, ...] = field(default_factory=tuple)
    # True if the provider needs an interactive login flow (e.g. pytr 2FA).
    interaktive_anmeldung: bool = False


@runtime_checkable
class PriceProvider(Protocol):
    """Interface every price provider implements (spec §6.1)."""

    name: str  # "fmp", "pytr", ...

    def get_quote(self, instrument) -> Quote | None:
        """Current quote for an instrument, or None if unavailable."""
        ...

    def get_history(self, instrument, von: date, bis: date) -> list[tuple[date, Decimal]]:
        """Daily closing prices in [von, bis]; empty list if unavailable."""
        ...
