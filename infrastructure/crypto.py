"""Symmetric encryption of provider credentials at rest (spec §6.6).

Uses Fernet (AES-128-CBC + HMAC) from `cryptography`. The key comes from the
environment (`CREDENTIALS_ENC_KEY`) and is never stored in the database.
Secrets are never logged and never returned to the UI in cleartext.
"""
from __future__ import annotations

import base64
import hashlib
import json


class VerschluesselungFehltError(RuntimeError):
    """Raised when credentials should be stored but no key is configured."""


def _fernet(key: str):
    from cryptography.fernet import Fernet

    if not key:
        raise VerschluesselungFehltError(
            "CREDENTIALS_ENC_KEY is not set — cannot encrypt/decrypt credentials."
        )
    try:
        return Fernet(key.encode())
    except Exception:
        # Allow arbitrary passphrases: derive a valid Fernet key from them.
        abgeleitet = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
        return Fernet(abgeleitet)


def encrypt_credentials(credentials: dict, key: str) -> str:
    """Encrypt a credentials dict to an opaque token for DB storage."""
    return _fernet(key).encrypt(json.dumps(credentials).encode()).decode()


def decrypt_credentials(token: str | None, key: str) -> dict:
    """Decrypt a stored token back to the credentials dict ({} if empty)."""
    if not token:
        return {}
    return json.loads(_fernet(key).decrypt(token.encode()).decode())
