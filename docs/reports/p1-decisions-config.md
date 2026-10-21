# P1 - Decisions and stage registry

**Status:** complete
**Date:** 2026-10-21
**Plan:** `plans/v1-build-plan.md` §4

## Goal

Write down the decisions that the schema depends on, and load the 2026/27 stage
registry from a validated file rather than from constants scattered through the
code.

## Decisions

| ADR | Decision |
|---|---|
| [0001](../adr/0001-history-model.md) | Immutable snapshot header, per-team facts, and an edge-based idempotency rule. |
| [0002](../adr/0002-precision.md) | Store source precision; round only at presentation. |
| [0003](../adr/0003-two-clocks.md) | `observed_at` orders history; `accepted_at` is audit-only. |
| [0004](../adr/0004-raw-is-system-of-record.md) | Raw captures are the recovery source; DuckDB is derived. |
| [0005](../adr/0005-duckdb-as-store.md) | DuckDB, one writer, explicit rollback, escaped-literal bulk inserts. |
| [0006](../adr/0006-source-use.md) | The owner accepted the source use for this local, private pipeline. |

## Stage registry

`config/stages.toml` contains all twelve measured 2026/27 competitions:

| Key | Teams | Declared format |
|---|---:|---|
| `epl-2026-2027` | 20 | `league` |
| `championship-2026-2027` | 24 | `league`, `playoff` |
| `efl-league-one-2026-2027` | 24 | `league`, `playoff` |
| `efl-league-two-2026-2027` | 24 | `league`, `playoff` |
| `la-liga-2026-2027` | 20 | `league` |
| `serie-a-2026-2027` | 20 | `league` |
| `bundesliga-2026-2027` | 18 | `league` |
| `ligue-1-2026-2027` | 18 | `league` |
| `eredivisie-2026-2027` | 18 | `league` |
| `champions-league-2026-2027` | 36 | `league`, `knockout`, `final` |
| `europa-league-2026-2027` | 36 | `league`, `knockout`, `final` |
| `conference-league-2026-2027` | 27 | `league`, `knockout`, `final` |

`expected_stages` is a declaration about the season, not a claim that every
stage id is already known. The registry currently contains the league stage for
every competition; knockout, play-off, and final ids are added only after they
are observed.

## Loader behaviour

`src/dataderby/config.py` exposes:

- `StageSpec`: frozen, `extra="forbid"`, with a WhoScored URL prefix check and a
  check that the configured `stage` is present in `expected_stages`.
- `Settings`: the three default paths plus a stage map keyed by `key`.
- `load_stages(path)`: parses `[[stage]]`, rejects duplicate keys, duplicate
  `whoscored_stage_id` values, duplicate addresses, and inconsistent
  `expected_stages` within one `(tournament, season)`.
- `load_settings(path)`: reads `[settings]` and delegates stage parsing to the
  same function.

The numeric identifiers are named `whoscored_stage_id`,
`whoscored_season_id`, and `whoscored_tournament_id`. Measurements such as
`expected_teams` remain unprefixed because they do not claim a source.

## Verification

`tests/test_config.py` covers:

- a valid stage and the real repository registry;
- a missing field, with the field name in the error;
- an unknown field rejected by `extra="forbid"`;
- duplicate key and duplicate stage id;
- inconsistent `expected_stages` in one season;
- a stage code absent from its expected list;
- a non-WhoScored URL;
- `[settings]` path loading;
- the twelve real stages and unique stage ids.

Run on 2026-10-21:

```text
uv run ruff format --check
41 files already formatted

uv run ruff check
All checks passed!

uv run mypy main.py
Success: no issues found in 1 source file

uv run pytest
37 passed in 3.77s
```

## Open items

- Conference League reports 27 teams against a 108-match calendar. The count is
  measured; the format anomaly still needs a fixtures-page check before the
  first live scrape.
- The 2026/27 knockout stage granularity is unobserved. The registry declares
  `knockout`/`final` but stores no id for them.
- The no-CI condition from P0 still applies; all gates are local.

## Next

P2: the 60/30-column contract, ownership map, and golden column-order tests.
