"""Parsing/validation for depots + time-range helpers (pure, no DB)."""
from __future__ import annotations

from datetime import date, timedelta

from domain.enums import Bezugsbasis, Zeitraum
from utils.parsing import parse_datum


def parse_depot(form) -> tuple[dict, list[str]]:
    fields = {
        "name": (form.get("name") or "").strip(),
        "eroeffnet_am": parse_datum(form.get("eroeffnet_am")),
        "basiswaehrung": (form.get("basiswaehrung") or "EUR").strip().upper() or "EUR",
        "notiz": (form.get("notiz") or "").strip() or None,
        "default_zeitraum": (form.get("default_zeitraum") or Zeitraum.SEIT_EROEFFNUNG.value),
        "default_bezugsbasis": (
            form.get("default_bezugsbasis") or Bezugsbasis.INKL_BARBESTAND.value
        ),
    }
    return fields, validate_depot(fields)


def validate_depot(fields: dict) -> list[str]:
    errors: list[str] = []
    if not fields.get("name"):
        errors.append("fehler.name_fehlt")
    if fields.get("eroeffnet_am") is None:
        errors.append("fehler.datum_fehlt")
    if len(fields.get("basiswaehrung") or "") != 3:
        errors.append("fehler.waehrung_ungueltig")
    try:
        Zeitraum(fields.get("default_zeitraum") or "")
    except ValueError:
        errors.append("fehler.zeitraum_ungueltig")
    try:
        Bezugsbasis(fields.get("default_bezugsbasis") or "")
    except ValueError:
        errors.append("fehler.bezugsbasis_ungueltig")
    return errors


def zeitraum_grenzen(
    zeitraum: Zeitraum,
    eroeffnet_am: date,
    von: str | None = None,
    bis: str | None = None,
    heute: date | None = None,
) -> tuple[date, date]:
    """Start/end date of the evaluated series for a time range (spec §5.5)."""
    heute = heute or date.today()
    ende = heute
    if zeitraum == Zeitraum.BENUTZERDEFINIERT:
        start = parse_datum(von) or eroeffnet_am
        ende = parse_datum(bis) or heute
        return start, ende
    if zeitraum == Zeitraum.M1:
        return heute - timedelta(days=30), ende
    if zeitraum == Zeitraum.M3:
        return heute - timedelta(days=91), ende
    if zeitraum == Zeitraum.M6:
        return heute - timedelta(days=182), ende
    if zeitraum == Zeitraum.YTD:
        return date(heute.year, 1, 1), ende
    if zeitraum == Zeitraum.J1:
        return heute - timedelta(days=365), ende
    return eroeffnet_am, ende  # SEIT_EROEFFNUNG
