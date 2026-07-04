"""Fake price/FX providers for tests.

Providers are NEVER tested against real FMP/Trade Republic in CI (spec §10).
The fakes register in the same registries as the real providers, proving the
extensibility contract at the same time (REQ-PRICE-EXT/REQ-FX-PROVIDER).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from domain.enums import Kursgruppe
from domain.kurse.price_provider import CredentialFeld, ProviderMetadaten, Quote


class FakePriceProvider:
    """Configurable in-memory provider; records every quote request."""

    def __init__(self, name: str):
        self.name = name
        self.quotes: dict[str, Quote] = {}
        self.historie: dict[str, list[tuple[date, Decimal]]] = {}
        self.aufrufe: list[str] = []

    def set_quote(self, isin: str, kurs: str, vortagesschluss: str | None = None,
                  waehrung: str = "EUR") -> None:
        self.quotes[isin] = Quote(
            kurs=Decimal(kurs),
            waehrung=waehrung,
            boerse="FAKE",
            zeitstempel=datetime.now(),
            vortagesschluss=Decimal(vortagesschluss) if vortagesschluss else None,
        )

    def reset(self) -> None:
        self.quotes.clear()
        self.historie.clear()
        self.aufrufe.clear()

    # -- PriceProvider ------------------------------------------------------
    def get_quote(self, instrument):
        self.aufrufe.append(instrument.isin)
        return self.quotes.get(instrument.isin)

    def get_history(self, instrument, von, bis):
        return [(d, w) for d, w in self.historie.get(instrument.isin, []) if von <= d <= bis]


class FakeExchangeRateProvider:
    def __init__(self, name: str = "fake_fx"):
        self.name = name
        self.rates: dict[tuple[str, str], Decimal] = {}
        self.tagesraten: dict[tuple[str, str, date], Decimal] = {}

    def reset(self) -> None:
        self.rates.clear()
        self.tagesraten.clear()

    # -- ExchangeRateProvider ------------------------------------------------
    def get_rate(self, von, nach, am=None):
        if am is not None:
            return self.tagesraten.get((von, nach, am))
        return self.rates.get((von, nach))

    def get_rate_history(self, von, nach, ab, bis):
        return sorted(
            (d, w) for (v, n, d), w in self.tagesraten.items()
            if v == von and n == nach and ab <= d <= bis
        )


# Module singletons so tests configure the instances the registry returns.
fake_aktien = FakePriceProvider("fake_aktien")
fake_hebel = FakePriceProvider("fake_hebel")
fake_fx = FakeExchangeRateProvider("fake_fx")

_registriert = False


def registriere_fakes() -> None:
    """Register the fakes once — proving the 'new provider = registry entry
    only' contract on the way."""
    global _registriert
    if _registriert:
        return
    from infrastructure.kurse import registry as kurs_registry
    from infrastructure.waehrung import registry as fx_registry

    kurs_registry.register(
        ProviderMetadaten(
            name="fake_aktien",
            anzeigename="Fake (Aktien/ETF)",
            kursgruppen=(Kursgruppe.AKTIEN_ETF,),
            benoetigte_credentials=(CredentialFeld("api_key", "API-Key", geheim=True),),
        ),
        lambda creds: fake_aktien,
    )
    kurs_registry.register(
        ProviderMetadaten(
            name="fake_hebel",
            anzeigename="Fake (Hebelprodukte)",
            kursgruppen=(Kursgruppe.HEBELPRODUKT,),
        ),
        lambda creds: fake_hebel,
    )
    fx_registry.register(
        ProviderMetadaten(name="fake_fx", anzeigename="Fake FX", kursgruppen=()),
        lambda creds: fake_fx,
    )
    _registriert = True
