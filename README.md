# Data Derby

Football competition data pipeline. This first slice ingests the 2026/27 fixture
calendar for twelve competitions into SQLite, orchestrated by Dagster.

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

## Layout

```
config/dagster.yaml        Dagster instance config (SQLite)
src/dataderby/fixtures/    competitions, download, parse, store, assets, CLI
tests/                     parser, storage, service, CLI, downloader
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
