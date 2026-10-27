# Points adjustments

**Status:** complete
**Date:** 2026-10-27
**Decision:** `docs/adr/0010-append-only-assertions.md`
**Follow-up to:** `docs/reports/all-league-capture.md`

## Goal

Make a points deduction visible without turning a legitimate deduction into a
publish failure. The all-league sweep found Southampton on −4: the reported
overall total (20) was four below `3 × won + drawn` (24). A19 was relaxed to
allow that, but the value then passed silently. An operator had to remember the
audit report to know it existed.

Done means three things:

- the publish gate reports the gap as a warning, with the team and the numbers;
- the gap is queryable in history, not only in a console line;
- the stored value is still the source value — nothing is derived or rewritten.

## What changed

| File | Change | Why |
|---|---|---|
| `sql/004_points_adjustments.sql` | `v_points_adjustments`: overall rows where `points < 3W+D`, with reported, expected, and adjustment | the persisted surface for analysts and for history |
| `sql/005_assertions_a22.sql` | A22 `WARN` over `_assert_standings_long` | the candidate-level surface during publish |
| `src/dataderby/validate.py` | `_assert_standings_long` carries the team name; `load_assertions()` reads every `sql/*assertions*.sql`; duplicate ids and empty markers fail | one contract can grow without editing an applied migration |
| `src/dataderby/publish.py` | optional `on_warning` callback | WARNs do not block, but they must not disappear |
| `src/dataderby/cli.py` | dry-run prints WARNs; a real run prints and logs each warning | an operator sees the deduction without opening the database |
| `.gitattributes` | `*.sql text eol=lf` | the migration ledger hashes bytes; CRLF changed the hash |
| `tests/test_assertions.py` | A22 and loader tests | the warning, its scope, and the contract loader are pinned |
| `tests/test_views.py` | view tests plus a Hypothesis arithmetic oracle | the view matches the definition for arbitrary totals |
| `tests/test_publish.py` | a deducted candidate publishes, warns, and the view shows the gap | the end-to-end path |
| `tests/test_pipeline_cli.py` | dry-run output and the durable JSON log | the operator path |
| `docs/adr/0010-append-only-assertions.md` | the append-only rule | why A22 is a new file, not an edit to 002 |
| `docs/design/project-structure.md`, SQL deck/report | A1–A22, eight views, 23 definitions | living documentation stays true |

## Design decisions

### A deduction is reported, not derived

The source reports the points total. `3W+D` is only the arithmetic maximum. A
deduction is an event outside the match results, so the database keeps the
reported value and the view computes the gap beside it. Replacing the reported
value with `3W+D` would erase the deduction; replacing `3W+D` with the reported
value would hide an impossible total.

### A22 checks the overall table only

A deduction applies to the overall total. Home and away points are split tables
and A20 already excludes points from their sums. Checking all three views would
report one deduction three times. `test_a22_checks_only_the_overall_table` and
`test_points_adjustments_ignores_the_home_and_away_splits` pin this.

### WARN, not BLOCK

A deduction is legitimate (EFL clubs have them). A19 still blocks the impossible
direction: `points > 3W+D` or a negative total. A22 catches only
`points < 3W+D`. A −4 and a −40 are both warnings; the delta is the evidence a
human uses to decide whether the source is wrong.

### The warning is a callback, not a return-value change

`publish()` keeps returning `Outcome`. Tests and callers compare it with
`is Outcome.ACCEPTED`, and the signature is part of the pipeline's shape. The
CLI passes `on_warning` to print and log; a caller that does not care passes
nothing. WARNs never enter `blocking_failures()`.

### The assertion contract is append-only

`002_assertions.sql` was already applied in the live ledger. Editing it produced:

```text
migration error: 002_assertions.sql changed after it was applied
(recorded 0d21c51f4943, now cebfbad5fa70)
```

A22 therefore lives in `sql/005_assertions_a22.sql`. The loader reads every
`*assertions*.sql` file in lexical order. Duplicate ids fail rather than
shadowing. `*.sql` is forced to LF because the ledger hashes bytes, and a
Windows checkout had rewritten `002` with CRLF. ADR 0010 records the rule and the
rejected alternatives.

### The view filters to real gaps

`v_points_adjustments` returns only rows where the arithmetic gap exists. A
consumer that wants every team's arithmetic can join the facts; a view named
"adjustments" that returned zero rows would be noise. It carries `snapshot_id`,
`observed_at`, tournament/season/stage, season key, run id, and the two totals,
so the row is traceable to a capture.

### Rejected alternatives

- **Derive points from W/D.** It destroys the deduction and makes the source
  value unrecoverable.
- **Block the publish.** A legitimate deduction would stop a season's load.
- **One WARN per split.** It triples the noise for one event.
- **A new assertion in `002`.** The checksum is the ledger; editing an applied
  file defeats it.
- **A separate `warnings` table.** The view already exposes published
  deductions; the JSON log records candidate warnings. A third copy would need
  its own lifecycle for no new question.
- **A `dataderby adjustments` command.** The view is queryable with DuckDB and
  the run prints warnings. A command can be added when an operator asks for one.

## Test matrix

| Test | Pins |
|---|---|
| `tests/test_assertions.py::test_a22_reports_a_points_deduction_as_a_warning` | one deducted team yields one A22 WARN with `(id, name, reported, expected, −4)` |
| `...::test_a22_is_absent_when_every_total_matches_won_and_drawn` | a clean table produces no warning |
| `...::test_a22_checks_only_the_overall_table` | a home-table deduction is not reported |
| `...::test_a22_does_not_soften_an_impossible_total` | `points > 3W+D` still blocks with A19, not A22 |
| `...::test_a22_reports_each_deducted_team_with_its_own_gap` | two teams produce two rows with −4 and −1 |
| `...::test_a_points_deduction_is_not_blocked` | A19 and A20 remain silent for a deduction |
| `...::test_assertion_loader_reads_every_contract_file` | 002 and 005 load in lexical order |
| `...::test_assertion_loader_rejects_a_duplicate_id_across_files` | a shadowed id fails closed |
| `...::test_assertion_loader_rejects_a_marker_without_sql` | an empty assertion fails closed |
| `...::test_assertion_loader_rejects_a_directory_without_a_contract` | a missing contract is explicit |
| `tests/test_views.py::test_points_adjustments_lists_only_the_gap` | exact row, expected total, −4, season key, run id |
| `...::test_points_adjustments_keeps_each_snapshot_in_history` | two snapshots produce two rows, ordered by `observed_at` |
| `...::test_points_adjustments_excludes_rows_it_cannot_interpret` | NULL points, NULL wins, and an impossible total are excluded |
| `...::test_points_adjustments_ignores_the_home_and_away_splits` | a home-only deduction produces no row |
| `...::test_points_adjustments_matches_the_arithmetic_oracle` | 50 Hypothesis examples match the Python definition exactly |
| `...::test_migrate_creates_all_eight_consumer_views` | the view is applied by `migrate()` |
| `tests/test_publish.py::test_a_deducted_total_publishes_and_the_view_shows_the_gap` | accepted, one callback, stored value unchanged, view shows −4 |
| `tests/test_pipeline_cli.py::test_a_dry_run_prints_a_points_deduction` | `WARN A22` and `adjustment -4` on stdout, exit 0, no database written |
| `...::test_a_run_logs_a_points_deduction_without_blocking` | exit 0, `publish.warning` JSON line, one snapshot, one view row |

What the tests deliberately do **not** assert:

- They do not assert a specific log filename or timestamp; the test reads every
  `*.jsonl` in the run's log directory.
- They do not assert that a deduction is "correct"; the source owns that. They
  assert the arithmetic gap is reported and stored unchanged.
- They do not assert the absence of a WARN for a `no_change` run. `publish()`
  returns before running assertions when the fingerprint is cached; the view is
  the durable surface for that case.

## Evidence

```text
$ uv run ruff format --check
104 files already formatted

$ uv run ruff check
All checks passed!

$ uv run mypy main.py
Success: no issues found in 1 source file

$ uv run pytest -q
233 passed in 250.07s (0:04:10)
```

The live database was migrated by a real run, not a dry run:

```text
$ uv run dataderby run --stage epl-2026-2027
epl-2026-2027: no_change (20 teams, run run_e7c39ff3cc4347cb9e0be567e6198d23)

$ uv run python -c "..."
migrations [('001_schema.sql',), ('002_assertions.sql',), ('003_views.sql',),
            ('004_points_adjustments.sql',), ('005_assertions_a22.sql',)]
adjustments (0,)
snapshots (1,)
```

The EPL has no deduction, so zero rows is the correct result. The view was also
exercised against a synthetic in-memory snapshot:

```text
$ uv run python <demo_adjustments>
[('Southampton', 20, 24, -4)]
```

The checksum failure that forced the append-only design:

```text
$ uv run dataderby run --stage epl-2026-2027
migration error: 002_assertions.sql changed after it was applied
(recorded 0d21c51f4943, now cebfbad5fa70)

$ uv run python -c "hashlib.sha256(Path('sql/002_assertions.sql').read_bytes())"
0d21c51f4943 10631 crlf 0
```

No live facts were changed by the failed run: `migrate()` runs before the stage
loop. The following successful run applied `004` and `005` and recorded
`no_change`.

## Deviations and open items

- **`no_change` does not re-run A22.** `publish()` checks the cached fingerprint
  before assertions. A deduction that was accepted before A22 existed still
  appears in `v_points_adjustments`, but it will not produce a new console
  warning until the content changes. This is deliberate: a no-change run should
  not repeat old warnings.
- **No CLI query command.** The view is the analyst surface; `duckdb` can query
  it. Add `dataderby adjustments` if operators ask.
- **Home and away deductions are not reported.** A22 and the view check the
  overall table only. That is the documented meaning of a deduction; a source
  that applies one to all three splits would need a separate rule.
- **The contract is split across `002` and `005`.** ADR 0010 records why. A future
  removal or replacement needs a disable mechanism that does not exist yet.
- **A transient browser failure remains.** On 2026-10-26 the first live dry run
  failed with `page did not expose gSiteHeaderValue`; the immediate retry
  succeeded. It is a transport race, unrelated to this change, and needs its own
  issue.
- **Historical reports and decks still say A1–A21.** They are dated records. The
  living map (`docs/design/project-structure.md`) and the current SQL deck were
  updated.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| A deduction is actually a source error | A22 reports the delta; A19 still blocks the impossible direction; a human decides |
| A22 is noisy in a league with many deductions | WARN only, never blocking; rows carry the exact gap |
| A warning is lost after the console closes | `publish.warning` is appended to the daily JSONL log; the view persists accepted rows |
| An applied migration is edited again | append-only rule, `.gitattributes` LF, loader duplicate check, ADR 0010 |
| Windows checkout changes a checksum | `*.sql text eol=lf`; the ledger hashes the working-tree bytes |
| The view is mistaken for the source of truth | it selects the reported values and only computes the difference; the facts are unchanged |
| `no_change` hides a warning | documented above; the view remains queryable |

## Reviewer checklist

- [ ] A22 is WARN and only checks `view = 'overall'`.
- [ ] `points > 3W+D` still blocks with A19.
- [ ] The stored `points_overall` is the reported value, not `3W+D`.
- [ ] `v_points_adjustments` returns only real gaps and carries lineage.
- [ ] `002_assertions.sql` is byte-identical to the applied version.
- [ ] `005_assertions_a22.sql` is LF and is recorded in `schema_migration`.
- [ ] Duplicate assertion ids across files fail closed.
- [ ] Dry-run prints the warning and still exits 0.
- [ ] A real run logs `publish.warning` and commits one snapshot.
- [ ] The index and the living docs are updated.

## References

- `docs/adr/0010-append-only-assertions.md` — why the contract grows by new
  files.
- `docs/adr/0007-migration-ledger.md` — the checksum rule.
- `docs/reports/all-league-capture.md` — the Southampton −4 evidence and the
  original recommendation.
- `sql/002_assertions.sql`, `sql/004_points_adjustments.sql`,
  `sql/005_assertions_a22.sql`.
- `src/dataderby/validate.py`, `src/dataderby/publish.py`,
  `src/dataderby/cli.py`.
- `docs/slides/sql-schema-slides.html` — the schema/contract deck.
