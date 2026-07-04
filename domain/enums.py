"""Domain enums (spec §4). Values are German domain terms by design."""
import enum


class Kategorie(enum.StrEnum):
    """Instrument category (spec §4.2)."""

    AKTIE = "AKTIE"
    ETF = "ETF"
    OPTIONSSCHEIN = "OPTIONSSCHEIN"
    KNOCKOUT = "KNOCKOUT"
    FAKTOR = "FAKTOR"
    SONSTIGES = "SONSTIGES"


class Kursgruppe(enum.StrEnum):
    """Price group, derived from the category; drives provider routing (§4.2/§6.2)."""

    AKTIEN_ETF = "AKTIEN_ETF"
    HEBELPRODUKT = "HEBELPRODUKT"


#: Mapping category -> price group (spec §4.2). SONSTIGES is treated as a
#: stock-like instrument (FMP routing) unless configured otherwise.
KURSGRUPPE_JE_KATEGORIE: dict[Kategorie, Kursgruppe] = {
    Kategorie.AKTIE: Kursgruppe.AKTIEN_ETF,
    Kategorie.ETF: Kursgruppe.AKTIEN_ETF,
    Kategorie.SONSTIGES: Kursgruppe.AKTIEN_ETF,
    Kategorie.OPTIONSSCHEIN: Kursgruppe.HEBELPRODUKT,
    Kategorie.KNOCKOUT: Kursgruppe.HEBELPRODUKT,
    Kategorie.FAKTOR: Kursgruppe.HEBELPRODUKT,
}


class ZahlungTyp(enum.StrEnum):
    """Cash movement type (spec §4.5)."""

    EINZAHLUNG = "EINZAHLUNG"
    AUSZAHLUNG = "AUSZAHLUNG"


class KursQuelle(enum.StrEnum):
    """Price source (spec §4.6)."""

    FMP = "FMP"
    PYTR = "PYTR"
    MANUELL = "MANUELL"


class Zeitraum(enum.StrEnum):
    """Display time range for chart/performance (spec §4.1/§5.5)."""

    SEIT_EROEFFNUNG = "SEIT_EROEFFNUNG"
    M1 = "1M"
    M3 = "3M"
    M6 = "6M"
    YTD = "YTD"
    J1 = "1J"
    BENUTZERDEFINIERT = "BENUTZERDEFINIERT"


class Bezugsbasis(enum.StrEnum):
    """Reference basis for chart/performance (spec §4.1/§5.5)."""

    NUR_WERTPAPIERE = "NUR_WERTPAPIERE"
    INKL_BARBESTAND = "INKL_BARBESTAND"


class Verrechnungsmethode(enum.StrEnum):
    """Cost matching method for realized gains (spec §5.3)."""

    FIFO = "FIFO"
    DURCHSCHNITT = "DURCHSCHNITT"
