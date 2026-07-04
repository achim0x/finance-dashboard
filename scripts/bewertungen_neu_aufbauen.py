"""Rebuild the `DepotBewertung` series from a cutoff date (spec §5.6).

Uses exclusively the stored daily closing prices (`Schlusskurs`) plus daily
FX rates — never intraday quotes (REQ-REVAL-CLOSE). Normally triggered
automatically after booking changes; this script exists for manual repairs
and full rebuilds.

Usage: python scripts/bewertungen_neu_aufbauen.py <depot_id> [--ab YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the valuation series of a depot")
    parser.add_argument("depot_id", type=int)
    parser.add_argument("--ab", type=date.fromisoformat, default=None,
                        help="cutoff date (default: depot opening date)")
    args = parser.parse_args()

    from flask import g

    from app import create_app

    app = create_app()
    with app.app_context():
        g.db_session = app.config["SESSION_FACTORY"]()
        try:
            from services.depots import get_depot
            from services.kurse import bewertungen_neu_aufbauen

            depot = get_depot(args.depot_id)
            if depot is None:
                print(f"Depot {args.depot_id} not found.", file=sys.stderr)
                return 1
            ab = args.ab or depot.eroeffnet_am
            bewertungen_neu_aufbauen(depot.id, ab=ab)
            g.db_session.commit()
            print(f"[{depot.name}] valuation series rebuilt from {ab}.")
        finally:
            g.db_session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
