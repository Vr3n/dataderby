# Runbook: schedule, freshness, and recovery

**Status:** operational from 2026-10-27. Thresholds are provisional until
experiment E5 measures the real publication lag (issue #8).

## What runs on a timer

One command, once a day, plus post-match sweeps. OS-level scheduling is enough:
one pipeline, one schedule, one writer. No orchestrator until a second source
or a cross-pipeline dependency exists.

| When | What | Why |
|---|---|---|
| `06:00 IST` daily | `uv run python scripts/scheduled_run.py --config config/stages.toml` | catches overnight results, late corrections, multi-day moves |
| last kickoff `+2 h` and `+6 h` | same command, only for competitions with a fixture in the last 24 h | provisional: catch the result and any late correction; E5 replaces the offsets with a measured p95 |

## Install

Windows Task Scheduler, daily at 06:00 IST:

```powershell
$action = New-ScheduledTaskAction -Execute "uv" `
  -Argument "run python C:\Users\Viren\codes\dataderby\scripts\scheduled_run.py --config C:\Users\Viren\codes\dataderby\config\stages.toml" `
  -WorkingDirectory "C:\Users\Viren\codes\dataderby"
$trigger = New-ScheduledTaskTrigger -Daily -At 06:00
Register-ScheduledTask -TaskName "dataderby-daily" -Action $action -Trigger $trigger
```

cron elsewhere (06:00 IST = 00:30 UTC):

```cron
30 0 * * * cd /opt/dataderby && uv run python scripts/scheduled_run.py --config config/stages.toml >> data/logs/scheduler.log 2>&1
```

The task must run as a user with a desktop session or a virtual display: the
feed only answers inside the site's own browser page (issue #14).

## Disable

```powershell
Disable-ScheduledTask -TaskName "dataderby-daily"
```

```cron
# comment out the dataderby line in crontab -e
```

Disabling the timer is the expected response to a source outage: it stops
burning the request budget while keeping the database queryable.

## Freshness and thresholds

`dataderby freshness --check` marks every stage `STALE` or `fresh` against a
ceiling and exits `6` when any stage is stale:

```bash
uv run dataderby freshness --check --config config/stages.toml
uv run dataderby freshness --check --max-age-hours 12 --json --config config/stages.toml
```

The default ceiling is **36 hours**: the daily heartbeat runs every 24 h, so
36 h tolerates one missed run plus a slow retry. A stage that never succeeded
(`last_success_at` is `NULL`) is always stale. An age exactly at the ceiling is
still fresh; the ceiling is a grace period, not a tripwire. Replace the number
with last-kickoff-plus-p95 once E5 reports.

Run the check on its own timer (for example hourly) and alert on a non-zero
exit. That is the absence detector: it fires when runs stop happening, which a
failure alert cannot catch.

## Alerts

Two different failures, two different detectors:

| Failure | Detector | Signal |
|---|---|---|
| the run fails | `scheduled_run.py` | alert line on stderr, optional POST to `DATADERBY_ALERT_URL`; the run's exit code is preserved |
| the scheduler dies | dead-man's switch | `scheduled_run.py` pings `DATADERBY_HEARTBEAT_URL` on success; the monitor alerts when no ping arrives in the window |

Set the heartbeat URL in the task environment:

```powershell
$env:DATADERBY_HEARTBEAT_URL = "https://monitor.example/ping/dataderby"
```

Without a URL the script logs `ok (no heartbeat URL set, skipping ping)` and
still exits `0`. A failed ping never changes the run's outcome.

## Exit codes

Fixed by `plans/v1-build-plan.md` §11:

| Code | Meaning | First response |
|---|---|---|
| `0` | ok, or `no_change` | none; check the WARN lines |
| `2` | a feed could not be fetched | read the stderr line; check the source and the request budget |
| `3` | publish or parse was blocked | read which assertion id; a BLOCK is a data problem, a WARN is not |
| `4` | configuration or usage | fix the invocation; includes a bad stage key and a bad `--max-age-hours` |
| `5` | another process holds the lock | the previous run overran; treat as a failure signal, not a retry hint |
| `6` | internal failure, or a verification mismatch | includes `freshness --check` finding a stale stage |

## Recovery

| Situation | Action |
|---|---|
| stale stage | run `dataderby run --stage <key>` by hand, then `freshness --check` to confirm |
| blocked run (`3`) | read the assertion id in stderr; fix the data or the rule, never delete the test |
| crashed run | `dataderby verify` to find the half-written state; `reconcile` repairs the ledger on the next run |
| locked (`5`) | do not delete the lock file while a run may be alive; wait, then check the process |
| source outage | disable the timer; the database stays queryable; re-enable and run once by hand |

## Post-publish drift checks

Assertions run before commit. `dataderby drift` runs after: it compares the
newest committed snapshot of each stage with its predecessor and reports what
changed. A finding never rolls back the commit and never blocks the next run.

```bash
uv run dataderby drift --config config/stages.toml
uv run dataderby drift --stage epl-2026-2027 --config config/stages.toml
```

`scripts/scheduled_run.py` runs `drift` automatically after every accepted run
and routes `DRIFT` lines to the alert channel. The findings are also written to
the JSONL log as `drift.check` events.

| Check | Catches | Expected response |
|---|---|---|
| `row_count` | a sweep that published fewer teams than the previous snapshot | compare with the source table; a real relegation/promotion boundary needs a registry update, anything else is a source or parse problem |
| `team_set` | a renamed or swapped `whoscored_team_id` | confirm the id on the source page; fix the parse or record the rename |
| `null_rate` | a source column that silently went empty (null fraction up > 0.10) | check the feed payload; a widened gate page looks exactly like this |
| `observed_lag` | a snapshot accepted > 6 h after it was observed | check for a stuck run or a replayed old bundle |
| `baseline` | the snapshot is unknown, not newest, or the first for its stage | not drift; informational only |

Thresholds live in one table, `THRESHOLDS` in `src/dataderby/drift.py`.
Distribution drift (a units change that keeps the shape valid) is not checked:
season measures are cumulative, so any fixed threshold false-positives every
matchday. It needs a baselined rate-of-change model first.

## Backup and restore

Back up the irreplaceable layer, not the derived one. `data/raw/` holds the
only copy of what the source said; the `.duckdb` file can be rebuilt from it
with `replay`. The first instinct on call is to back up the database. Do not.

```powershell
$env:DATADERBY_BACKUP_DIR = "D:\dataderby-backup"
uv run python scripts/backup_raw.py
```

Run it on the same timer as the daily heartbeat (after the run), or at least
daily. The script copies every raw file with its SHA-256 sidecar and verifies
each copy by hash; it exits `1` on any mismatch.

Restore drill (do this once, write the result in the v1-gate report):

```powershell
# 1. pick one raw bundle from the backup
# 2. replay it into a scratch database and compare fingerprints
uv run dataderby replay --run-id <run_id> --raw-dir <backup>/<bundle> --check
```

A replay that prints the published content fingerprint proves the backup is
sufficient: raw plus code rebuilds history. If the drill ever fails, the
backup schedule is broken, not the database.

The source-use licence posture is one click away at all times:
[`docs/adr/0006-source-use.md`](../adr/0006-source-use.md). Raw bundles are
kept, not republished; derived data stays inside this pipeline until that ADR
is reviewed.

## Where the evidence lives

- Run ledger: `ingestion_run` table (`running` → `accepted` / `no_change` / `blocked` / `failed`).
- Raw bundles: `data/raw/<tournament>/<season>/<stage>/<timestamp>/` with SHA-256 sidecars.
- JSON-lines logs: `data/logs/<UTC date>.jsonl`, including `publish.warning` lines.
- Freshness: `v_pipeline_freshness` (`age_seconds`, `last_outcome`, `attempt_count`).
- Scheduler output: `data/logs/scheduler.log` (cron) or the Task Scheduler history tab.
