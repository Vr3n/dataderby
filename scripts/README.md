# Operator scripts

These are run by a human, not imported by the package. They are allowed to touch
the network and to write under `data/`, which normal code is not.

| Script | What it does | Writes | Safe to run in CI? |
|---|---|---|---|
| `audit_all_stages.py` | Captures every configured stage, validates all nine feeds, publishes each into a scratch database, records failures and continues. | `data/live-audit/<timestamp>/` (git-ignored) | No — needs the live source and a browser. |
| `capture_live_stage.py` | Captures one stage and writes a redacted fixture for tests. | The chosen fixture directory (committed only after review). | No. |
| `discover_stages.py` | Dumps the `#stages` dropdown (value + label) for given season URLs. | Nothing (stdout only) | No — needs the live source and a browser. |
| `discover_epl_seasons.py` | Reads the tournament seasons dropdown, visits each season, records the stage show URL and stage tabs. Prints JSON. | Nothing (stdout only) | No — needs the live source and a browser. |
| `dagster.ps1` | Starts the Dagster UI for the fixture-calendar pipeline. | `data/dagster/` | No. |
| `check_robots.py` | Fetches `robots.txt` and prints its status, date, SHA-256, and body. | Nothing | No — one network request. |
| `scheduled_run.py` | Runs `dataderby run`, pings the heartbeat monitor on success, alerts on any non-zero exit. | Nothing outside the pipeline's own paths | No — runs the live pipeline. |
| `backup_raw.py` | Copies `data/raw/` to a second location and verifies every file by SHA-256. | The backup destination | No — needs real raw bundles. |

## Rules

- A script is not production code. If logic is needed by the pipeline, move it
  into `src/dataderby/` and call it from there.
- Every script here needs a short docstring, a `--help`, and an entry in this
  table.
- Anything that writes raw source data must write under `data/`, never under
  `docs/` or `src/`.
- Fixtures produced by `capture_live_stage.py` are redacted and reviewed before
  they are committed. See `tests/fixtures/whoscored/README.md`.

## Common commands

```bash
# all twelve stages, into data/live-audit/<timestamp>/
uv run python scripts/audit_all_stages.py --out data/live-audit

# one stage, into a fixture directory
uv run python scripts/capture_live_stage.py \
  --stage epl-2026-2027 \
  --out tests/fixtures/whoscored/epl-2026-2027-25544
```
