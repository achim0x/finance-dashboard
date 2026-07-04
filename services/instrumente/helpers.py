"""Parsing/validation for instruments (pure functions, no DB)."""
from __future__ import annotations

from domain.enums import Kategorie


def parse_instrument(form) -> tuple[dict, list[str]]:
    """Parse the instrument form; returns (fields, i18n error keys)."""
    fields = {
        "isin": (form.get("isin") or "").strip().upper(),
        "wkn": (form.get("wkn") or "").strip().upper() or None,
        "name": (form.get("name") or "").strip(),
        "kategorie": (form.get("kategorie") or "").strip(),
        "waehrung": (form.get("waehrung") or "EUR").strip().upper() or "EUR",
        "referenzboerse": (form.get("referenzboerse") or "").strip() or None,
        "symbol": (form.get("symbol") or "").strip() or None,
        "basiswert": (form.get("basiswert") or "").strip() or None,
    }
    return fields, validate_instrument(fields)


def validate_instrument(fields: dict) -> list[str]:
    errors: list[str] = []
    isin = fields.get("isin") or ""
    if len(isin) != 12 or not isin[:2].isalpha() or not isin.isalnum():
        errors.append("fehler.isin_ungueltig")
    if not fields.get("name"):
        errors.append("fehler.name_fehlt")
    try:
        Kategorie(fields.get("kategorie") or "")
    except ValueError:
        errors.append("fehler.kategorie_ungueltig")
    if len(fields.get("waehrung") or "") != 3:
        errors.append("fehler.waehrung_ungueltig")
    return errors
