"""Flash helpers: translate i18n error keys before flashing (REQ-I18N)."""
from __future__ import annotations

from flask import flash

from utils.i18n import uebersetze


def flash_errors(schluessel: list[str]) -> None:
    for eintrag in schluessel:
        flash(uebersetze(eintrag), "error")


def flash_ok(schluessel: str, **params) -> None:
    flash(uebersetze(schluessel, **params), "success")
