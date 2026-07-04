"""Test data factories — thin wrappers around the real services so the same
validation/recalculation runs as in production. Use recent dates by default
to keep the valuation-series rebuild loops short."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

#: Reference day for test bookings (recent past keeps rebuilds fast).
T0 = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) - timedelta(days=14)


def tag(offset: int) -> datetime:
    return T0 + timedelta(days=offset)


def mach_depot(name: str = "Testdepot", eroeffnet_am: date | None = None, **extra):
    from services.depots import depot_anlegen

    return depot_anlegen(
        {
            "name": name,
            "eroeffnet_am": eroeffnet_am or T0.date(),
            "basiswaehrung": extra.pop("basiswaehrung", "EUR"),
            "notiz": None,
            "default_zeitraum": "SEIT_EROEFFNUNG",
            "default_bezugsbasis": "INKL_BARBESTAND",
            **extra,
        }
    )


def mach_instrument(isin: str = "DE0007164600", name: str = "SAP SE",
                    kategorie: str = "AKTIE", waehrung: str = "EUR", **extra):
    from services.instrumente import instrument_anlegen

    return instrument_anlegen(
        {
            "isin": isin,
            "wkn": None,
            "name": name,
            "kategorie": kategorie,
            "waehrung": waehrung,
            "referenzboerse": None,
            "symbol": None,
            "basiswert": None,
            **extra,
        }
    )


def mach_einzahlung(depot_id: int, betrag: str = "10000", zeitpunkt: datetime | None = None):
    from services.zahlungen import zahlung_erfassen

    return zahlung_erfassen(
        depot_id,
        {"typ": "EINZAHLUNG", "betrag": Decimal(betrag), "zeitpunkt": zeitpunkt or tag(0), "notiz": None},
    )


def mach_kauf(depot_id: int, instrument_id: int, stueck: str, kurs: str,
              zeitpunkt: datetime | None = None, spesen: str = "0"):
    from services.kaeufe import kauf_erfassen

    kauf, _ = kauf_erfassen(
        depot_id,
        {
            "instrument_id": instrument_id,
            "stueck": Decimal(stueck),
            "kaufkurs": Decimal(kurs),
            "kauf_zeitpunkt": zeitpunkt or tag(1),
            "spesen": Decimal(spesen),
            "boerse": None,
        },
    )
    return kauf


def mach_verkauf(depot_id: int, instrument_id: int, stueck: str, kurs: str,
                 zeitpunkt: datetime | None = None, spesen: str = "0", steuer: str = "0"):
    from services.verkaeufe import verkauf_erfassen

    return verkauf_erfassen(
        depot_id,
        {
            "instrument_id": instrument_id,
            "stueck": Decimal(stueck),
            "verkaufskurs": Decimal(kurs),
            "verkauf_zeitpunkt": zeitpunkt or tag(5),
            "spesen": Decimal(spesen),
            "steuer": Decimal(steuer),
            "boerse": None,
        },
    )


def mach_dividende(depot_id: int, instrument_id: int, betrag: str,
                   zeitpunkt: datetime | None = None):
    from services.dividenden import dividende_erfassen

    return dividende_erfassen(
        depot_id,
        {
            "instrument_id": instrument_id,
            "betrag": Decimal(betrag),
            "zeitpunkt": zeitpunkt or tag(3),
            "notiz": None,
            "betrag_je_anteil": None,
            "stueck_zum_zeitpunkt": None,
        },
    )


def mach_steuerverrechnung(depot_id: int, betrag: str, zeitpunkt: datetime | None = None):
    from services.steuern import steuerverrechnung_erfassen

    return steuerverrechnung_erfassen(
        depot_id,
        {"betrag": Decimal(betrag), "zeitpunkt": zeitpunkt or tag(6), "notiz": None},
    )
