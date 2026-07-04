"""Pure calculation core (spec §5) — no DB access, fully unit-testable."""
from .fifo import (
    OffeneTranche,
    UnzureichenderBestandError,
    Verrechnung,
    offene_tranchen,
    realisierte_gewinne,
    verrechne,
)
from .ledger import barbestand
from .kennzahlen import (
    DepotKennzahlen,
    PositionsKennzahlen,
    depot_kennzahlen,
    positions_kennzahlen,
)

__all__ = [
    "OffeneTranche",
    "UnzureichenderBestandError",
    "Verrechnung",
    "offene_tranchen",
    "realisierte_gewinne",
    "verrechne",
    "barbestand",
    "DepotKennzahlen",
    "PositionsKennzahlen",
    "depot_kennzahlen",
    "positions_kennzahlen",
]
