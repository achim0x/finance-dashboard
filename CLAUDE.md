# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Sources of truth

1. **`Musterdepot-SPEC.md`** — the domain spec (German): data model, binding
   calculation logic (§5), provider architecture (§6), requirement IDs (§10).
2. **`.claude/skills/web-app/`** — the house tech stack and conventions.
   The Skill defines *how*; the Spec defines *what*.

Binding decisions (do not re-litigate): no auth (single user), PWA yes,
`pydantic-settings`, SQLAlchemy 2.0 + Repository + Alembic (SQLite dev /
MariaDB prod), money/prices always `Decimal` (round only at display),
providers fully abstracted behind registries, credentials encrypted at rest
(`CREDENTIALS_ENC_KEY` from env), **code comments/docs in English**, UI
multilingual via i18n with German first (REQ-I18N).

## Commands

```bash
. .venv/bin/activate                        # project venv (Python 3.12)
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head                        # create/upgrade schema
python run.py                               # dev server on :5000
python run_mcp.py                           # MCP server (needs MUSTERDEPOT_MCP_KEY)

pytest                                      # full suite (~65 tests, <5s)
pytest tests/unit                           # calc engine + helpers, no DB
pytest tests/requirements                   # one test per REQ-* (writes reports/requirements-matrix.md)
pytest tests/requirements/test_req_calc.py::test_realisierter_gewinn_fifo_mit_teilverkauf_und_spesen
TEST_MARIADB_URL=mariadb+mariadbconnector://app:app@localhost:3306/app_dev pytest  # dual backend

python scripts/kurse_aktualisieren.py       # batch: quotes + daily closes + valuations
python scripts/bewertungen_neu_aufbauen.py <depot_id> [--ab YYYY-MM-DD]
python scripts/icons_generieren.py          # regenerate PWA icons
```

## Architecture

```
blueprints/ (thin, depot-scoped via get_depot_or_404)
   → services/<feature>/ (package: service.py + helpers.py + __init__.py re-export)
      → domain/          (entities, enums, berechnung/ = pure calc core, provider protocols)
      → infrastructure/  (DB provider, sqlalchemy_repos, kurse/ + waehrung/ provider impls + registries, crypto)
utils/ (db session access, i18n, formatters, parsing, flash, context processor)
mcp_server/ (imports services directly — never HTTP; static bearer key)
```

Key invariants:

- **Import services from the package** (`from services.kaeufe import ...`),
  never from `service.py`. No SQL outside `infrastructure/persistence/`.
- **Derived state is never stored**: cash balance, positions and KPIs are
  recomputed from bookings. Persisted derivations: `Verkauf.realisierter_gewinn`,
  the `DepotBewertung` daily series, frozen `DepotSnapshot`.
- **Every booking mutation** calls `services.neuberechnung.nach_buchungsaenderung`
  (recompute realized gains of the instrument + rebuild the valuation series
  from the earliest affected day). Rebuilds use **daily closes only**
  (`Schlusskurs`), never intraday quotes (REQ-REVAL-CLOSE).
- The coverage check (`services.zahlungen.deckung_pruefen`) runs after flush
  and uses the **minimum running balance**, so back-dated bookings can't
  overdraw the account; callers roll back on `ValidierungsFehler`.
- **New price/FX provider** = implementation in `infrastructure/kurse|waehrung/`
  + one `register(...)` call in the matching `registry.py`. Nothing else
  changes (REQ-PRICE-EXT / REQ-FX-PROVIDER are tests).
- **i18n**: no hardcoded UI strings — Jinja uses `_("key")`, Python uses
  `utils.i18n.uebersetze`/flash helpers; keys live in `translations/de.json`.
  Validation errors are i18n keys carried by `ValidierungsFehler`.
- Providers fail soft: return `None`/`[]`, never raise into callers; the UI
  shows the last quote flagged "veraltet". Secrets never appear in logs.

## Tests

Full pyramid + requirements traceability (markers:
`@pytest.mark.requirement("REQ-...")`; matrix written by `tests/conftest.py`).
Providers are tested against **fakes** (`tests/fixtures/fakes.py`) routed via
test settings — never real FMP/pytr in CI (FMP/FX providers make no network
calls when no API key is configured). `tests/fixtures/daten.py` has factories
that go through the real services; use recent dates (`tag(n)`) to keep
valuation rebuilds fast. The `svc` fixture provides a request context with an
open DB session for direct service calls.

## Gotchas

- SQLite stores `Numeric` as float (warning filtered in `pyproject.toml`);
  MariaDB uses real DECIMALs — keep both backends working (skip logic via
  `TEST_MARIADB_URL`).
- `pytr` is intentionally NOT in `requirements.txt` (heavy, unofficial); the
  provider lazy-imports it. Install manually on hosts that use it.
- `bewertungen_neu_aufbauen` runs on every booking change — it preloads all
  data once; don't add per-day queries inside its loop.
- Bump `VERSION` in `static/sw.js` on every release (PWA cache busting).
