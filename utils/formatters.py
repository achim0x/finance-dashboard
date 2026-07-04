"""Display formatting. Money/prices are Decimal end-to-end; commercial
rounding to 2 decimal places happens HERE and only here (spec §2/§5).
German number format (1.234,56) as the default UI locale.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal


def _de_zahl(wert: Decimal, stellen: int = 2) -> str:
    quant = Decimal(1).scaleb(-stellen)
    gerundet = wert.quantize(quant, rounding=ROUND_HALF_UP)
    text = f"{gerundet:,.{stellen}f}"  # 1,234.56
    return text.replace(",", " ").replace(".", ",").replace(" ", ".")


def format_betrag(wert: Decimal | None, stellen: int = 2) -> str:
    if wert is None:
        return "–"
    return _de_zahl(Decimal(wert), stellen)


def format_prozent(wert: Decimal | None, stellen: int = 2) -> str:
    """Input is a fraction (0.05 = 5 %)."""
    if wert is None:
        return "–"
    return _de_zahl(Decimal(wert) * 100, stellen) + " %"


def format_datum(wert: date | datetime | None) -> str:
    if wert is None:
        return "–"
    return wert.strftime("%d.%m.%Y")


def format_zeitpunkt(wert: datetime | None) -> str:
    if wert is None:
        return "–"
    if (wert.hour, wert.minute, wert.second) == (0, 0, 0):
        return wert.strftime("%d.%m.%Y")
    return wert.strftime("%d.%m.%Y %H:%M")


def vorzeichen_klasse(wert: Decimal | None) -> str:
    """CSS class for gain/loss coloring."""
    if wert is None or wert == 0:
        return "neutral"
    return "positiv" if wert > 0 else "negativ"


def register_filters(app) -> None:
    app.template_filter("betrag")(format_betrag)
    app.template_filter("prozent")(format_prozent)
    app.template_filter("datum")(format_datum)
    app.template_filter("zeitpunkt")(format_zeitpunkt)
    app.jinja_env.globals["vorzeichen_klasse"] = vorzeichen_klasse
