"""Transactions tab: the chronological ledger across all booking types
(spec §7). Every row links back to its edit form.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from domain.enums import ZahlungTyp
from utils.db import current_session
from infrastructure.persistence.sqlalchemy_repos import (
    SqlAlchemyDividendeRepository,
    SqlAlchemyKaufRepository,
    SqlAlchemySteuerverrechnungRepository,
    SqlAlchemyVerkaufRepository,
    SqlAlchemyZahlungRepository,
)


@dataclass
class LedgerZeile:
    typ: str            # i18n key suffix: kauf|verkauf|einzahlung|auszahlung|dividende|steuerverrechnung
    zeitpunkt: datetime
    betrag: Decimal     # signed cash effect (spec §5.2)
    id: int             # booking id (for the edit link)
    instrument_name: str | None = None
    details: str | None = None


def ledger(depot_id: int) -> list[LedgerZeile]:
    s = current_session()
    zeilen: list[LedgerZeile] = []

    for k in SqlAlchemyKaufRepository(s).list_for_depot(depot_id):
        zeilen.append(
            LedgerZeile(
                typ="kauf",
                zeitpunkt=k.kauf_zeitpunkt,
                betrag=-(k.stueck * k.kaufkurs + k.spesen),
                id=k.id,
                instrument_name=k.instrument.name if k.instrument else None,
                details=f"{k.stueck} × {k.kaufkurs}",
            )
        )
    for v in SqlAlchemyVerkaufRepository(s).list_for_depot(depot_id):
        zeilen.append(
            LedgerZeile(
                typ="verkauf",
                zeitpunkt=v.verkauf_zeitpunkt,
                betrag=v.stueck * v.verkaufskurs - v.spesen - v.steuer,
                id=v.id,
                instrument_name=v.instrument.name if v.instrument else None,
                details=f"{v.stueck} × {v.verkaufskurs}",
            )
        )
    for z in SqlAlchemyZahlungRepository(s).list_for_depot(depot_id):
        einzahlung = z.typ == ZahlungTyp.EINZAHLUNG.value
        zeilen.append(
            LedgerZeile(
                typ="einzahlung" if einzahlung else "auszahlung",
                zeitpunkt=z.zeitpunkt,
                betrag=z.betrag if einzahlung else -z.betrag,
                id=z.id,
                details=z.notiz,
            )
        )
    for d in SqlAlchemyDividendeRepository(s).list_for_depot(depot_id):
        zeilen.append(
            LedgerZeile(
                typ="dividende",
                zeitpunkt=d.zeitpunkt,
                betrag=d.betrag,
                id=d.id,
                instrument_name=d.instrument.name if d.instrument else None,
                details=d.notiz,
            )
        )
    for sv in SqlAlchemySteuerverrechnungRepository(s).list_for_depot(depot_id):
        zeilen.append(
            LedgerZeile(
                typ="steuerverrechnung",
                zeitpunkt=sv.zeitpunkt,
                betrag=sv.betrag,
                id=sv.id,
                details=sv.notiz,
            )
        )

    zeilen.sort(key=lambda z: z.zeitpunkt)
    return zeilen
