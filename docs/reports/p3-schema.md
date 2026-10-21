# P3 - Schema and DuckDB helpers

**Status:** complete
**Date:** 2026-10-21
**Plan:** `plans/v1-build-plan.md` §6

## Goal

Six tables that enforce the v1 invariants without relying on application code,
plus the connection, migration, and transaction helpers those tables need.

## Tables

`sql/001_schema.sql` creates:

| Table | Invariant |
|---|---|
| `ingestion_run` | One row per run; outcome is one of seven declared values. |
| `raw_capture` | One ledger row per run/section/view; byte count and attempt are non-negative. |
| `competition_snapshot` | Unique `(parent, fingerprint)` edge; unique stage/`observed_at` address. |
| `fact_team_snapshot` | Header FK; one row per snapshot/team; 60 contract measures. |
| `fact_standings_snapshot` | Header FK; one row per snapshot/team; 30 contract measures. |
| `pipeline_checkpoint` | One row per stage; attempt and abandoned-run counts. |

### Source naming

The plan's schema sketch used bare `tournament_id` and `team_id`. The committed
schema uses the source-qualified names required by `AGENTS.md`:

- `whoscored_tournament_id`
- `whoscored_season_id`
- `whoscored_stage_id`
- `whoscored_team_id`
- `whoscored_team_name`
- `whoscored_page_url`

`raw_capture.byte_count` replaces the sketch's `bytes` to avoid a type/function
name collision.

### Types and checks

- `apps_*` and `ranking_*` are `INTEGER`; other measures are `DOUBLE`. Goals and
  cards remain `DOUBLE` because the source sends values such as `31.0`.
- Every measure is nullable and has `CHECK (col >= 0)`. In SQL, `NULL >= 0`
  evaluates to `NULL`, so a missing measure passes while a negative one fails.
- `goal_difference_*` is signed and has no non-negative check.
- Foreign keys on both fact tables make a fact without a header fail.

## Helpers

`src/dataderby/db.py` provides:

- `connect(path, read_only=False)`: creates the parent directory for a writable
  file and sets `PRAGMA threads=4`.
- `migrate(con, sql_dir=...)`: applies every `*.sql` file in lexical order. The
  v1 schema is idempotent; a future non-idempotent migration must guard itself.
- `transaction(con)`: `BEGIN`, then `COMMIT` on success or `ROLLBACK` and
  re-raise on failure. There is deliberately no `COMMIT` in `finally`.

## Verification

`tests/test_schema.py` covers:

- applying the schema twice;
- fact and standings rows without a header;
- a snapshot with zero standings rows;
- duplicate `(parent, content)`;
- duplicate `(stage, observed_at)`;
- the `(NULL, content)` uniqueness trap on a throwaway table;
- a negative count rejected and a `NULL` accepted;
- all 60 fact columns in contract order;
- all 30 standings columns in contract order;
- a failed transaction rolling back and a successful transaction committing.

Run on 2026-10-21:

```text
uv run ruff format --check
47 files already formatted

uv run ruff check
All checks passed!

uv run mypy main.py
Success: no issues found in 1 source file

uv run pytest
57 passed in 6.88s
```

## Open items

- `migrate()` applies a whole SQL file in one `execute()`. That works for
  `001_schema.sql`; a future migration with statements that cannot share a
  transaction needs a different runner.
- The schema has no CI dry run and no migration-history table. v1 has one
  migration; add a history table before the second one.
- The `NULL` parent trap is documented and tested, but production code must
  still default a new snapshot to `'genesis'`, never to `NULL`.

## Next

P4: page capture, three standings views, nine feed payloads, raw landing, and the
run ledger.
