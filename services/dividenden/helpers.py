"""Parsing/validation for dividends (pure functions, no DB)."""
from __future__ import annotations

from decimal import Decimal

from utils.parsing import parse_decimal, parse_zeitpunkt


def parse_dividende(form) -> tuple[dict, list[str]]:
    fields = {
        "instrument_id": _parse_id(form.get("instrument_id")),
        "betrag": parse_decimal(form.get("betrag")),
        "zeitpunkt": parse_zeitpunkt(form.get("zeitpunkt")),
        "notiz": (form.get("notiz") or "").strip() or None,
        "betrag_je_anteil": parse_decimal(form.get("betrag_je_anteil")),
        "stueck_zum_zeitpunkt": parse_decimal(form.get("stueck_zum_zeitpunkt")),
    }
    return fields, validate_dividende(fields)


def _parse_id(wert) -> int | None:
    try:
        return int(wert)
    except (TypeError, ValueError):
        return None


def validate_dividende(fields: dict) -> list[str]:
    errors: list[str] = []
    if fields.get("instrument_id") is None:
        errors.append("fehler.instrument_fehlt")
    betrag = fields.get("betrag")
    if betrag is None or betrag <= Decimal("0"):
        errors.append("fehler.betrag_positiv")
    if fields.get("zeitpunkt") is None:
        errors.append("fehler.zeitpunkt_fehlt")
    return errors
