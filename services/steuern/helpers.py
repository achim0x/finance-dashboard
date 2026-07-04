"""Parsing/validation for tax settlements (pure functions, no DB)."""
from __future__ import annotations

from decimal import Decimal

from utils.parsing import parse_decimal, parse_zeitpunkt


def parse_steuerverrechnung(form) -> tuple[dict, list[str]]:
    fields = {
        "betrag": parse_decimal(form.get("betrag")),
        "zeitpunkt": parse_zeitpunkt(form.get("zeitpunkt")),
        "notiz": (form.get("notiz") or "").strip() or None,
    }
    return fields, validate_steuerverrechnung(fields)


def validate_steuerverrechnung(fields: dict) -> list[str]:
    errors: list[str] = []
    betrag = fields.get("betrag")
    if betrag is None or betrag <= Decimal("0"):
        errors.append("fehler.betrag_positiv")
    if fields.get("zeitpunkt") is None:
        errors.append("fehler.zeitpunkt_fehlt")
    return errors
