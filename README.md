# Finance Dashboard

A single-user web tool for managing multiple **paper stock portfolios**
("Musterdepots"). Buys and sells are recorded hypothetically and valued
continuously against live market prices. It is a **tracking and simulation
tool only** — it places **no real orders**, gives **no investment advice**,
and is **not tax software**. The UI is multilingual (German is the first
implemented language); the domain language and DB columns are German.

The full functional specification lives in
[`Musterdepot-SPEC.md`](./Musterdepot-SPEC.md) (German, binding).

## Overview

- **Multiple depots** with an overview dashboard (KPIs per depot + totals) and
  a per-depot dashboard: KPI tiles (total value, securities, cash, total gain,
  realized/unrealized gain, dividends, taxes, net result) and a value-history
  chart with selectable **time range** and **reference basis** (securities
  only / incl. cash).
- **All instrument types**: stocks, ETFs, and leveraged products (warrants,
  knock-outs/turbos, factor certificates).
- **Bookings**: buys (tranches), partial/full sells with **FIFO** realized
  gains (average-cost optional), deposits/withdrawals, dividends, sale taxes
  and tax settlements. The cash balance is **always derived** from the
  ledger, never stored. Every booking — including its timestamp — can be
  edited or deleted later; all derived state is recomputed automatically.
- **Pricing** through pluggable providers routed by instrument category:
  Financial Modeling Prep (stocks/ETFs) and Trade Republic via `pytr`
  (leveraged products), plus a manual-quote fallback. FX conversion is
  likewise pluggable (initial provider: FMP). Provider failures never break
  the UI — the last known quote stays visible, flagged as stale.
- **Setup page**: choose provider per price group, store credentials
  (encrypted at rest), set the polling interval, run the Trade Republic 2FA
  login, and run a per-depot **availability test** that writes nothing.
- **Mini charts** ("since purchase") from daily closing prices, with optional
  historical **backfill** when a buy is recorded with a past date.
- **Snapshots**: freeze named depot states and compare two snapshots.
- **Exports**: xlsx (openpyxl), CSV, and a printable view for PDF (print CSS).
- **PWA**: installable, offline app shell with fallback page.
- **MCP server** exposing the same service layer to AI clients.

Architecture: Flask 3 + Jinja2 (server-rendered, no SPA), a pragmatic
3-layer structure, SQLAlchemy 2.0 + repository pattern + Alembic.

## Quick start (local)

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env            # fill in: SECRET_KEY, CREDENTIALS_ENC_KEY, API keys
alembic upgrade head            # create the schema
python run.py                   # dev server on :5000
```

Then open <http://127.0.0.1:5000/>, create a depot, record a deposit and the
first buy. Configure price providers under **Kurs-Setup**.

The daily quote/valuation job runs outside the request path:

```bash
python scripts/kurse_aktualisieren.py        # quotes + daily closes + valuations
python scripts/bewertungen_neu_aufbauen.py 1 # rebuild a depot's valuation series
```

Schedule `kurse_aktualisieren.py` via cron/systemd timer/NSSM; a run after
market close finalizes the day's closing prices.

## Configuration

`pydantic-settings` (`settings.py`); all values come from the environment /
`.env`. Provider routing/credentials/intervals set here are only
bootstrap/fallback defaults — the authoritative runtime configuration lives
in the DB and is maintained through the setup page.

| Variable | Required | Purpose |
|---|---|---|
| `DB_BACKEND` / `DB_URL` | yes | `sqlite` (dev) or `mariadb` (prod) + SQLAlchemy URL |
| `SECRET_KEY` | yes (prod) | Flask session key — 32 random bytes, never the placeholder |
| `CREDENTIALS_ENC_KEY` | yes* | Encryption key for provider credentials stored in the DB (never in the DB itself). *Required to save credentials on the setup page. |
| `DEFAULT_SPRACHE` | no | Default UI language (default `de`) |
| `BARBESTAND_UEBERZIEHEN_ERLAUBEN` | no | Allow negative cash (default `false`) |
| `VERRECHNUNGSMETHODE` | no | `FIFO` (default) or `DURCHSCHNITT` |
| `PROVIDER_AKTIEN_ETF` / `PROVIDER_HEBELPRODUKT` | no | Bootstrap provider routing (default `fmp` / `pytr`) |
| `KURS_CACHE_TTL` | no | Quote cache TTL in seconds (default 60) |
| `FMP_API_KEY` | no | FMP key (quotes for stocks/ETFs and FX) |
| `FX_PROVIDER` | no | Bootstrap FX provider (default `fmp`) |
| `PYTR_PHONE_NO` / `PYTR_PIN` / `PYTR_KEYFILE` | no | Trade Republic bootstrap credentials + session keyfile path (secrets — never logged) |
| `MUSTERDEPOT_MCP_KEY` | for MCP | Static bearer key for the MCP server (no key = server refuses everything) |
| `MUSTERDEPOT_MCP_HOST` / `MUSTERDEPOT_MCP_PORT` | no | MCP bind address (default `127.0.0.1:8000`) |

## Architecture

```
blueprints/  (thin routes)  →  services/<feature>/  (business logic)  →  domain/ + infrastructure/
                                        │                                  (entities, calc engine,
                                     utils/                                 repositories, providers)
```

- **Routes are thin**: parse form → call service → render. Feature blueprints
  are depot-scoped (`/depots/<id>/…`) via `get_depot_or_404`.
- **Each service is a package**: `service.py` (DB via repositories) +
  `helpers.py` (pure `parse_*`/`validate_*`) + `__init__.py` (public API).
- **Calculation core** (`domain/berechnung/`): pure, DB-free functions for
  FIFO matching, the cash ledger and all KPIs — exhaustively unit-tested.
- **Provider registries** (`infrastructure/kurse|waehrung/registry.py`):
  adding a price/FX provider = new implementation + one registry entry;
  services and UI stay untouched (a tested requirement).
- **i18n**: all UI strings go through `utils/i18n.py` + `translations/<lang>.json`;
  adding a language = adding one JSON file (German fallback).
- Only `Verkauf.realisierter_gewinn`, the daily `DepotBewertung` series and
  frozen `DepotSnapshot` rows are persisted; every other figure is derived on
  the fly. Historical revaluation uses **daily closing prices only**.

See `Musterdepot-SPEC.md` for the binding calculation rules and `docs/` for
guides.

## Database & migrations

SQLite for development/tests, MariaDB/MySQL for production (install a driver,
e.g. `mariadb` or `PyMySQL`, and set `DB_BACKEND=mariadb`).

```bash
alembic upgrade head                                  # apply migrations
alembic revision --autogenerate -m "my change"        # new revision (review the diff!)
```

Migrations are forward-only; back up the DB before production upgrades.

## PWA

Installable as an app (manifest + service worker + icons; regenerate icons
with `python scripts/icons_generieren.py`). The app shell and static assets
are cached; HTML pages are network-first with an offline fallback page.
**Limits:** the app is server-rendered and data-driven — dynamic pages need a
connection; installation and the app shell work offline. HTTPS is required
in production (localhost works for development). Bump `VERSION` in
`static/sw.js` on every release.

## MCP server

Exposes the depot data and business logic to AI clients (Claude Desktop,
Claude Code) via the [Model Context Protocol](https://modelcontextprotocol.io)
— streamable HTTP on `/mcp`.

- **Read tools**: `whoami`, `list_depots`, `uebersicht`, `get_depot`,
  `list_positionen`, `list_verkaeufe`, `list_transaktionen`,
  `list_dividenden`, `list_snapshots`, `get_kurs`, `get_wechselkurs`.
- **Reporting**: `depot_zusammenfassung`, `gewichtung`, `performance`,
  `snapshot_vergleich`, `kurse_testen`.
- **Writes**: `kauf_erfassen`, `verkauf_erfassen`, `einzahlung`,
  `auszahlung`, `dividende_erfassen`, `steuerverrechnung_erfassen`,
  `buchung_bearbeiten`, `buchung_loeschen`, `snapshot_erstellen`,
  `instrument_anlegen`, `kurse_aktualisieren` — all writes reuse the exact
  `parse_*`/`validate_*` helpers of the web forms.
- **Out of scope**: creating/deleting depots, editing snapshots, changing
  provider credentials.
- **Auth**: single-user app — one **static bearer key** from
  `MUSTERDEPOT_MCP_KEY` (constant-time compared, fail-closed when unset).
  Run only behind TLS; default bind is `127.0.0.1`.
- **Connectivity**: the server imports the service layer directly (same
  validation/calculation as the UI) and uses the same `.env`/DB — it never
  calls the web app over HTTP.

```bash
python run_mcp.py --host 127.0.0.1 --port 8000
```

Client configuration (Claude Code example):

```json
{
  "mcpServers": {
    "musterdepot": {
      "type": "http",
      "url": "https://<host>/mcp",
      "headers": { "Authorization": "Bearer <MUSTERDEPOT_MCP_KEY>" }
    }
  }
}
```

Call `whoami` first to verify the connection.

## Tests

```bash
pytest                     # full suite
pytest tests/unit          # fast unit tests (calc engine, helpers — no DB)
pytest tests/integration   # services + web through a real DB
pytest tests/requirements  # one test per REQ-* requirement (spec §10)
pytest -m requirement      # only requirement-marked tests
```

Integration/requirements tests run against SQLite always and against MariaDB
when reachable:

```bash
TEST_MARIADB_URL=mariadb+mariadbconnector://app:app@localhost:3306/app_dev pytest
```

Price/FX providers are tested against **fakes** — CI never calls FMP or
Trade Republic. Each run writes the requirements-traceability matrix to
`reports/requirements-matrix.md`.

## Deployment

WSGI behind a TLS reverse proxy; internal services bind to `127.0.0.1`.

- **Linux**: Apache `mod_wsgi` pointing at `wsgi.py` (or waitress/gunicorn
  behind nginx). Schedule `scripts/kurse_aktualisieren.py` with a systemd
  timer or cron.
- **Windows**: nginx + waitress (`waitress-serve --listen=127.0.0.1:8080 wsgi:app`)
  as an NSSM service; schedule the quote job with Task Scheduler/NSSM.
- GitLab CI runs the tests on every push; the staging deploy job follows the
  in-house `webtools_common` pattern (`.gitlab-ci.yml`).

Update ritual: back up the DB → `git pull` → `pip install -r requirements.txt`
→ `alembic upgrade head` → restart the service → bump `VERSION` in `sw.js`.

## Project status / open points

- **No authentication** by design (single user). Hardening point: add the
  skill's LDAP/session layer before any multi-user exposure. Do not expose
  the app or MCP port without TLS and network-level protection.
- **pytr / Trade Republic** is an unofficial API: ToS questions, possible
  breaking changes, unknown session lifetime — re-login via the setup page;
  manual quote entry exists as the fallback.
- **FMP free tier** covers US/OTC listings; native German exchanges (`*.DE`)
  require FMP Premium (HTTP 402) — an operations/cost decision.
- **Range performance** is a naive value difference; cashflows in the range
  distort it (shown as a hint). A time-weighted return is a planned
  extension, as are benchmarks, price alerts and CSV/broker import.
- Historical FX depth for rebuilds and the history depth for leveraged
  products remain open (spec §13).
