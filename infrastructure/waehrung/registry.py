"""FX-provider registry (spec §6.10) — mirrors the price-provider registry.

New FX provider = new implementation + one `register(...)` call here;
selectable in the setup page without touching services or UI (REQ-FX-PROVIDER).
"""
from __future__ import annotations

from typing import Callable

from domain.kurse.price_provider import CredentialFeld, ProviderMetadaten
from domain.waehrung.exchange_rate_provider import ExchangeRateProvider

_REGISTRY: dict[str, tuple[ProviderMetadaten, Callable[[dict], ExchangeRateProvider]]] = {}


def register(metadaten: ProviderMetadaten, factory: Callable[[dict], ExchangeRateProvider]) -> None:
    _REGISTRY[metadaten.name] = (metadaten, factory)


def get_metadaten(name: str) -> ProviderMetadaten | None:
    eintrag = _REGISTRY.get(name)
    return eintrag[0] if eintrag else None


def build_provider(name: str, credentials: dict) -> ExchangeRateProvider | None:
    eintrag = _REGISTRY.get(name)
    return eintrag[1](credentials) if eintrag else None


def alle_metadaten() -> list[ProviderMetadaten]:
    return [m for m, _ in _REGISTRY.values()]


def _register_builtin() -> None:
    from infrastructure.waehrung.fmp_fx import FmpExchangeRateProvider

    register(
        ProviderMetadaten(
            name="fmp",
            anzeigename="Financial Modeling Prep (FMP)",
            kursgruppen=(),
            benoetigte_credentials=(CredentialFeld("api_key", "API-Key", geheim=True),),
        ),
        lambda creds: FmpExchangeRateProvider(api_key=creds.get("api_key", "")),
    )


_register_builtin()
