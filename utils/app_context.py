"""Template context processor: current depot (session), depot switcher list
and the stale-quotes badge (skill's count_incomplete convention).
"""
from __future__ import annotations

from flask import session


def register_context(app) -> None:
    @app.context_processor
    def _kontext():
        from services.depots import alle_depots, get_depot  # lazy: avoid cycle
        from services.kurse import veraltete_kurse  # lazy: avoid cycle

        depot = None
        badge = 0
        depot_id = session.get("aktuelles_depot_id")
        try:
            if depot_id is not None:
                depot = get_depot(depot_id)
            depots = alle_depots()
            if depot is not None:
                badge = veraltete_kurse(depot.id)
        except Exception:  # noqa: BLE001 — context must never break rendering
            depots = []
        return {
            "aktuelles_depot": depot,
            "alle_depots_nav": depots,
            "veraltete_kurse_badge": badge,
        }
