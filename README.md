# Finance Dashboard

A single-user web tool for managing multiple **paper stock portfolios**. It lets
you track investment ideas without real money: buys and sells are recorded
hypothetically and valued continuously against live market prices.

It is a **tracking and simulation tool only** — it places **no real orders**, gives
**no investment advice**, and is **not tax software**.

> The application is not yet implemented. The full functional and technical
> specification lives in [`Musterdepot-SPEC.md`](./Musterdepot-SPEC.md) (German),
> and the house tech stack and conventions come from the internal `web-app` skill.
> The user-facing language of the app is **German**.

## What it does

- **Multiple portfolios** with derived cash balance, positions, and per-portfolio KPIs.
- **All instrument types** — stocks, ETFs, and leveraged products (warrants,
  knock-outs/turbos, factor certificates).
- **Buys, sells, deposits/withdrawals, dividends, and tax entries**, each editable
  after the fact; any change triggers a full recomputation of derived values.
- **FIFO** realized-gain calculation, unrealized performance, dividends and taxes
  tracked as their own KPIs.
- **Live pricing** through pluggable providers, routed by instrument category
  (stocks/ETFs via Financial Modeling Prep; leveraged products via Trade Republic
  through `pytr`). Foreign-currency conversion is likewise pluggable.
- **Value-history chart** with selectable time range and reference basis
  (securities only / incl. cash), plus per-position "since purchase" mini-charts.
- **Named snapshots** to freeze and compare a portfolio's state over time.
- **Exports** to xlsx, CSV, and PDF.
- **Installable PWA** with an offline app shell.
- **MCP server** exposing the service layer for read, reporting, and (later) write tools.

## Tech stack

- **Flask 3.x** with server-rendered **Jinja2** templates (no SPA).
- **3-layer architecture**: `blueprints/` (routes) → `services/` (business logic) →
  `domain/` + `infrastructure/` (repositories, providers).
- **SQLAlchemy 2.0** + Repository pattern + **Alembic** migrations; SQLite (dev) /
  MariaDB (prod). Money and prices are always `Decimal`.
- **pydantic-settings** for configuration; no authentication (single user).
- Vanilla JS + CSS with **Chart.js**; **pytest** with a full test pyramid and
  requirements traceability.

## Getting started

The app has not been scaffolded yet. Once it exists, the intended workflow is:

```bash
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head          # create/upgrade the database schema
python run.py                 # start the local dev server
python run_mcp.py             # start the MCP server
pytest                        # run the test suite
```

Configuration is provided via a `.env` file — see `Musterdepot-SPEC.md` §11 for the
full list of variables (database, provider credentials, encryption key, MCP key).

## Documentation

- [`Musterdepot-SPEC.md`](./Musterdepot-SPEC.md) — full functional & technical spec
  (data model, calculation logic, features, MCP tools, requirements).
- [`CLAUDE.md`](./CLAUDE.md) — orientation for working in this repository.
