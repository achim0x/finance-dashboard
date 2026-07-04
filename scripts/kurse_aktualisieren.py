"""Batch job (spec §6.5): refresh quotes for all instruments in open
positions, write the daily closing price per instrument and today's
`DepotBewertung` per depot.

Run periodically via cron/systemd timer/NSSM (see docs/deployment). The
polling interval per price group is configured on the setup page; schedule
this script at least as often as the smallest configured interval. A run
after market close finalizes today's `Schlusskurs` (last run wins — the
upsert is idempotent per (instrument, day)).

Usage: python scripts/kurse_aktualisieren.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from flask import g

    from app import create_app

    app = create_app()
    with app.app_context():
        g.db_session = app.config["SESSION_FACTORY"]()
        try:
            from services.depots import alle_depots
            from services.kurse import bewertung_schreiben, depot_aktualisieren, schlusskurs_schreiben

            for depot in alle_depots():
                ergebnisse = depot_aktualisieren(depot.id)
                for ergebnis in ergebnisse:
                    status = ergebnis.status
                    print(f"[{depot.name}] {ergebnis.instrument.isin}: {status}")
                    if status == "OK" and ergebnis.kurs is not None:
                        # Today's close = the last fetched quote of the day.
                        schlusskurs_schreiben(
                            ergebnis.instrument.id,
                            date.today(),
                            ergebnis.kurs,
                            ergebnis.quelle or "MANUELL",
                        )
                bewertung_schreiben(depot.id)
                g.db_session.commit()
                print(f"[{depot.name}] Bewertung für {date.today()} geschrieben.")
        finally:
            g.db_session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
