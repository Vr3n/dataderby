# Data Derby

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
[`docs/whoscored-discovery-report.md`](docs/whoscored-discovery-report.md) and
[`docs/whoscored-discovery-report.html`](docs/whoscored-discovery-report.html). The
decisions and the cadence evidence are in
[`docs/whoscored-decisions.md`](docs/whoscored-decisions.md) and
[`docs/whoscored-cadence.md`](docs/whoscored-cadence.md).

The final v1 plan and its 47-slide deck are in
[`plans/v1-implementation-plan.md`](plans/v1-implementation-plan.md) and
[`docs/dataderby-v1-plan.html`](docs/dataderby-v1-plan.html). The executable build
order and test matrix are in [`plans/v1-build-plan.md`](plans/v1-build-plan.md).

The P0–P7 production-readiness review is a beginner-oriented animated deck in
[`docs/production-readiness-slides.html`](docs/production-readiness-slides.html):
one concept per slide, each with a plain-language explanation, a source, and a
recommendation. Open it in a browser; it works offline.

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
one-page summary is [`docs/p8-summary.md`](docs/p8-summary.md).

The schema is applied through a checksummed ledger (`schema_migration`), so an
applied SQL file is never re-run and never silently edited.

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
