# Data Derby

[![gates](https://github.com/Vr3n/dataderby/actions/workflows/ci.yml/badge.svg)](https://github.com/Vr3n/dataderby/actions/workflows/ci.yml)

Football competition data pipeline. Two independent slices: the 2026/27 fixture
calendar for twelve competitions (SQLite, orchestrated by Dagster), and the
WhoScored team-statistics pipeline (DuckDB, append-only snapshots).

## Sources

The two datasets come from different websites, on purpose:

| Data | Source | Why |
|---|---|---|
| Fixture calendar | [fixturedownload.com](https://fixturedownload.com) | Plain CSV exports, no login, one file per competition |
| Team season stats (planned) | WhoScored | Per-team measure tables, not available as a bulk export |

The WhoScored discovery notes and decision deck are in
[`docs/research/whoscored-discovery-report.md`](docs/research/whoscored-discovery-report.md) and
[`docs/slides/whoscored-discovery-report.html`](docs/slides/whoscored-discovery-report.html). The
decisions and the cadence evidence are in
[`docs/research/whoscored-decisions.md`](docs/research/whoscored-decisions.md) and
[`docs/research/whoscored-cadence.md`](docs/research/whoscored-cadence.md).

The final v1 plan and its 47-slide deck are in
[`plans/v1-implementation-plan.md`](plans/v1-implementation-plan.md) and
[`docs/slides/dataderby-v1-plan.html`](docs/slides/dataderby-v1-plan.html). The executable build
order and test matrix are in [`plans/v1-build-plan.md`](plans/v1-build-plan.md).

The P0–P7 production-readiness review is a beginner-oriented animated deck in
[`docs/slides/production-readiness-slides.html`](docs/slides/production-readiness-slides.html):
one concept per slide, each with a plain-language explanation, a source, and a
recommendation. Open it in a browser; it works offline.

Documentation is organised by kind — decisions, reports, decks, research, design,
and archived reference. Start at [`docs/README.md`](docs/README.md); the layout
and its Databricks/Azure mapping are in
[`docs/design/project-structure.md`](docs/design/project-structure.md).

They are independent inputs. The calendar is used to decide *when* to scrape team
stats, not to join against them: the fixture site publishes display names
(`Spurs`, `Man Utd`), while WhoScored keys teams on numeric `teamId`. Nothing in v1
joins the two by team name, and the `fixtures` table does not claim to share a
vocabulary with the team-stats tables.

The provenance of each competition row is stored alongside it
(`competitions.fixturedownload_slug` and `competitions.fixturedownload_url`), so the
export a fixture came from is always recoverable from the database.

## Quick start

```powershell
uv sync
uv run python main.py refresh         # download and store all fixtures
uv run python main.py next --days 7   # what is on in the next week (IST)
.\scripts\dagster.ps1                 # Dagster UI at http://127.0.0.1:3000
```

## WhoScored pipeline

The team-statistics pipeline has its own entry point. It is separate from the
fixture commands above, and `main.py` still belongs to the fixture CLI:

```powershell
uv run dataderby stages list
uv run dataderby probe --stage epl-2026-2027          # one feed, no writes
uv run dataderby run --stage epl-2026-2027 --dry-run  # validate in memory
uv run dataderby run --stage epl-2026-2027
uv run dataderby freshness
uv run dataderby verify
```

Exit codes: `0` ok, `2` fetch failed, `3` blocked, `4` config, `5` locked,
`6` internal or verification mismatch. The phase report is
[`docs/reports/p8-cli-operations.md`](docs/reports/p8-cli-operations.md) and the
one-page summary is [`docs/reports/p8-summary.md`](docs/reports/p8-summary.md).

The schema is applied through a checksummed ledger (`schema_migration`), so an
applied SQL file is never re-run and never silently edited.

## Data contract

What the WhoScored pipeline's data can and cannot answer:

| It can | It cannot |
|---|---|
| cumulative season measures per team (20–36 teams per snapshot) | per-match attribution — there is no match grain, only snapshots |
| league-table state per snapshot: rank, points, form, W/D/L | event data — no goals, cards, or substitutions as events |
| when something was observed (`observed_at`) and accepted (`accepted_at`) | expected goals (xG) or any model output |
| whether the table moved between snapshots (`v_snapshot_delta`) | why a deduction was applied — only the gap is recorded |
| which deductions exist (`v_points_adjustments`) | future fixtures — the fixture calendar is a separate slice |

Snapshots land on the schedule in [`docs/design/runbook.md`](docs/design/runbook.md):
daily at 06:00 IST plus provisional post-match sweeps. A snapshot is one
observation, never a live table.

## Source use

WhoScored data is captured politely (1.2 s pacing, per-run request budget,
`Retry-After` honoured) and kept as raw evidence, not republished. The licence
posture, the robots record, and what may and may not leave the pipeline are in
[`docs/adr/0006-source-use.md`](docs/adr/0006-source-use.md). Review that ADR
before any derived data is shared or published.

## Layout

```
config/dagster.yaml        Dagster instance config (SQLite)
src/dataderby/fixtures/    competitions, download, parse, store, assets, CLI
src/dataderby/             WhoScored pipeline: page, fetch, raw, parse, publish, cli
sql/                       001 schema, 002 assertions, 003 views
tests/                     parser, storage, service, CLI, downloader, pipeline
data/                      ignored: raw CSVs, SQLite databases, Dagster history
```

## Storage

Two SQLite databases, deliberately separate:

| Database | Holds | Why |
|---|---|---|
| `data/fixtures.sqlite3` | `competitions`, `fixtures`, views | domain data |
| `data/dagster/history/` | Dagster runs, events, schedules | orchestrator state |

Dagster's instance database is its own bookkeeping. Domain tables do not belong in it:
Dagster migrates that schema between versions, and mixing the two makes both harder to
reason about.

The calendar tables:

- `competitions` — one row per competition, with the source row counts.
- `fixtures` — one row per match, keyed on competition + season + round + teams.
- `v_upcoming_fixtures` — matches with a kick-off in the future.

## Timezone

fixturedownload.com times are fetched as **UTC** and converted to **Asia/Kolkata** with `zoneinfo`.
Both are stored: `kickoff_utc` for ordering and joining, `kickoff_ist` for display.

The WhoScored snapshot tables take a different approach, decided in
[`docs/adr/0008-timestamptz.md`](docs/adr/0008-timestamptz.md): every timestamp is
`TIMESTAMP WITH TIME ZONE`, so one column holds one instant. Local time is rendered
at read time by [`v_snapshot_clock`](sql/003_views.sql), which shows UTC and IST side
by side. There is no stored `observed_at_ist` column, and a different zone is a
query-level expression rather than a schema change.

The fixture table keeps its two columns. Migrating it is not part of v1.

The source also offers an `IndiaStandardTime` export, but it is not used. Measured on
19 Oct 2026: it is missing for five of twelve competitions, and where present it is wrong
for 56 of 380 Premier League rows (match 46, 20/09 13:00 UTC, exported as 19/09 19:30).
The UTC export is the reliable one.

## Dagster

`scripts/dagster.ps1` sets `DAGSTER_HOME`, points the instance at
`data/dagster/history` (an absolute path is required — a relative one resolves against
the working directory), and starts `dagster dev`.

Assets:

- `raw_fixture_csvs` — downloads the twelve UTC exports into `data/fixtures/raw/`.
- `fixtures_table` — parses them into SQLite.

Checks (all blocking): every kick-off carries `+05:30`, stored counts match the source,
match numbers are unique per competition, and all twelve competitions are present.

The job `fixture_refresh_job` runs daily at 06:00 Asia/Kolkata via
`fixture_refresh_daily`.

## Quality gates

```powershell
uv run ruff format --check
uv run ruff check
uv run mypy main.py
uv run pytest
```

The same four gates run in CI on Ubuntu and Windows for every push and pull
request (`.github/workflows/ci.yml`).
