"""Unit tests for parsing/validation helpers and formatters."""
from datetime import date, datetime
from decimal import Decimal

from utils.parsing import parse_datum, parse_decimal, parse_zeitpunkt
from utils.formatters import format_betrag, format_prozent


def test_parse_decimal_deutsch_und_technisch():
    assert parse_decimal("1.234,56") == Decimal("1234.56")
    assert parse_decimal("1234.56") == Decimal("1234.56")
    assert parse_decimal("0,5") == Decimal("0.5")
    assert parse_decimal("") is None
    assert parse_decimal("abc") is None


def test_parse_zeitpunkt_datetime_local_und_datum():
    assert parse_zeitpunkt("2025-03-01T14:30") == datetime(2025, 3, 1, 14, 30)
    assert parse_zeitpunkt("2025-03-01") == datetime(2025, 3, 1, 0, 0)
    assert parse_zeitpunkt("") is None
    assert parse_datum("2025-03-01") == date(2025, 3, 1)


def test_format_deutsch_kaufmaennisch_gerundet():
    # Commercial rounding to 2 decimals only at display time (spec §5).
    assert format_betrag(Decimal("1234.567")) == "1.234,57"
    assert format_betrag(Decimal("-0.005")) == "-0,01"
    assert format_prozent(Decimal("0.1234")) == "12,34 %"
    assert format_betrag(None) == "–"


def test_kauf_und_verkauf_validierung():
    from services.kaeufe import validate_kauf
    from services.verkaeufe import validate_verkauf

    fehler = validate_kauf({"instrument_id": None, "stueck": Decimal("0"),
                            "kaufkurs": None, "kauf_zeitpunkt": None, "spesen": Decimal("-1")})
    assert set(fehler) == {
        "fehler.instrument_fehlt", "fehler.stueck_positiv", "fehler.kurs_positiv",
        "fehler.zeitpunkt_fehlt", "fehler.spesen_negativ",
    }
    fehler = validate_verkauf({"instrument_id": 1, "stueck": Decimal("1"),
                               "verkaufskurs": Decimal("1"),
                               "verkauf_zeitpunkt": datetime(2025, 1, 1),
                               "spesen": Decimal("0"), "steuer": Decimal("-1")})
    assert fehler == ["fehler.steuer_negativ"]


def test_zeitraum_grenzen():
    from domain.enums import Zeitraum
    from services.depots import zeitraum_grenzen

    heute = date(2025, 7, 1)
    eroeffnet = date(2024, 1, 15)
    assert zeitraum_grenzen(Zeitraum.SEIT_EROEFFNUNG, eroeffnet, heute=heute) == (eroeffnet, heute)
    assert zeitraum_grenzen(Zeitraum.YTD, eroeffnet, heute=heute) == (date(2025, 1, 1), heute)
    start, ende = zeitraum_grenzen(Zeitraum.BENUTZERDEFINIERT, eroeffnet,
                                   von="2025-02-01", bis="2025-03-01", heute=heute)
    assert (start, ende) == (date(2025, 2, 1), date(2025, 3, 1))
