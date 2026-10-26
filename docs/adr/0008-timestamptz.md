# 0008 - Store instants, render local time at read time

**Status:** accepted, 2026-10-26
**Decision owner:** project owner
**Resolves:** issue #4, and the open item in `docs/reports/p8-cli-operations.md`
**Related:** `docs/adr/0003-two-clocks.md`, `docs/reports/p7-views.md`

## Context

The schema stored every timestamp as a naive `TIMESTAMP`. Correctness depended on
`db.connect()` running `SET TimeZone='UTC'`. That worked for every caller that used
the helper, and failed for every caller that did not:

- P7's freshness test expected an age near five minutes and got one offset by the
  host's UTC offset, because DuckDB bound an aware UTC `datetime` through an
  `Asia/Calcutta` session into a naive column.
- The fix at the time was `SET TimeZone='UTC'` in `connect()` plus two tests. That
  protects the pipeline. It does not protect the `duckdb` CLI, a BI tool, a
  notebook, or a second service that opens the file directly.

The guarantee lived in code that has to be called. The data itself carried no
guarantee.

## Decision

1. Every pipeline timestamp is `TIMESTAMP WITH TIME ZONE` (`TIMESTAMPTZ`).
2. No local-time column is stored.
3. Local time is rendered at read time, by a view or by the consumer's query.
4. The session stays pinned to UTC, but only as a default for rendering and for
   parsing naive input. It is no longer the correctness mechanism.

The eight affected columns:

| Table | Columns |
|---|---|
| `ingestion_run` | `started_at`, `finished_at`, `observed_at` |
| `competition_snapshot` | `observed_at`, `accepted_at` |
| `raw_capture` | `captured_at` |
| `pipeline_checkpoint` | `last_probe_at`, `last_success_at` |
| `schema_migration` | `applied_at` |

`v_pipeline_freshness` now compares `last_success_at` with `current_timestamp`
directly. The old `current_timestamp AT TIME ZONE 'UTC'` existed only to match a
naive column; keeping it would compare a `TIMESTAMPTZ` with a naive `TIMESTAMP`.

## The data-layer argument

"Store UTC" is shorthand. The precise rule is: **store the instant, and let the type
say so**.

- `TIMESTAMPTZ` stores one instant (epoch microseconds). UTC is the encoding, not a
  second copy.
- There is no "UTC column" to protect from a local one. One column, one truth.
- Ordering, `max(observed_at)`, and "latest snapshot" are then independent of the
  machine, the session, and the reader.

This is the same reasoning as `docs/adr/0003-two-clocks.md`: we are recording when
something was observed, not the wall clock of the machine that recorded it.

## The presentation-layer argument

A local timestamp is a **function of an instant and a zone**. Storing the result of
that function creates a second truth:

- it drifts when the zone rule changes (DST, policy, a user in another zone);
- it goes stale on backfill unless every writer recomputes it;
- it is ambiguous during a fall-back hour (`01:30` happens twice);
- it bakes a presentation policy into immutable history.

So the application layer passes aware instants, the data layer stores one instant,
and the presentation layer decides how to show it.

`sql/003_views.sql` adds one lens:

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
FROM competition_snapshot;
```

The view stores nothing. It is the "show both side by side" requirement, expressed
where it belongs. A different zone is a one-line change to the view, or an
expression in the consumer's own query:

```sql
SELECT observed_at AT TIME ZONE 'Europe/London' AS observed_at_london
FROM competition_snapshot;
```

`AT TIME ZONE` returns a naive `TIMESTAMP` on purpose: the result is a wall-clock
label, not an instant. Do not feed it back into storage.

## What the data looks like

Stored: one instant, `2026-10-21 10:00:00+00`.

| Session | `observed_at` | `observed_at AT TIME ZONE 'Asia/Kolkata'` |
|---|---|---|
| UTC | `2026-10-21 10:00:00+00` | `2026-10-21 15:30:00` |
| `Asia/Kolkata` | `2026-10-21 15:30:00+05:30` | `2026-10-21 15:30:00` |

Before this change, both sessions returned the bare value `2026-10-21 10:00:00`.
The second session had no way to know it was UTC, which is exactly how the P7 defect
happened.

## Migration

There is no production database and no committed capture. Editing `001_schema.sql`
is the cheap path, and it is the one taken.

This is a deliberate exception to the ledger rule that applied files are immutable.
The justification is not convenience, it is row count: zero. The alternative, a
`004_timestamptz.sql` that rebuilds every table to change a type, would be more
dangerous than the change it migrates.

Consequence for a developer with an older database: the ledger refuses `001` with a
checksum error. Delete `data/dataderby.duckdb` and re-run. There is nothing to
preserve. After the first real capture, this path is closed and a type change
requires a real migration.

## Consequences

**Good**

- A reader cannot misinterpret the instant, even without `connect()`.
- The UTC defect class is removed at the type level.
- Local rendering is explicit, testable, and reversible.

**Costs**

- Python now returns timezone-aware datetimes. Code comparing against naive
  datetimes must move to aware or to `.timestamp()`. Two existing tests needed this.
- Day bucketing needs an explicit zone:
  `date_trunc('day', observed_at AT TIME ZONE 'Asia/Kolkata')`, not
  `date_trunc('day', observed_at)`.
- CSV/JSON exports render in the exporting session unless pinned. Pin UTC in the
  exporter or export the ISO-8601 string with the offset.

**Unchanged**

- `connect()` still sets `TimeZone='UTC'`. It is now a default, not a guarantee.
- Raw payloads are still the system of record
  (`docs/adr/0004-raw-is-system-of-record.md`).

## Rejected alternatives

- **Keep naive `TIMESTAMP` and rely on `connect()`.** This is what failed. The
  guarantee cannot travel with the file.
- **Store UTC epoch as `BIGINT`.** Correct but hostile: every query needs a
  conversion, and the unit becomes tribal knowledge.
- **Store both `observed_at_utc` and `observed_at_ist`.** Two truths for one
  instant; the local one drifts on DST and policy changes. This is the pattern the
  legacy fixture table uses (`kickoff_utc` / `kickoff_ist`), and it is deliberately
  not copied into the snapshot schema.
- **Store a fixed offset (`+05:30`).** Offsets are not zones. They are wrong for any
  region with DST and wrong the moment a policy changes.
- **Store a timezone name on every row.** WhoScored publishes no timestamps; the
  instant is ours. A zone column would be constant and misleading. If a future
  source carries a local schedule, that is a different column with different
  semantics (see below).

## When a local value *is* data

Storing a zone is correct when the zone is part of the business fact:

- a fixture's local kickoff date (`match_date DATE` in the competition's zone);
- a daily report partitioned by local date;
- a schedule that means "09:00 local", which must store `09:00` plus
  `Europe/London`, not a UTC instant, because the instant moves with DST.

Those are additions, not replacements. They do not reintroduce a duplicate instant.

## Tests

- `tests/test_schema.py::test_timestamps_store_an_instant_not_a_wall_clock`
- `tests/test_schema.py::test_a_non_utc_session_reads_the_same_instant`
- `tests/test_schema.py::test_pipeline_timestamp_columns_carry_a_timezone`
- `tests/test_views.py::test_snapshot_clock_renders_one_instant_in_utc_and_ist`
- `tests/test_views.py::test_standings_history_returns_one_series_row_per_snapshot`
  (updated: history now returns aware datetimes)
- `tests/test_views.py::test_migrate_creates_all_seven_consumer_views`
  (the view count is a contract)
