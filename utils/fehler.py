"""Shared service-layer exceptions."""
from __future__ import annotations


class ValidierungsFehler(Exception):
    """Validation failure; carries i18n message keys for the UI (REQ-I18N)."""

    def __init__(self, *meldungen: str):
        self.meldungen = list(meldungen)
        super().__init__("; ".join(meldungen))
