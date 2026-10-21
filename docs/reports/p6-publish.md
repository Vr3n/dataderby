# P6 - Publish, validate, and reconcile

**Status:** complete
**Date:** 2026-10-21
**Plan:** `plans/v1-build-plan.md` §9

## Goal

Make a candidate publishable exactly once, refuse an incoherent sweep before it
can change the warehouse, and give an interrupted run a deterministic restart
path.

The phase has three parts:

1. `validate.py` stages the candidate and its provenance and executes A1-A21.
2. `publish.py` writes the header and facts in one transaction, or returns
   `no_change` without writing a second snapshot.
3. `reconcile()` turns runs left in `running` into `accepted` or `abandoned`
   when the process starts again.

## What was built

| Module | Responsibility |
|---|---|
| `src/dataderby/validate.py` | Assertion loader, candidate/provenance staging, execution, actions, and `PublishBlocked`. |
| `src/dataderby/publish.py` | Parent selection, single transaction, literal fact inserts, checkpoint/run updates, no-change handling, `reconcile()`, and `sql_literal()`. |
| `sql/002_assertions.sql` | Comment-delimited A1-A21 plus the A7 uniqueness warn (`A7U`). |

### The assertion contract

`sql/002_assertions.sql` is deliberately comment-only. `migrate()` can execute
it safely, while `validate.load_assertions()` reads this shape:

```sql
-- @@A1|BLOCK
-- SELECT ...
```

Each SQL query returns offending rows; no rows means the assertion passed.
Actions follow the implementation plan:

| ID | Action | Check |
|---|---|---|
| A1 | BLOCK | Exactly `expected_teams` candidate rows. |
| A2 | BLOCK | Team ids unique. |
| A3 | BLOCK | Nine feed captures, one per `(section, view)`. |
| A4 | RETRY | Team-id set identical across all nine captures. |
| A5 | RETRY | `apps`, goals, yellow, and red split totals add up. |
| A6 | RETRY | Shared `apps`/`rating`/`shotsPerGame` agree across sections. |
| A7 | BLOCK | Ranking is in `1..N` for every section/view. |
| A7U | WARN | Ranking uniqueness only warns. |
| A8 | BLOCK | Rating/percentage ranges, non-negative counts, finite doubles. |
| A9 | BLOCK | No NULL identity fields. |
| A10 | BLOCK | `apps` did not decrease versus the previous accepted snapshot. |
| A11 | BLOCK | Feed URLs contain `stageId=<stage>`. |
| A12 | BLOCK | The page URL contains the configured season and stage path. |
| A13 | BLOCK | Payload tournament/isOpta metadata matches the run. |
| A14 | RETRY | Capture span is at most 180 seconds. |
| A15 | BLOCK | Source schema and name checks pass while re-reading the raw feeds. |
| A16 | BLOCK | Fact/header anti-join is empty. |
| A17 | RETRY | One page capture; three standings views iff the stage declares a table. |
| A18 | RETRY | Standings and feed team-id sets are equal. |
| A19 | BLOCK | Standings arithmetic and form rules. |
| A20 | RETRY | Standings home + away = overall. |
| A21 | BLOCK | Rank is a permutation in every split. |

`publish()` treats `RETRY` and `BLOCK` as blocking for this attempt and raises
`PublishBlocked` with the failures. The retry-once policy belongs to the caller
(P8); P6 exposes the action so the caller does not have to parse messages.

### Staging and provenance

`run_assertions()` creates temporary `_assert_*` tables for the candidate,
standings, run metadata, captures, source-level team sets, shared measures, and
long-form measure/standings views. Candidate/standings staging uses one literal
multi-row insert per table: the first implementation used `executemany()` and
spent most of its time in per-row calls.

Provenance-dependent assertions (A3/A4/A11/A12/A15/A17) are skipped when
`run=None`. `publish()` always supplies a `LandingResult`, so a real publish
never takes that shortcut.

### Publish transaction

`publish(con, candidate, standings, spec, run)`:

1. Computes the canonical fingerprint.
2. Returns `NO_CHANGE` immediately when the checkpoint already holds that
   fingerprint.
3. Starts a transaction and runs the assertions.
4. Selects the parent with the latest `observed_at` for the stage, or `genesis`.
5. Inserts the header with
   `ON CONFLICT (parent_snapshot_id, content_fingerprint) DO NOTHING RETURNING`.
6. If the conflict produced no row, resolves the existing snapshot id, updates
   the checkpoint to `no_change`, marks the run `no_change`, commits, and
   returns `NO_CHANGE`.
7. Otherwise inserts 20 team facts and 20 standings facts (or zero standings
   facts for a no-table stage), updates the checkpoint and run to `accepted`,
   commits, and returns `ACCEPTED`.
8. Rolls back the whole transaction on any failure. Validation failures mark the
   run `blocked`; unexpected insert failures mark it `crashed`.

The header insert, both fact tables, the checkpoint, and the run outcome share
the same transaction. A crash therefore cannot leave an accepted run without
facts or a committed snapshot without a checkpoint.

### Parent selection and backfill

`latest_parent_snapshot()` orders accepted headers by `observed_at DESC`,
`accepted_at DESC`, `snapshot_id DESC`. A backfilled older snapshot still points
at the latest observed snapshot, but it does not become the newest snapshot.
A10 compares against the newest accepted snapshot strictly before the
candidate's `observed_at`, so a backfill is compared with the state that preceded
it, not with the later state it is backfilling beneath.

### Reconciliation

`reconcile(con)` finds `ingestion_run.outcome = 'running'`:

- a run with a committed snapshot becomes `accepted` and records its snapshot;
- every other run becomes `abandoned`, and its stage checkpoint increments
  `abandoned_runs`.

Because the publish transaction commits the run outcome with the data, a normal
crash between header and facts cannot leave a running row. Reconciliation still
covers process death before publish starts and externally interrupted runs.

### Literal facts

`sql_literal()` and `insert_facts()` do not bind fact rows. `sql_literal()`
supports `None`, `int`, `float`, `str`, and `bool`, rejects NaN/infinity, and
escapes `'` as `''`. `insert_facts(con, candidate, standings, snapshot_id)`
issues one multi-row `INSERT ... VALUES` per fact table.

## Tests

`tests/test_assertions.py`:

- asserts the contract file contains A1-A21 and A7U with BLOCK/RETRY/WARN
  actions;
- passes a clean 20-team/60-measure/30-standings candidate with no failures;
- has one trap per assertion: short cohort, duplicate ids, missing capture,
  changed team set, broken split totals, shared-measure conflict, ranking range,
  duplicate ranking warn, negative/NaN/out-of-range measure, NULL identity,
  apps decrease and override, missing `stageId`, bad page URL, wrong metadata,
  slow span, schema drift, orphan fact constraint, missing standings views,
  team-set mismatch, standings arithmetic, split totals, and rank permutation;
- verifies a no-table stage ignores a leaked table when A17 says no table is
  expected;
- verifies provenance assertions are skipped when no landing result is supplied.

`tests/test_publish.py`:

- accepted publish writes one header, 20 team facts, 20 standings facts, the
  checkpoint, and the run outcome;
- same content returns `NO_CHANGE` without a second header;
- A -> B -> A creates a new edge rather than reusing the first A;
- a backfill gets the latest observed snapshot as parent and does not become
  newest;
- A5 validation failure rolls back every table and marks the run `blocked`;
- a same-observed insert failure rolls back the whole snapshot and marks the run
  `crashed`;
- a no-table stage publishes zero standings facts;
- `sql_literal()` round-trips an adversarial string set and a Hypothesis text
  property, and rejects non-finite/unsupported values;
- fact names keep quotes verbatim;
- reconciliation accepts a committed running run and abandons an uncommitted
  one.

The P5 synthetic helper was adjusted for P6 only: `apps` and goals now split into
home/away totals, and feed URLs contain `stageId`. The P5 parse/standings tests
still pass unchanged otherwise.

## Verification

Run on 2026-10-21:

```text
uv run ruff format --check
73 files already formatted

uv run ruff check
All checks passed!

uv run mypy main.py
Success: no issues found in 1 source file

uv run pytest
153 passed in 228.62s (0:03:48)
```

`uv run mypy src/dataderby/publish.py src/dataderby/validate.py` also passes.
`migrate()` was separately exercised against the comment-only assertion file and
reported the expected six tables.

## Deviations and open items

- A7 uniqueness is the extra `A7U` WARN definition because one assertion id
  cannot produce both a BLOCK range result and a WARN duplicate result.
- DuckDB 1.5.6 actually enforces the fact/header foreign key in this environment,
  contrary to the implementation-plan note. A16 remains as defence in depth;
  the test verifies the constraint rejects an orphan before the assertion runs.
- Retry-once policy is not in P6. `publish()` reports `RETRY` failures through
  `PublishBlocked`; the caller must fetch again and decide when to give up.
- The validation fixtures remain synthetic. No live capture or raw payload is
  committed.
- A1 does not yet set the `whoscored_not_ready` error code; the P8 CLI will map
  assertion failures to operator-facing codes.
- There is no CI; all gates are local.
- E5 cadence measurement still waits for the 2026-10-24 EPL window.
- Conference League stage `25802` and 2026/27 knockout stage granularity remain
  unverified against the live source.
