"""Parsing/validation for buys (pure functions, no DB)."""
from __future__ import annotations

from decimal import Decimal

from utils.parsing import parse_decimal, parse_zeitpunkt


def parse_kauf(form) -> tuple[dict, list[str]]:
    fields = {
        "instrument_id": _parse_id(form.get("instrument_id")),
        "stueck": parse_decimal(form.get("stueck")),
        "kaufkurs": parse_decimal(form.get("kaufkurs")),
        "kauf_zeitpunkt": parse_zeitpunkt(form.get("kauf_zeitpunkt")),
        "spesen": parse_decimal(form.get("spesen")) or Decimal("0"),
        "boerse": (form.get("boerse") or "").strip() or None,
    }
    return fields, validate_kauf(fields)


def _parse_id(wert) -> int | None:
    try:
        return int(wert)
    except (TypeError, ValueError):
        return None


def validate_kauf(fields: dict) -> list[str]:
    errors: list[str] = []
    if fields.get("instrument_id") is None:
        errors.append("fehler.instrument_fehlt")
    stueck = fields.get("stueck")
    if stueck is None or stueck <= Decimal("0"):
        errors.append("fehler.stueck_positiv")
    kurs = fields.get("kaufkurs")
    if kurs is None or kurs <= Decimal("0"):
        errors.append("fehler.kurs_positiv")
    if fields.get("kauf_zeitpunkt") is None:
        errors.append("fehler.zeitpunkt_fehlt")
    spesen = fields.get("spesen")
    if spesen is not None and spesen < Decimal("0"):
        errors.append("fehler.spesen_negativ")
    return errors
