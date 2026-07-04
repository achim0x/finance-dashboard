"""Shared Flask extension instances.

Kept in a dedicated module to avoid circular imports between `app.py`
and the `blueprints` package.
"""
from flask_wtf import CSRFProtect

csrf = CSRFProtect()
