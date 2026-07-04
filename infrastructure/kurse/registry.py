"""Price-provider registry (spec §6.2/§6.6).

Maps provider name -> (metadata, factory). Adding a provider means adding an
implementation module and one `register(...)` call here — services and UI
stay untouched (REQ-PRICE-EXT). The setup page renders credential inputs
from the declared metadata.
"""
from __future__ import annotations

from typing import Callable

from domain.enums import Kursgruppe
from domain.kurse.price_provider import CredentialFeld, PriceProvider, ProviderMetadaten

_REGISTRY: dict[str, tuple[ProviderMetadaten, Callable[[dict], PriceProvider]]] = {}


def register(metadaten: ProviderMetadaten, factory: Callable[[dict], PriceProvider]) -> None:
    """Register a provider. `factory(credentials)` builds a configured instance."""
    _REGISTRY[metadaten.name] = (metadaten, factory)


def get_metadaten(name: str) -> ProviderMetadaten | None:
    eintrag = _REGISTRY.get(name)
    return eintrag[0] if eintrag else None


def build_provider(name: str, credentials: dict) -> PriceProvider | None:
    eintrag = _REGISTRY.get(name)
    return eintrag[1](credentials) if eintrag else None


def list_for_kursgruppe(kursgruppe: Kursgruppe) -> list[ProviderMetadaten]:
    """Providers available for a given price group (setup page dropdown)."""
    return [m for m, _ in _REGISTRY.values() if kursgruppe in m.kursgruppen]


def alle_metadaten() -> list[ProviderMetadaten]:
    return [m for m, _ in _REGISTRY.values()]


def _register_builtin() -> None:
    """Register the built-in providers (spec: FMP for stocks/ETF, pytr for
    leveraged products, plus a manual fallback provider)."""
    from infrastructure.kurse.fmp import FmpPriceProvider
    from infrastructure.kurse.pytr_provider import PytrPriceProvider
    from infrastructure.kurse.manuell import ManuellPriceProvider

    register(
        ProviderMetadaten(
            name="fmp",
            anzeigename="Financial Modeling Prep (FMP)",
            kursgruppen=(Kursgruppe.AKTIEN_ETF,),
            benoetigte_credentials=(
                CredentialFeld("api_key", "API-Key", geheim=True),
            ),
        ),
        lambda creds: FmpPriceProvider(api_key=creds.get("api_key", "")),
    )
    register(
        ProviderMetadaten(
            name="pytr",
            anzeigename="Trade Republic (pytr)",
            kursgruppen=(Kursgruppe.HEBELPRODUKT,),
            benoetigte_credentials=(
                CredentialFeld("telefonnummer", "Telefonnummer"),
                CredentialFeld("pin", "PIN", geheim=True),
            ),
            interaktive_anmeldung=True,
        ),
        lambda creds: PytrPriceProvider(
            telefonnummer=creds.get("telefonnummer", ""),
            pin=creds.get("pin", ""),
            keyfile=creds.get("keyfile", ""),
        ),
    )
    register(
        ProviderMetadaten(
            name="manuell",
            anzeigename="Manuelle Kurspflege",
            kursgruppen=(Kursgruppe.AKTIEN_ETF, Kursgruppe.HEBELPRODUKT),
        ),
        lambda creds: ManuellPriceProvider(),
    )


_register_builtin()
