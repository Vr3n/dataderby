# P8 implementation summary

**Date:** 2026-10-26
**Scope:** issues #1, #2, #3
**Detail:** `docs/reports/p8-cli-operations.md`

## In one paragraph

The pipeline now has an operator entry point, a migration ledger, and CI. Before
this change, every module existed but nothing called them in order, the schema could
only change by re-running idempotent files, and "the gates pass" meant "on my
machine". After it, `uv run dataderby run` captures, parses, validates, and
publishes; `replay` rebuilds a candidate from raw bytes and compares fingerprints;
`verify` checks the invariants that the database cannot express; and the four gates
run on Ubuntu and Windows for every push.

## What changed

| Area | Before | After |
|---|---|---|
| Entry point | `main.py` → fixture CLI only | `dataderby` console script and `python -m dataderby`; `main.py` unchanged |
| Schema changes | re-run every `*.sql`, rely on `IF NOT EXISTS` | checksummed ledger; each file applied once; tampering refused |
| Running a stage | write Python | `dataderby run --stage KEY` |
| Inspecting | read DuckDB by hand | `freshness`, `verify`, `stages list` |
| Recovering | no path | `dataderby replay --raw-dir … --check` |
| Proving it | local habit | CI on both operating systems |

## The three decisions worth remembering

1. **Lock before config.** A run that cannot get the lock says so, even if its
   config is also broken. Precedence is part of the contract: exit `5` means "someone
   else is running", not "your file is wrong".
2. **Dry-run uses an in-memory database.** It exercises the real assertions rather
   than a pretend subset, and it cannot leave a file behind. The test asserts the
   database and `data/raw` are absent, not just that the exit code is zero.
3. **Replay compares content, never ids.** Ids are generated; content is the thing
   that must survive a rebuild. This is the same rule P6 already used.

## Evidence

```
uv run ruff format --check   → 82 files already formatted
uv run ruff check            → All checks passed
uv run mypy main.py          → Success: no issues found
uv run pytest -q             → 189 passed
```

CI: both `gates` legs green on `901eb7b` (Ubuntu and Windows).

New tests: 7 for the ledger, 17 for the CLI. The CLI suite runs a real 20-team
candidate through the real assertions and the real publish transaction; only the
page capture and the feed client are injected.

## What this does not claim

- No real WhoScored capture has been parsed. Issue #5 is still the gate on that.
- The timestamp type is still naive `TIMESTAMP` (issue #4). The UTC session pin is
  still load-bearing.
- The fetch policy is unchanged: no 429/`Retry-After` branch yet (issue #6).
- Nothing is scheduled and nothing alerts (issue #7).

## Next

In order: the timestamp decision (#4), one real capture (#5), the fetch policy
(#6), then the schedule (#7) and the v1 gate (#9).
