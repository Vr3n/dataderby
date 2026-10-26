# TIMESTAMPTZ migration

**Status:** complete
**Date:** 2026-10-26
**Issue:** #4
**Decision:** `docs/adr/0008-timestamptz.md`
**Commit:** `0c69ade`
**Scope:** schema, assertion staging, freshness view, one new presentation view,
tests, README

## Goal

Remove the class of bug where the same stored value means two different instants
depending on who reads it.

Before this change the guarantee lived in `db.connect()`:

```python
con.execute("SET TimeZone='UTC'")
```

Every caller that used the helper was safe. Every caller that opened the file
directly — the `duckdb` CLI, a BI tool, a notebook, a future service — was not. P7
already produced one defect of this class: an age near five minutes came back offset
by the host's UTC offset because DuckDB bound an aware UTC datetime through an
`Asia/Calcutta` session into a naive column.

The fix is not a better helper. The fix is a type that carries the instant.

## What changed

| File | Change | Why |
|---|---|---|
| `sql/001_schema.sql` | 8 columns `TIMESTAMP` → `TIMESTAMP WITH TIME ZONE` | the guarantee moves into the data |
| `src/dataderby/db.py` | ledger `applied_at` is `TIMESTAMPTZ`; `connect()` docstring | the ledger is data too; the docstring no longer claims the pin is correctness |
| `src/dataderby/validate.py` | `_assert_run.observed_at`, `_assert_capture.captured_at` | assertion staging must match the tables it models |
| `sql/003_views.sql` | freshness compares `TIMESTAMPTZ` with `current_timestamp`; new `v_snapshot_clock` | remove the naive shim; add a read-time local lens |
| `tests/test_schema.py` | 3 timestamp tests replace 1 | pin the new contract |
| `tests/test_views.py` | clock view test; aware history expectations; seven-view contract | pin presentation and the new count |
| `README.md` | timezone section explains the two approaches | a reader should not assume the fixture table's pattern is the snapshot pattern |

No runtime dependency was added.

## Schema

The eight columns:

| Table | Columns |
|---|---|
| `ingestion_run` | `started_at`, `finished_at`, `observed_at` |
| `competition_snapshot` | `observed_at`, `accepted_at` |
| `raw_capture` | `captured_at` |
| `pipeline_checkpoint` | `last_probe_at`, `last_success_at` |
| `schema_migration` | `applied_at` |

Example:

```sql
-- before
observed_at  TIMESTAMP NOT NULL,

-- after
observed_at  TIMESTAMP WITH TIME ZONE NOT NULL,
```

`TIMESTAMPTZ` is an alias for `TIMESTAMP WITH TIME ZONE`; the explicit form is used
in DDL so the intent survives a search for `TIMESTAMP`.

## Semantics

`TIMESTAMPTZ` stores one instant (epoch microseconds). It does not store a zone, an
offset, or a local wall clock. Rendering is a session concern.

| Session | `observed_at` | `observed_at AT TIME ZONE 'Asia/Kolkata'` |
|---|---|---|
| UTC | `2026-10-21 10:00:00+00` | `2026-10-21 15:30:00` |
| `Asia/Kolkata` | `2026-10-21 15:30:00+05:30` | `2026-10-21 15:30:00` |

Before the change both sessions returned `2026-10-21 10:00:00`. The second session
had no way to know it was UTC.

Two consequences worth stating because they are easy to get wrong:

- `AT TIME ZONE` returns a **naive** `TIMESTAMP`: a wall-clock label, not an
  instant. Do not write it back to storage.
- `date_trunc('day', observed_at)` buckets by UTC. A local day needs
  `date_trunc('day', observed_at AT TIME ZONE 'Asia/Kolkata')`.

## Presentation view

```sql
CREATE OR REPLACE VIEW v_snapshot_clock AS
SELECT
    snapshot_id,
    whoscored_tournament_id,
    whoscored_season_id,
    whoscored_stage_id,
    observed_at                             AS observed_at_utc,
    observed_at AT TIME ZONE 'Asia/Kolkata' AS observed_at_ist,
    accepted_at                             AS accepted_at_utc,
    accepted_at AT TIME ZONE 'Asia/Kolkata' AS accepted_at_ist
FROM competition_snapshot
ORDER BY observed_at DESC, accepted_at DESC, snapshot_id DESC;
```

The view stores nothing. It is the "show both side by side" requirement expressed
where it belongs, and it is reversible: changing the zone changes a rendering, not
history.

A consumer with a different zone does not need a schema change:

```sql
SELECT observed_at AT TIME ZONE 'Europe/London' AS observed_at_london
FROM competition_snapshot;
```

## Freshness

Before:

```sql
date_diff('second', c.last_success_at, current_timestamp AT TIME ZONE 'UTC')
```

After:

```sql
date_diff('second', c.last_success_at, current_timestamp)
```

The `AT TIME ZONE 'UTC'` was a shim to match a naive column. With both sides
`TIMESTAMPTZ`, keeping it would compare an instant with a wall clock and reintroduce
the bug in the one place it had already been fixed.

`test_pipeline_freshness_returns_one_row_per_configured_stage` still asserts
`250 <= age_seconds <= 3600`, which is the regression guard for the offset error.

## Application-layer contract

- Write aware `datetime` values. The pipeline already does (`datetime.now(UTC)`,
  parsed capture times).
- Read aware values. DuckDB's Python client returns aware datetimes for
  `TIMESTAMPTZ`.
- Do not compare an aware value with a naive one. Move the naive side to UTC or
  compare `.timestamp()`.
- Exports: pin UTC, or emit ISO-8601 with the offset. A CSV exported from an
  `Asia/Calcutta` session renders `15:30+05:30`.

## Migration

There is no production database and no committed capture. `data/dataderby.duckdb`
does not exist. `001_schema.sql` was therefore edited directly.

This is a deliberate exception to the ledger rule that applied files are immutable.
The justification is row count, not convenience:

- zero rows to preserve;
- a `004_timestamptz.sql` that rebuilt every table to change a type would be more
  dangerous than the change itself;
- after the first real capture this shortcut is closed, and a type change needs a
  real migration.

Developer with an older database:

1. the ledger raises `MigrationError` naming `001_schema.sql` and both checksums;
2. delete `data/dataderby.duckdb`;
3. re-run `dataderby run` (or `migrate()` from a test).

There is nothing to back up. If that is no longer true, do not follow this path.

## Test matrix

| Test | Pins |
|---|---|
| `test_timestamps_store_an_instant_not_a_wall_clock` | round-trip returns an aware value equal to the input |
| `test_a_non_utc_session_reads_the_same_instant` | an `Asia/Kolkata` reader gets the same instant, rendered `15:30` |
| `test_pipeline_timestamp_columns_carry_a_timezone` | every timestamp column in `information_schema` is `TIMESTAMP WITH TIME ZONE` |
| `test_snapshot_clock_renders_one_instant_in_utc_and_ist` | `10:00Z` → `15:30` IST; UTC side stays aware, IST side is naive |
| `test_standings_history_returns_one_series_row_per_snapshot` | history now yields aware datetimes |
| `test_migrate_creates_all_seven_consumer_views` | the view count is a contract, not an accident |
| `test_pipeline_freshness_returns_one_row_per_configured_stage` | the age regression guard still holds |

What the tests deliberately do **not** do:

- They do not assert the SQL text of the view. They assert the rendering.
- They do not mock DuckDB. The type semantics are the thing under test; a mock
  would pass with the wrong type.
- They do not assert a specific timezone database version. The `10:00 → 15:30`
  offset is stable for `Asia/Kolkata` (no DST).

## Verification

```
$ uv run ruff format --check
84 files already formatted

$ uv run ruff check
All checks passed!

$ uv run mypy main.py
Success: no issues found in 1 source file

$ uv run pytest -q
192 passed
```

CI on `0c69ade`: `gates (ubuntu-latest)` and `gates (windows-latest)` both pass.
The Windows leg matters for the lock and path code, not for the type, but the type
change is exercised by the same suite.

## Reviewer checklist

- [ ] Every `TIMESTAMP` in `sql/` is either `TIMESTAMP WITH TIME ZONE` or an
      `AT TIME ZONE` rendering.
- [ ] No new column stores a local duplicate of an instant.
- [ ] New queries that bucket by day state the zone explicitly.
- [ ] Any new export path pins UTC or emits an offset.
- [ ] The fixture `kickoff_ist` column is untouched: this change does not migrate
      the SQLite slice.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Naive comparisons break silently | the type change surfaces them as `TypeError`/wrong results in tests; both affected tests were updated |
| A consumer expects `10:00` and now sees `15:30+05:30` | documented here and in the README; consumers should use `v_snapshot_clock` for display |
| Old database refuses `001` | delete it; no data exists. The ledger error names the file |
| Someone "fixes" a timestamp with an `UPDATE` | ADR 0008 states instants are immutable; fix the reader |
| A future source carries local schedule times | store zone + local time as separate columns; do not convert to an instant and lose the zone |

## Follow-ups

- The legacy SQLite fixture table still stores `kickoff_utc` and `kickoff_ist`.
  That is out of scope for v1 and is called out in the README.
- If a future schedule means "09:00 local", store `09:00` plus the zone, not a UTC
  instant. ADR 0008 records this rule.
- `docs/reports/p8-cli-operations.md` and `docs/p8-summary.md` now point at this
  change; the P8 evidence line records 192 tests.

## References

- `docs/adr/0008-timestamptz.md` — the decision and rejected alternatives.
- `docs/adr/0003-two-clocks.md` — observed vs accepted time.
- `docs/reports/p7-views.md` — the defect that motivated the change.
- PostgreSQL date/time types — https://www.postgresql.org/docs/current/datatype-datetime.html
- DuckDB timestamp types — https://duckdb.org/docs/current/sql/data_types/timestamp.html
