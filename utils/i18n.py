"""Lightweight i18n mechanism (REQ-I18N).

The app is multilingual by design; German is the first fully implemented
language. All user-facing strings go through `uebersetze()` / the Jinja
global `_()` — no hardcoded UI strings. Adding a language means adding one
JSON file under `translations/` (e.g. `en.json`); no code changes.

Translation files are flat-or-nested JSON; nested keys are flattened with
dots ("nav.uebersicht"). Lookup order: selected language -> German -> the
key itself (visible marker for missing translations).
"""
from __future__ import annotations

import json
from pathlib import Path

from flask import current_app, session

FALLBACK_SPRACHE = "de"
_VERZEICHNIS = Path(__file__).resolve().parent.parent / "translations"

_cache: dict[str, dict[str, str]] = {}


def _flach(daten: dict, praefix: str = "") -> dict[str, str]:
    flach: dict[str, str] = {}
    for schluessel, wert in daten.items():
        voll = f"{praefix}.{schluessel}" if praefix else schluessel
        if isinstance(wert, dict):
            flach.update(_flach(wert, voll))
        else:
            flach[voll] = str(wert)
    return flach


def _laden(sprache: str) -> dict[str, str]:
    if sprache not in _cache:
        pfad = _VERZEICHNIS / f"{sprache}.json"
        if pfad.exists():
            _cache[sprache] = _flach(json.loads(pfad.read_text(encoding="utf-8")))
        else:
            _cache[sprache] = {}
    return _cache[sprache]


def cache_leeren() -> None:
    """For tests and after adding translation files at runtime."""
    _cache.clear()


def verfuegbare_sprachen() -> list[str]:
    """Languages discovered from the translations directory."""
    return sorted(p.stem for p in _VERZEICHNIS.glob("*.json"))


def aktuelle_sprache() -> str:
    standard = FALLBACK_SPRACHE
    try:
        standard = current_app.config["SETTINGS"].default_sprache
    except (RuntimeError, KeyError):
        pass
    try:
        return session.get("sprache", standard)
    except RuntimeError:  # outside request context (scripts, MCP)
        return standard


def uebersetze(schluessel: str, sprache: str | None = None, **params) -> str:
    sprache = sprache or aktuelle_sprache()
    text = _laden(sprache).get(schluessel)
    if text is None and sprache != FALLBACK_SPRACHE:
        text = _laden(FALLBACK_SPRACHE).get(schluessel)
    if text is None:
        return schluessel
    try:
        return text.format(**params) if params else text
    except (KeyError, IndexError):
        return text


def register_i18n(app) -> None:
    app.jinja_env.globals["_"] = lambda schluessel, **params: uebersetze(schluessel, **params)

    @app.context_processor
    def _sprache():
        return {
            "aktuelle_sprache": aktuelle_sprache(),
            "verfuegbare_sprachen": verfuegbare_sprachen(),
        }
