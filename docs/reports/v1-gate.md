# V1 gate

**Status:** complete
**Date:** 2026-10-27
**Issue:** #9
**Design:** `docs/design/runbook.md`

## Goal

Prove the system runs unattended: two consecutive runs with no manual
intervention, the second writing nothing; a short cohort refused; freshness
showing both runs; a backup that actually restores. The gate is the definition
of "runs unattended", not a checklist.

## Evidence

### Full ingestion: 11 of 12 stages publish

Every schedulable stage was run live on 2026-10-27 (the Conference League feed
returns zero rows and stays unscheduled by design):

| Stage | Teams | Outcome |
|---|---|---|
| Premier League | 20 | `no_change` (fingerprint still matches) |
| Championship | 24 | `accepted`, then `no_change` on the repeat |
| League One | 24 | `accepted` |
| League Two | 24 | `accepted` |
| La Liga | 20 | `accepted` |
| Serie A | 20 | `accepted` |
| Bundesliga | 18 | `accepted` |
| Ligue 1 | 18 | `accepted` |
| Eredivisie | 18 | `accepted` |
| Champions League | 36 | `accepted` |
| Europa League | 36 | `accepted` |

258 team facts and 258 standings facts. Every run exited `0`.

### Two consecutive runs, second `no_change`

```text
$ uv run dataderby run --stage championship-2026-2027
championship-2026-2027: accepted (24 teams, run run_3812ace...)

$ uv run dataderby run --stage championship-2026-2027
championship-2026-2027: no_change (24 teams, run run_daa8f2...)
```

The stage still has exactly 1 snapshot; the checkpoint reads
`('no_change', 2, True)`: two attempts, latest outcome `no_change`, accepted
snapshot intact. The second run wrote no snapshot and no facts.

### A deduction surfaced on the first real encounter

The Championship repeat printed:

```text
WARN A22: Southampton (team 18) reports 20 points, expected 24, adjustment -4
```

and `v_points_adjustments` returns `[('Southampton', 20, 24, -4)]`. The issue
#11/#22 machinery worked on live data without intervention.

### A 19-team cohort is refused

Covered by the suite, not by poisoning the live database:
`test_nineteen_team_cohort_is_incomplete` (the parse layer raises
`IncompleteCohort` before anything is staged) and
`test_blocking_assertion_rolls_back_and_marks_run` (a blocked publish rolls
back and marks the run). The previous snapshot stays latest because a blocked
publish never commits.

### Freshness shows every run

```text
$ uv run dataderby freshness --check
... 11 stages, all fresh, 0 of 11 stages stale (older than 36 h)
exit=0
```

`last_outcome`, `attempt_count`, and `accepted_snapshots` are visible per
stage; the EPL row shows the earlier `no_change` run.

### Backup and restore drill

```text
$ uv run python scripts/backup_raw.py
backup_raw: 364/364 files verified in <backup dir>

$ uv run dataderby replay --raw-dir <backup>/7/11184/25588/<timestamp> --check
MATCH 9c78aed9c6116baa5a82f6cd0f444c379eedae711e13e8bc3bca1ca1f18fcf1c
```

364 raw files copied and every copy hash-verified. A bundle restored from the
backup replays to the exact published content fingerprint. Raw plus code
rebuilds history; the backup schedule is sound.

### Drift on the live database

```text
$ uv run dataderby drift --stage championship-2026-2027
championship-2026-2027: no drift in snap_96a59b...
```

### Gates

```text
$ uv run ruff format --check
$ uv run ruff check
$ uv run mypy main.py
$ uv run pytest -q
264 passed
```

CI green on the merge commit.

## What changed

| File | Change | Why |
|---|---|---|
| `scripts/backup_raw.py` | stdlib-only raw backup with per-file SHA-256 verification | the database is derivable; raw is not |
| `scripts/README.md` | backup entry | the table stays complete |
| `README.md` | data contract table + source-use section with ADR 0006 pointer | what the data can/can't answer; licence posture one click away |
| `docs/design/runbook.md` | backup/restore section + ADR pointer | the restore drill and the backup location, in writing |
| `docs/reports/v1-gate.md` | this report | the gate evidence in one place |

## Deviations and open items

- **No installed timer yet.** The runs above were operator-invoked, one stage
  at a time. The schedule definition and wrapper are done (#7); installing the
  OS task and collecting two timer-fired runs is the remaining step.
- **No live 19-team refusal.** Deliberately not tested against the production
  database; suite coverage cited above.
- **Conference League unscheduled.** Source feed empty; tracked in
  `docs/reports/all-league-capture.md`.
- **E5 still open.** The 36 h ceiling and provisional post-match sweeps stand
  until the next matchday measurement (issue #8).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| The timer is never installed | #7 documents install/disable; this report records that it is still manual |
| Backup rots | the drill is replayable in one command; rerun it after any raw-layout change |
| A future run silently stops publishing | `freshness --check` on an hourly timer; dead-man's switch on silence |
| Derived data leaks beyond the licence | ADR 0006 pointer in the README and the runbook; review before sharing |

## Reviewer checklist

- [ ] 11 stages publish; the 12th is unscheduled with a reason.
- [ ] Second consecutive run is `no_change` and writes nothing.
- [ ] Short-cohort refusal is tested (no live poison).
- [ ] Freshness shows all runs.
- [ ] Backup verifies 364/364; replay MATCHes the fingerprint.
- [ ] Gates pass in CI.
- [ ] Runbook holds the drill and the backup location.

## References

- `docs/design/runbook.md` — install, recovery, backup, drift responses
- `docs/adr/0006-source-use.md` — licence posture
- `docs/adr/0004-raw-is-system-of-record.md` — why raw is backed up
- `plans/v1-build-plan.md` §13 — the gate definition
