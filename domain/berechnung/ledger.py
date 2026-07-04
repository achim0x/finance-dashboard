"""Cash ledger (spec §5.2). The cash balance is always derived, never stored.

    barbestand =  Σ deposits
                − Σ withdrawals
                − Σ (buy value incl. fees)
                + Σ (sale proceeds − fees − tax)
                + Σ dividends
                + Σ tax settlements
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from domain.enums import ZahlungTyp

ZERO = Decimal("0")


def barbestand(
    zahlungen=(),
    kaeufe=(),
    verkaeufe=(),
    dividenden=(),
    steuerverrechnungen=(),
    bis: datetime | None = None,
) -> Decimal:
    """Cash balance of a depot, optionally only counting bookings up to `bis`
    (inclusive) — used for the coverage check and historical rebuilds."""

    def _zaehlt(zeitpunkt: datetime) -> bool:
        return bis is None or zeitpunkt <= bis

    saldo = ZERO
    for z in zahlungen:
        if not _zaehlt(z.zeitpunkt):
            continue
        if z.typ == ZahlungTyp.EINZAHLUNG.value:
            saldo += z.betrag
        else:
            saldo -= z.betrag
    for k in kaeufe:
        if _zaehlt(k.kauf_zeitpunkt):
            saldo -= k.stueck * k.kaufkurs + k.spesen
    for v in verkaeufe:
        if _zaehlt(v.verkauf_zeitpunkt):
            saldo += v.stueck * v.verkaufskurs - v.spesen - v.steuer
    for d in dividenden:
        if _zaehlt(d.zeitpunkt):
            saldo += d.betrag
    for s in steuerverrechnungen:
        if _zaehlt(s.zeitpunkt):
            saldo += s.betrag
    return saldo


def min_laufender_saldo(
    zahlungen=(),
    kaeufe=(),
    verkaeufe=(),
    dividenden=(),
    steuerverrechnungen=(),
) -> Decimal:
    """Minimum running cash balance over the whole booking history.

    Used for the coverage check (spec §5.2): a buy/withdrawal — including one
    inserted or edited into the past — is only allowed if the balance never
    dips below zero (unless overdrawing is enabled in the settings).
    """
    ereignisse: list[tuple[datetime, Decimal]] = []
    for z in zahlungen:
        betrag = z.betrag if z.typ == ZahlungTyp.EINZAHLUNG.value else -z.betrag
        ereignisse.append((z.zeitpunkt, betrag))
    for k in kaeufe:
        ereignisse.append((k.kauf_zeitpunkt, -(k.stueck * k.kaufkurs + k.spesen)))
    for v in verkaeufe:
        ereignisse.append(
            (v.verkauf_zeitpunkt, v.stueck * v.verkaufskurs - v.spesen - v.steuer)
        )
    for d in dividenden:
        ereignisse.append((d.zeitpunkt, d.betrag))
    for s in steuerverrechnungen:
        ereignisse.append((s.zeitpunkt, s.betrag))

    ereignisse.sort(key=lambda e: e[0])
    saldo = ZERO
    minimum = ZERO
    for _, betrag in ereignisse:
        saldo += betrag
        minimum = min(minimum, saldo)
    return minimum
