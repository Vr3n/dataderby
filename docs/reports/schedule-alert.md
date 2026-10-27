# Schedule and freshness alert

**Status:** complete
**Date:** 2026-10-27
**Issue:** #7
**Design:** `docs/design/runbook.md`

## Goal

`v_pipeline_freshness` computed `age_seconds`, but nothing ran the pipeline on
a timer and nothing read the view. A freshness number nobody watches is a
dashboard, not an alert. Done means the run happens unattended, a failure
alerts, an absence alerts through a different detector, and an operator can
install, disable, and recover the schedule from one page.

## What changed

| File | Change | Why |
|---|---|---|
| `src/dataderby/schedule.py` | `evaluate_freshness`, `ping_heartbeat`, `run_scheduled`, `STALE_AFTER_HOURS = 36.0` | the timer logic, testable without a clock, a database, or a network |
| `src/dataderby/cli.py` | `freshness --check --max-age-hours` | the absence detector: exits `6` when any stage is stale |
| `scripts/scheduled_run.py` | stdlib-only wrapper: run, ping on success, alert on any non-zero exit | the one command the timer calls |
| `scripts/README.md` | wrapper entry | the table stays complete |
| `docs/design/runbook.md` | install, disable, thresholds, exit codes, recovery, evidence locations | the operator page issue #7 asked for |
| `tests/test_schedule.py` | 18 tests | the staleness policy, the wrapper contract, and the CLI paths |

## Design decisions

### Stale means never-succeeded or older than the ceiling

A stage with `last_success_at IS NULL` has `age_seconds IS NULL`; it is stale
because it never produced a snapshot, not because the arithmetic is missing.
An age exactly at the ceiling is fresh: the ceiling is a grace period. This is
pinned by `test_an_age_exactly_at_the_ceiling_is_still_fresh`.

### The ceiling is 36 hours and says so

The daily heartbeat runs every 24 h, so 36 h tolerates one missed run plus a
slow retry. The number is provisional until E5 measures the real publication
lag; the CLI help, the runbook, and `test_provisional_ceiling_is_36_hours` all
carry that warning. A test pins the constant so the replacement is a deliberate
diff, not drift.

### A stale check exits 6

Exit codes are fixed by `plans/v1-build-plan.md` §11, so no new code was added.
`6` is "internal failure, or a verification mismatch": a stale stage is a
verification mismatch between the schedule's promise and the database. The
default `freshness` output is byte-identical to before; `--check` adds a
`STATUS` column (human) and `stale` + `max_age_seconds` keys (JSON) only.

### Two detectors, not one

A failure alert cannot fire if the scheduler dies, so the run pings a
dead-man's-switch monitor on success and the monitor alerts on silence. The
ping uses only the standard library — no new dependency, per the project rule.
Without a URL the wrapper logs that it skipped the ping and still exits `0`;
a failed ping never rewrites the run's outcome.

### Exit 5 alerts

A held lock at the scheduled time means the previous run overran. That is a
signal, not a retry hint, so `run_scheduled` alerts on every non-zero exit
including `5`. Pinned by `test_a_held_lock_alerts_like_any_other_failure`.

### Rejected alternatives

- **A new exit code for stale.** The plan fixes the codes; reusing `6` keeps the
  contract stable.
- **An orchestrator (Airflow/Dagster).** One pipeline, one schedule, one
  writer. Add one with a second source or a cross-pipeline dependency.
- **An external monitoring dependency.** The ping is a stdlib HTTP call to an
  operator-chosen URL; nothing is installed.
- **Hardcoding the E5 threshold now.** E5 has not run. A generous ceiling plus a
  named replacement is honest; a precise-looking number would be invented.

## Test matrix

| Test | Pins |
|---|---|
| `test_provisional_ceiling_is_36_hours` | the ceiling value, so replacing it is deliberate |
| `test_a_never_successful_stage_is_stale` | `NULL` age is stale |
| `test_an_age_past_the_ceiling_is_stale` / `..._exactly_at_the_ceiling_is_still_fresh` / `test_a_recent_success_is_fresh` | the boundary |
| `test_mixed_stages_keep_their_order_and_flags` | per-stage verdicts, order preserved |
| `test_a_2xx_ping_is_a_success` / `test_a_failed_ping_never_raises` / `test_a_non_2xx_ping_is_a_failure` | ping never masks the run |
| `test_a_successful_run_pings_and_never_alerts` / `test_a_failed_run_alerts_and_never_pings` | the wrapper contract |
| `test_a_held_lock_alerts_like_any_other_failure` | exit `5` alerts |
| `test_freshness_check_passes_on_a_recent_success` | exit `0`, `0 of 1 stages stale` |
| `test_freshness_check_fails_on_a_stale_stage` | exit `6` on a 2020 timestamp (absence alert) |
| `test_freshness_check_fails_when_a_stage_never_succeeded` | exit `6` on `NULL` |
| `test_freshness_check_json_marks_each_stage` | `stale` + `max_age_seconds` keys |
| `test_freshness_check_rejects_a_non_positive_ceiling` | bad ceiling is exit `4` |
| `test_freshness_without_check_is_unchanged` | default output has no `STATUS`/`STALE` |

## Evidence

```text
$ uv run ruff format --check
$ uv run ruff check
$ uv run mypy main.py
$ uv run pytest -q
```

(Full output recorded at commit time.)

Simulated alerts without touching the live database: a checkpoint row with a
2020 `last_success_at` exits `6`; a bad stage key exits `4`:

```text
$ uv run dataderby freshness --check --config <tmp>
... STALE ... 1 of 1 stages stale (older than 36 h)
exit=6
```

## Deviations and open items

- **No live scheduled runs yet.** The timer is documented but not installed;
  the two-consecutive-runs evidence belongs to #9 (v1 gate).
- **No E5 threshold.** The 36 h ceiling stands until issue #8 measures p95.
- **Heartbeat URL is an operator choice, not code.** No monitor is configured
  in this change.
- **Post-match `+2 h`/`+6 h` sweeps need fixture knowledge.** The wrapper takes
  `--stage`; selecting "competitions with a fixture in the last 24 h" is still
  manual until the fixture calendar exists.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| The timer dies silently | dead-man's switch alerts on missing pings |
| A stale alert is ignored | exit `6` is machine-readable; hourly check recommended |
| The 36 h ceiling is wrong | named provisional; E5 replaces it |
| Overlapping runs corrupt state | single-writer lock; exit `5` alerts instead of overlapping |
| Alert fatigue from WARNs | WARNs never affect the exit code; only real failures alert |

## Reviewer checklist

- [ ] Default `freshness` output is unchanged.
- [ ] `--check` exits `6` on stale, `0` on fresh.
- [ ] `NULL` success is stale; exact-ceiling age is fresh.
- [ ] Wrapper preserves the run's exit code in all paths.
- [ ] No new dependency was added.
- [ ] Runbook covers install, disable, thresholds, exit codes, recovery.
- [ ] The index is updated.

## References

- `docs/design/runbook.md`
- `docs/research/whoscored-cadence.md` — provisional cadence and E5 plan
- `src/dataderby/schedule.py`, `scripts/scheduled_run.py`
- `plans/v1-build-plan.md` §11 (exit codes), §13 (v1 gate)
