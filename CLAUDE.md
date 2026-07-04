# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

This repo is **greenfield and spec-driven**: no application code and no commits exist yet.
Everything to build is described in two places, which are the sources of truth — read
both before writing code:

1. **`Musterdepot-SPEC.md`** — the domain: what the app is, its data model, and (most
   importantly) the **binding calculation logic**. All prose, domain terms, and DB
   columns are **German**.
2. **`.claude/skills/web-app/`** — the house tech stack, directory layout, layering, and
   conventions. Start at `SKILL.md`, then read the relevant `references/*.md` for the
   part you're implementing. **The Skill defines *how*; the Spec defines *what*.** The
   Spec deliberately does not repeat the Skill — it references it.

The `web-app` Skill auto-activates for this kind of work. Use it; don't reinvent the
structure.

## What is being built

**Musterdepot** — a single-user web tool to manage multiple paper stock portfolios
(hypothetical buys/sells, valued against live market prices). It executes **no real
orders**, gives no advice, and is not tax software.

## Binding project decisions (Spec §2)

These are already decided — do not re-litigate them:

- **No auth / no login** — single user. (Skill supports adding LDAP later; not now.)
- **PWA = yes** — installable, offline app shell (`references/pwa.md`).
- **Config** = `pydantic-settings` (`settings.py`, not `config.py`).
- **Persistence** = SQLAlchemy 2.0 + Repository + Alembic; SQLite (dev) / MariaDB (prod).
- **Money & prices are always `Decimal`, never `float`.** Round (commercial, 2 dp) only at
  display time.
- **Prices are fully abstracted** behind a `PriceProvider` protocol, routed by instrument
  category (`AKTIEN_ETF` → FMP, `HEBELPRODUKT` → pytr/Trade Republic). FX is abstracted
  behind `ExchangeRateProvider` (initial: FMP). New providers = new impl + registry entry,
  with **no changes to the service or UI layer** — this extensibility is a tested requirement.
- Provider credentials are **encrypted at rest** (key `CREDENTIALS_ENC_KEY` from env, never
  the DB), never logged, never returned in cleartext to the UI.

## Architecture (from the Skill)

3-layer, thin routes, deutsch user-facing text:

```
blueprints/ (routes, thin)  →  services/<feature>/ (business logic)  →  domain/ + infrastructure/ (repositories, providers)
                                        │
                                     utils/ (cross-cutting)
```

- **Routes are thin:** parse form → call service → format → render. No SQL or business
  logic in a blueprint.
- **Each service is a package**: `service.py` (DB via repositories) + `helpers.py`
  (pure `parse_*`/`validate_*`/`format_*`) + `__init__.py` (re-exports the public API).
  Import from the package (`from services.kaeufe import ...`), never from `service.py`.
- **No raw SQL in the request path** — all DB access via parametrized repositories.
- Feature blueprints are **depot-scoped** (`/depots/<int:depot_id>/…`) via a
  `get_depot_or_404` helper (analogous to the Skill's `get_project_or_404`).
- **The MCP server imports the service layer directly** (never HTTP to the web app), so it
  reuses the exact same validation and calculation as the UI. `helpers.py` parse/validate
  functions are shared between web forms and MCP write tools.

## The calculation logic is the heart (Spec §5)

Get these right and test them exhaustively — they carry the requirement IDs in Spec §10:

- **FIFO realized gain** on sells (`REQ-CALC-FIFO`), incl. partial sells and fees.
- **Cash ledger** derives the balance (`barbestand`) — it is **never stored**, always
  recomputed from buys/sells/payments/dividends/taxes (`REQ-CASH-LEDGER`).
- **All bookings are editable/deletable** (incl. their timestamp). Any edit triggers a
  **recomputation** of all derived state (balance, FIFO, realized gains, KPI/valuation
  series) — `REQ-EDIT-RECALC`.
- Key KPI identities to enforce as tests:
  `Gesamtgewinn = Realisierter + Unrealisierter Gewinn` and
  `Gesamtergebnis = Gesamtgewinn + Dividenden − Steuern`.
- Historical revaluation uses **only daily closing prices** (`Schlusskurs`), never intraday.

Derived state (balance, open positions, position KPIs, depot KPIs) is computed on the fly;
only `Verkauf.realisierter_gewinn`, the `DepotBewertung` time series, and (frozen)
`DepotSnapshot` are persisted.

## Commands (conventions to follow once code exists)

Per the Skill's `references/testing.md` and `assets/`. No `requirements.txt`/tests exist
yet — create them from the Skill's `assets/` and reference files when scaffolding.

```bash
pip install -r requirements.txt -r requirements-dev.txt
python run.py                 # local dev server (create_app() factory)
python run_mcp.py             # MCP server launcher

pytest                        # full suite
pytest tests/unit             # fast unit tests (formulas/helpers, no DB)
pytest -m requirement         # requirements-traceability tests (REQ-* markers)
pytest tests/requirements/test_req_calc_fifo.py   # a single requirement test

# Integration tests are dual-backend; MariaDB variant is skipped unless reachable:
TEST_MARIADB_URL=mariadb+mariadbconnector://app:app@localhost:3306/app_dev pytest

alembic upgrade head          # apply migrations (revision 0001_initial first)
```

Providers are tested against **fakes** — never hit real FMP/Trade Republic in CI.

## Build order

Spec §14 maps the implementation sequence onto the Skill workflow. Follow it:
scaffold → persistence → config → "Kauf → Bestand" vertical slice → price/FX providers +
setup page → sells/payments/dividends/taxes → edit + recompute → chart range/basis →
overview + snapshots → export → PWA → MCP server → tests → deployment.
