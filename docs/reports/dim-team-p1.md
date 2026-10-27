# Dim team P1 (006, backfill, archived split)

**Status:** complete
**Date:** 2026-10-27
**Decision:** `docs/adr/0011-team-stage-dimensions.md` (team half)
**Plan:** `docs/reports/dim-tables-plan.md`

## Goal

Land the team half of the dims plan without touching publishing or views:
one canonical row per club, one mapping row per WhoScored team, an idempotent
backfill, and an archived/active split so future history seasons never pollute
the schedule or freshness. Stage dims (007) and view cutover stay in P2.

## What changed

| File | Change | Why |
|---|---|---|
| `sql/006_dim_team.sql` | `dim_team` + `team_source_key`, PK/UNIQUE/FK as designed | Canonical identity plus per-source mappings; keys are the guarantee |
| `src/dataderby/dims.py` | `mint_team_id`, `backfill_team_dims`, `unmapped_teams` | One module owns team identity; backfill reruns add zero rows |
| `src/dataderby/config.py` | `StageSpec.active: bool = True` | Registry marks archived seasons; scheduler skips them, explicit runs still work |
| `src/dataderby/cli.py` | `run`/`probe`/`drift` default to active stages; `stages list` shows ACTIVE; `freshness --check` evaluates active stages only; new `dims backfill` command | Polling set vs explicit set; freshness stays meaningful with archived history present |
| `tests/test_dims.py` | 13 tests | Pins DDL, backfill counts, idempotence, key guarantees, active filtering, freshness skip, CLI command |
| `docs/reports/dim-team-p1.md` | This report | AGENTS.md: one report per non-phase change |
| `docs/reports/README.md` | Index row | Keep the index complete |

No change to `config/stages.toml`: all 11 live stages default to active. Facts,
headers, views, and assertions are untouched, so current output is
byte-identical.

## Design decisions

- Canonical ids are minted (`dtm_` + 12 hex), never derived from WhoScored ids:
  a StatsBomb-first club later needs an id with no WhoScored value to derive
  from, and uuids never collide across writers.
- Backfill names come from fact rows and `first_seen_at` from the earliest
  accepting snapshot: verified stable (no id maps to two names in the live 221).
- `dims backfill` reruns inside the pipeline lock after `migrate`, and reports
  coverage; anything left unmapped exits non-zero rather than silently passing.
- `freshness --check` filters to active registry addresses; plain display still
  shows every stage so operators see archived state.

### Rejected alternatives

- **Deriving `dtm_{whoscored_id}`.** Breaks for source-first clubs and leaks the
  source key into the canonical namespace.
- **Backfilling canonical ids onto facts in P1.** Publish-time wiring and view
  cutover belong to P2 with 007; P1 keeps facts byte-identical and shippable.
- **A separate archived registry file.** One `active` flag keeps a single source
  of truth for stage addresses and survives `load_settings` validation.

## Test matrix

| Test | Pins |
|---|---|
| `test_migration_006_creates_dim_tables` | 006 applies with 001-005; both tables exist |
| `test_backfill_maps_every_fact_team_once` | shared club (2 snapshots) gets 1 dim row; 2 teams, 2 mappings |
| `test_backfill_is_idempotent` | rerun adds (0, 0); count stable |
| `test_double_mapping_is_rejected` | duplicate (source, id) and duplicate (canonical, source) fail |
| `test_unmapped_teams_lists_new_facts` | new fact team surfaces as a gap |
| `test_mint_team_id_shape` | `dtm_` + 12 hex, unique |
| `test_active_defaults_to_true` / `test_active_false_parses` | registry flag behaviour |
| `test_run_without_stage_skips_archived` | default run sweeps active only |
| `test_run_with_explicit_stage_still_runs_archived` | explicit `--stage` overrides the skip |
| `test_freshness_check_skips_archived` | stale archived + fresh active passes check |
| `test_freshness_check_flags_stale_when_active` | same staleness with stage active fails check |
| `test_dims_backfill_command` | CLI maps 20 teams, reports 100%, rerun adds zero |

Deliberately not asserted: StatsBomb mapping values (no fixture exists);
view output changes (none by design).

## Evidence

```text
$ uv run pytest tests/test_dims.py tests/test_config.py tests/test_migrations.py -q
30 passed in 36.44s
$ uv run pytest tests/test_pipeline_cli.py tests/test_cli.py tests/test_schedule.py tests/test_publish.py -q
54 passed in 117.75s (0:01:57)
$ uv run ruff format --check
122 files already formatted
$ uv run ruff check
All checks passed!
$ uv run mypy main.py
Success: no issues found in 1 source file
```

Full-suite gate (`uv run pytest -q`, 233 passed) ran green before P1 on the
same tree; P1 adds 13 tests and changes no existing behaviour.

Live warehouse backfill (`dataderby dims backfill`, 27 Oct 2026):

```text
dim_team: 221 teams, 221 mappings added
coverage: 100% (221 teams mapped)
```

Verified after: `dim_team` 221, `team_source_key` 221, unmapped 0,
`schema_migration` lists 001-006, `v_latest_team_with_standings` still 258.

## Deviations and open items

- P2 still owns: `007_dim_stage.sql`, canonical columns on facts/headers,
  publish-time wiring, A23/A24, view cutover (plan deck slides 07-08).
- EPL 1999-2000 pilot capture not started; needs the human stage-id discovery
  pass first.
- The `dims backfill` leftover-gap branch (`INTERNAL`) is defensive: current
  backfill maps everything it finds, so it cannot trigger without a concurrent
  writer, which the lock excludes.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Archived stage runs by default somewhere | `_keys` is the single choke point; both run paths and probe/drift share it |
| Hand-mapped team row edited later | mappings change by script; ledger pattern carries over from migrations |
| Rename breaks canonical_name trust | weekly drift query is P2; `updated_at` already recorded |

## Reviewer checklist

- [ ] 006 matches ADR 0011 DDL.
- [ ] No existing test modified; stages-list change is additive (existing test passes).
- [ ] `stages.toml` untouched; all live stages stay active by default.
- [ ] Index and report links updated.

## References

- Plan: `docs/reports/dim-tables-plan.md`, deck `docs/slides/dim-tables-plan-slides.html`
- ADR: `docs/adr/0011-team-stage-dimensions.md`
- SQL: `sql/006_dim_team.sql`; code: `src/dataderby/dims.py`
