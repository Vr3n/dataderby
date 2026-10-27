# Post-publish drift checks

**Status:** complete
**Date:** 2026-10-27
**Issue:** #11
**Design:** `docs/design/runbook.md` (drift section)

## Goal

Assertions A1–A22 run before commit, so they protect the warehouse from a bad
write. Nothing ran after commit, so a bad state that passed the assertions was
invisible until a consumer noticed. Done means each accepted snapshot is
compared with its predecessor, findings are recorded and alerted, and no
finding can roll back a commit or block the next run.

## What changed

| File | Change | Why |
|---|---|---|
| `src/dataderby/drift.py` | `check_drift`, `record_drift`, `THRESHOLDS` | the four checks plus the JSONL event, in one testable module |
| `src/dataderby/cli.py` | `dataderby drift [--stage] [--snapshot]` | the operator surface; always exits `0` on a readable database |
| `scripts/scheduled_run.py` | post-run `drift` invocation with alert routing | drift reaches the alert channel without touching the run's exit code |
| `docs/design/runbook.md` | drift section with the response table | each check names its expected response |
| `tests/test_drift.py` | 13 tests | every check has a firing fixture and a passing fixture |

## Design decisions

### Four checks, not five

The issue lists row count, team set, null rate, distribution drift, and
freshness. Freshness already exists (`freshness --check`, issue #7), so it is
wired, not rebuilt. Distribution drift is deferred with the reason in the
module docstring: season measures are cumulative, so means grow legitimately
and any fixed threshold false-positives every matchday. The fourth
implemented check is `observed_lag` (accepted long after observed), which is
the commit-time half of the freshness question.

### The baseline rule matches `v_latest_*`

Newest-first by `observed_at`, then `accepted_at`, then `snapshot_id`. A first
snapshot has no baseline and returns no findings. A non-newest snapshot is
reported, not compared backwards: comparing old-vs-new inverts every delta.

### Exit 0, always

Drift output goes to stdout (`DRIFT <check>: <detail>`) and to the JSONL log
as `drift.check` with the snapshot id, stage key, and findings. The command
exits `0` because a finding must not block the next run. The scheduled wrapper
routes `DRIFT` lines to the alert channel separately, so visibility does not
depend on the exit code.

### Thresholds in one table

`THRESHOLDS = {"null_rate_delta_max": 0.10, "observed_lag_hours_max": 6.0}`.
Row count and team set are exact-match: any difference is drift. The null-rate
delta ignores wobbles below 0.10 (pinned by a 20-team fixture with one NULL).

### Rejected alternatives

- **Rolling back on drift.** A committed snapshot is history; deleting it
  rewrites what the pipeline saw. Record, alert, leave it in place.
- **Blocking the next run on drift.** The next observation is the evidence a
  human needs. Blocking destroys it.
- **A fixed distribution threshold.** Cumulative measures make it a
  false-positive generator. Deferred until a rate-of-change baseline exists.
- **Reusing the assertion framework.** Assertions read staged candidates and
  block; drift reads committed snapshots and reports. Different inputs,
  different verbs, different module.

## Test matrix

| Test | Pins |
|---|---|
| `test_thresholds_live_in_one_table` | the threshold names and values |
| `test_identical_snapshots_have_no_drift` | the passing fixture |
| `test_a_first_snapshot_has_no_baseline` | no history, no findings |
| `test_a_dropped_team_fires_row_count_and_team_set` | count + set with `added`/`removed` evidence |
| `test_a_swapped_team_fires_team_set_without_row_count` | same count, different set |
| `test_a_column_going_empty_fires_null_rate` | `0.00->1.00` with the column named |
| `test_a_small_null_wobble_does_not_fire` | 1 NULL in 20 rows is below the delta |
| `test_a_snapshot_accepted_late_fires_observed_lag` | 11 h lag fires; a prompt accept does not |
| `test_an_unknown_snapshot_reports_no_baseline` | unknown id is informational |
| `test_a_non_newest_snapshot_is_not_compared_backwards` | old snapshot is informational |
| `test_record_drift_writes_a_jsonl_event` | `drift.check` event shape |
| `test_drift_command_reports_no_drift_and_logs` | CLI pass path + log |
| `test_drift_command_reports_findings_without_blocking` | CLI reports `DRIFT` lines and exits `0` |

## Evidence

```text
$ uv run ruff format --check
$ uv run ruff check
$ uv run mypy main.py
$ uv run pytest -q
```

(Full output recorded at commit time.)

## Deviations and open items

- **Distribution drift is deferred**, with the reason documented in code, the
  runbook, and this report.
- **No live drift finding yet.** The checks run against fixtures here; the
  first real finding will come from scheduled runs.
- **The wrapper's drift routing is glue.** Detection logic is unit-tested in
  `src`; the subprocess grep in `scripts/` is covered by the CLI tests' output
  contract (`DRIFT` lines on stdout).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| A real squad change fires `team_set` every season | expected at season boundaries; the registry update is the response |
| Alert fatigue | findings are per-stage and specific; exit code stays `0` |
| A drifted snapshot misleads a consumer | the finding is in the log before the next run; a human decides |
| Thresholds are wrong | one table, one test, named values |

## Reviewer checklist

- [ ] Each check has a firing and a passing fixture.
- [ ] `drift` exits `0` with findings present.
- [ ] Findings reach the JSONL log and stdout.
- [ ] The baseline order matches `v_latest_*`.
- [ ] Distribution deferral is documented in all three places.
- [ ] The runbook names the response for each check.
- [ ] The index is updated.

## References

- `src/dataderby/drift.py`
- `docs/design/runbook.md` — drift section
- `docs/reports/schedule-alert.md` — the alert channel drift routes into
