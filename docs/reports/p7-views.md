# P7 - Consumer views

**Status:** complete
**Date:** 2026-10-21
**Plan:** `plans/v1-build-plan.md` §10

## Goal

Expose the three questions the warehouse can answer without letting a consumer
copy a near-miss query from a dashboard:

1. what is the current state of a stage;
2. how did the season-to-date table move between accepted snapshots;
3. is the pipeline fresh.

The phase ships `sql/003_views.sql` and `tests/test_views.py`. `migrate()` applies
the file after the schema and the assertion contract, so every connection that
migrates gets the views.

## What was built

| View | Grain | Responsibility |
|---|---|---|
| `v_latest_team_state` | one row per team in the latest snapshot of a stage | Snapshot chosen first, then joined to `fact_team_snapshot`; carries the header, identity, and 60 team measures. |
| `v_latest_standings` | one row per team in the latest snapshot of a stage | The same snapshot selection, joined to `fact_standings_snapshot`; the 30 standings measures without the 60 team measures. |
| `v_latest_team_with_standings` | one row per team at the latest snapshot | Consumer view: the 60 team measures plus the 30 standings measures, `LEFT JOIN`ed on `(snapshot_id, whoscored_team_id)`; a no-table stage yields NULL standings columns, never missing teams. |
| `v_standings_history` | one row per `(stage, team, observed_at)` | The journey view: rank, points, and form per split over every accepted snapshot. |
| `v_snapshot_delta` | one row per `(team, snapshot)` that has an immediate predecessor | Full-history `lag()` over `(tournament, season, stage, team)`; deltas only for `apps`, `goal`, `yellow_card`, and `red_card`; `is_correction` is `d_apps < 0`. |
| `v_pipeline_freshness` | one row per known stage | Checkpoint health plus the accepted-snapshot count: `last_probe_at`, `last_success_at`, `age_seconds`, `last_outcome`, `attempt_count`, `accepted_snapshots`, `last_committed_fingerprint`. |

### Snapshot selection

The latest views rank `competition_snapshot` per
`(whoscored_tournament_id, whoscored_season_id, whoscored_stage_id)` by
`observed_at DESC, accepted_at DESC, snapshot_id DESC`, keep rank 1, and only then
join facts. Selecting the snapshot first is the whole point: a team missing from
the newest snapshot cannot be resurrected by a fact-row join. A backfill has an
older `observed_at`, so it never becomes the latest row even when its
`accepted_at` is newer.

Selection is per stage, not global. A league stage and a knockout stage of the
same tournament/season coexist in the views.

### Delta semantics

`v_snapshot_delta` uses the full accepted history, not "the latest two rows per
team". A row is emitted only when the team was present in the immediately
preceding snapshot of that stage. If a team is absent from a middle snapshot, the
next appearance produces no diff rather than a silently joined diff across the
gap. Additive measures are differenced; rate and percentage measures are not,
because their difference does not count anything.

### Freshness and the UTC clock

`v_pipeline_freshness` unions stage addresses from `pipeline_checkpoint`,
`competition_snapshot`, and `ingestion_run`. A stage that only exists in
configuration has no database row, so the view cannot show it; the union is the
closest honest definition of "known stage".

`age_seconds` is `greatest(0, date_diff('second', last_success_at, current_timestamp AT TIME ZONE 'UTC'))`
and is NULL until the first success. This exposed a real defect during P7:
DuckDB binds a timezone-aware UTC `datetime` into a `TIMESTAMP` column using the
session timezone. On this host (`Asia/Calcutta`) an observation at `10:00Z` was
being stored as `15:30`, and a naive timestamp compared with `current_timestamp`
was off by the host's UTC offset. `db.connect()` now pins `TimeZone=UTC`, so the
P5/P6 write path stores UTC wall time and `age_seconds` is correct regardless of
the machine that runs the pipeline.

## Tests

`tests/test_views.py`:

- asserts `migrate()` creates exactly the six consumer views;
- **latest-state leak:** a team dropped from the newest snapshot does not
  reappear from an older one;
- **delta gap:** a team absent from the middle snapshot yields no diff against
  the snapshot before the gap;
- **delta arithmetic:** all four additive deltas and the `is_correction` flag;
- **backfill:** an older observation with a newer `accepted_at` does not change
  `v_latest_team_state`;
- **standings join:** the consumer view is one row per team, joins on ids rather
  than names, and a no-table stage keeps the teams with NULL standings columns;
- **latest standings:** the standings-only view returns one row per team and is
  empty for a no-table stage;
- **standings history:** one rank/points/form row per team per snapshot, ordered
  by `observed_at`;
- **freshness:** exactly one row per configured stage, `age_seconds` near the
  five-minute truth (which also traps a local-time comparison), and NULL before
  the first success;
- **freshness union:** stages seen only in an `ingestion_run` or only in a
  `competition_snapshot` still appear.

`tests/test_schema.py` gained two guards for the UTC session, and its table-list
assertion now filters `table_type = 'BASE TABLE'` so the six-table contract
remains exact while views are covered by `test_views.py`.

## Verification

Run on 2026-10-21:

```text
uv run ruff format --check
75 files already formatted

uv run ruff check
All checks passed!

uv run mypy main.py
Success: no issues found in 1 source file

uv run pytest
165 passed in 261.42s (0:04:21)
```

The views were also exercised directly against a scratch DuckDB file before the
tests were written: all six created, and `DESCRIBE` reported the expected column
sets.

## Deviations and open items

- The build-plan task list names five views; the implementation plan §8.1 and the
  v1 deck require `v_standings_history`, so P7 ships six. The history view is the
  one a chart or a "position over time" query reads.
- The delta sketch in the implementation plan filters only on `prev_apps IS NOT
  NULL`. The committed view additionally requires the team's previous appearance
  to be the previous stage snapshot, which is what makes the gap test meaningful.
- The freshness view cannot know a configured stage that has never been probed.
  The P8 CLI can left-join the registry if it needs a true per-config row.
- Pinning the DuckDB session to UTC changes stored timestamp values relative to
  P5/P6 behaviour on a non-UTC host. The warehouse has no committed real
  captures, so no data migration is required; synthetic fixtures are unaffected.
- There is no CI; all gates are local.
- No live capture is committed; P7 fixtures are synthetic.
- E5 cadence measurement still waits for the 2026-10-24 EPL window.
- Conference League stage `25802` and 2026/27 knockout stage granularity remain
  unverified against the live source.
