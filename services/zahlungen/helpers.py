"""Parsing/validation for cash movements (pure functions, no DB)."""
from __future__ import annotations

from decimal import Decimal

from domain.enums import ZahlungTyp
from utils.parsing import parse_decimal, parse_zeitpunkt


def parse_zahlung(form) -> tuple[dict, list[str]]:
    fields = {
        "typ": (form.get("typ") or "").strip(),
        "betrag": parse_decimal(form.get("betrag")),
        "zeitpunkt": parse_zeitpunkt(form.get("zeitpunkt")),
        "notiz": (form.get("notiz") or "").strip() or None,
    }
    return fields, validate_zahlung(fields)


def validate_zahlung(fields: dict) -> list[str]:
    errors: list[str] = []
    try:
        ZahlungTyp(fields.get("typ") or "")
    except ValueError:
        errors.append("fehler.zahlungstyp_ungueltig")
    betrag = fields.get("betrag")
    if betrag is None or betrag <= Decimal("0"):
        errors.append("fehler.betrag_positiv")
    if fields.get("zeitpunkt") is None:
        errors.append("fehler.zeitpunkt_fehlt")
    return errors
