"""Parsing/validation for sales (pure functions, no DB)."""
from __future__ import annotations

from decimal import Decimal

from utils.parsing import parse_decimal, parse_zeitpunkt


def parse_verkauf(form) -> tuple[dict, list[str]]:
    fields = {
        "instrument_id": _parse_id(form.get("instrument_id")),
        "stueck": parse_decimal(form.get("stueck")),
        "verkaufskurs": parse_decimal(form.get("verkaufskurs")),
        "verkauf_zeitpunkt": parse_zeitpunkt(form.get("verkauf_zeitpunkt")),
        "spesen": parse_decimal(form.get("spesen")) or Decimal("0"),
        "steuer": parse_decimal(form.get("steuer")) or Decimal("0"),
        "boerse": (form.get("boerse") or "").strip() or None,
    }
    return fields, validate_verkauf(fields)


def _parse_id(wert) -> int | None:
    try:
        return int(wert)
    except (TypeError, ValueError):
        return None


def validate_verkauf(fields: dict) -> list[str]:
    errors: list[str] = []
    if fields.get("instrument_id") is None:
        errors.append("fehler.instrument_fehlt")
    stueck = fields.get("stueck")
    if stueck is None or stueck <= Decimal("0"):
        errors.append("fehler.stueck_positiv")
    kurs = fields.get("verkaufskurs")
    if kurs is None or kurs <= Decimal("0"):
        errors.append("fehler.kurs_positiv")
    if fields.get("verkauf_zeitpunkt") is None:
        errors.append("fehler.zeitpunkt_fehlt")
    for schluessel in ("spesen", "steuer"):
        wert = fields.get(schluessel)
        if wert is not None and wert < Decimal("0"):
            errors.append("fehler.spesen_negativ" if schluessel == "spesen" else "fehler.steuer_negativ")
    return errors
