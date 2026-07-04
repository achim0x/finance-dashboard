"""Shared form-input parsing helpers.

Accept both German ("1.234,56") and technical ("1234.56") decimal notation;
datetimes come from HTML `datetime-local`/`date` inputs. Parsers return None
on invalid input — validation messages are the caller's job (i18n keys).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def parse_decimal(wert: str | None) -> Decimal | None:
    if wert is None:
        return None
    text = wert.strip().replace(" ", "")
    if not text:
        return None
    if "," in text:
        # German notation: dots are thousands separators, comma is decimal.
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_datum(wert: str | None) -> date | None:
    if not wert:
        return None
    try:
        return date.fromisoformat(wert.strip())
    except ValueError:
        return None


def parse_zeitpunkt(wert: str | None) -> datetime | None:
    """Parse an HTML datetime-local ('YYYY-MM-DDTHH:MM[:SS]') or plain date
    input; a plain date becomes midnight (time is optional per spec §4.3)."""
    if not wert:
        return None
    text = wert.strip()
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    d = parse_datum(text)
    if d is not None:
        return datetime(d.year, d.month, d.day)
    return None
