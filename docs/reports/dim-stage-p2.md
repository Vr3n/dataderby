# Dim stage P2 (007-009, publish wiring, view cutover)

**Status:** complete
**Date:** 2026-10-27
**Decision:** `docs/adr/0011-team-stage-dimensions.md` (fully built)
**Plan:** `docs/reports/dim-tables-plan.md` (P1-P3 rollout)
**Branch:** `p2-dim-stage-cutover`

## Goal

Finish the dims plan: canonical ids on every header and fact, A23/A24 guarding
resolution, and the four latest/history views exposing the canonical team name.
Publishing keeps working unchanged for operators; the only new step is
`dims backfill`, and views gain additive columns only.

## What changed

| File | Change | Why |
|---|---|---|
| `sql/007_dim_stage.sql` | `dim_stage`, `stage_source_key`, nullable canonical columns on the header and both fact tables | Stage identity plus the join keys; nullable so old rows and new publishes converge without a rewrite |
| `sql/008_assertions_dims.sql` | A23 (team resolves), A24 (stage resolves), both BLOCK | The resolution guarantee in the assertion vocabulary; fires on real inconsistency |
| `sql/009_views_dims.sql` | Redefines 4 views with `canonical_team_name` via LEFT JOIN | Consumers read canonical names without rejoining; no existing column touched |
| `src/dataderby/dims.py` | Stage mint/ensure/backfill, canonical fill, unmapped stages, shared `ensure_team_mapping` | One module owns all identity writes; backfills are idempotent |
| `src/dataderby/publish.py` | Ensure-then-assert: stage + team ids resolved pre-assertions, stored on header and facts | Bootstrap paradox (below) makes ensure-before-assert the only coherent order |
| `src/dataderby/cli.py` | `dims backfill` covers registry stages first, then warehouse leftovers, then fill; new `dims map-stage`; `dims map-team` unchanged; dry-run ensures dims in memory | Registry names always win; curation has both team and stage paths |
| `tests/test_dims_p2.py` | 14 tests | Pins 007, backfills, ensure-before-assert, A23/A24 firing and passing, CLI curation, views, registry-name priority |
| `tests/test_assertions.py` | Fixture seeds dims; id-set test includes A23/A24 | Clean candidate needs mappings to stay clean |
| `tests/test_publish.py` | Direct `insert_facts` call passes canonical ids | New required parameter |
| `docs/reports/dim-stage-p2.md` | This report | AGENTS.md: one report per non-phase change |
| `docs/reports/README.md` | Index row | Keep the index complete |

`config/stages.toml` untouched. Existing fact/header columns untouched.

## Design decisions

- **Ensure-before-assert in publish.** A first publish cannot be blocked on
  unknown mappings: no facts exist yet to backfill from, so blocking would make
  every new stage unpublishable without manual mapping. Source ids are stable,
  so insert-if-missing is mechanical; curation owns names (drift review),
  renames (update), and second sources (manual rows). A23/A24 verify
  post-ensure and fire on real inconsistency (deleted mapping, failed ensure).
- **Registry names win in backfill.** `dims backfill` ensures configured stages
  with real names first; warehouse-only leftovers get `unmapped-{stage}` codes.
  This fixed a live bug found during cutover: placeholders had won for all 11
  stages and were repaired.
- **No NOT NULL on the new columns.** DuckDB's FK handling makes in-place
  parent updates painful; A23/A24 plus the publish path enforce presence
  instead. Nullable also keeps the rollout shippable per phase.
- **Views are additive only.** `canonical_team_name` appended; row counts
  identical (258/258/258/258 live).

### Rejected alternatives

- **Strict block-on-unknown in publish.** Correct-looking, unusable: the first
  publish of any stage has no mappings by construction.
- **Backfill-only mapping creation.** Leaves new publishes unmapped when the
  backfill is forgotten; publish-time ensure closes the gap.
- **Rewriting history rows.** Old rows keep their values; `fill_canonical_ids`
  only fills NULLs.

## Test matrix

| Test | Pins |
|---|---|
| `test_007_creates_stage_tables_and_canonical_columns` | 007 applies with 001-006; tables + columns exist |
| `test_backfill_stage_dims_counts` | 2 stages seed 2+2 rows; rerun adds 0 |
| `test_fill_canonical_ids_writes_old_rows` | NULL rows fill; rerun stable |
| `test_publish_writes_canonical_ids` | header + 20 facts carry ids; stage id matches key table |
| `test_canonical_ids_are_stable_across_snapshots` | second snapshot reuses team ids |
| `test_a23_fires_when_a_mapping_is_missing` | deleted team mapping blocks |
| `test_a24_fires_when_the_stage_mapping_is_missing` | deleted stage mapping blocks |
| `test_clean_candidate_passes_a23_and_a24` | seeded dims pass |
| `test_assertion_contract_includes_a23_a24` | loader sees 25 definitions, no duplicates |
| `test_map_team_cli_curates_a_new_club` | curation path writes dim + key |
| `test_map_stage_cli_curates_a_stage` | curation path writes stage dim + key |
| `test_views_expose_canonical_names` | 20/20 names on latest + history; joined view intact |
| `test_dims_backfill_uses_registry_names` | proper names beat placeholders |
| `test_dims_backfill_maps_stages_and_fills_ids` | end-to-end fill, zero NULLs left |

Existing suites updated, none weakened: assertion id-set extended, one
`insert_facts` call site updated for the new parameter, assertion/publish
fixtures seed dims.

## Evidence

```text
$ uv run pytest tests/test_dims_p2.py tests/test_dims.py -q
27 passed in 71.12s
$ uv run pytest tests/test_publish.py tests/test_assertions.py tests/test_config.py tests/test_migrations.py tests/test_views.py tests/test_contract.py -q
89 passed in 195.16s
$ uv run pytest tests/test_pipeline_cli.py tests/test_cli.py tests/test_schedule.py -q
41 passed (after dry-run dims seeding; 2 needed the fix, then green)
$ uv run ruff format --check
124 files already formatted
$ uv run ruff check
All checks passed!
$ uv run mypy main.py
Success: no issues found in 1 source file
```

Live cutover (`data/dataderby.duckdb`, 27 Oct 2026):

```text
dim_team: 221 teams, 221 mappings added (P1 run)
dim_stage: 11 stages + 1 registry-only (conference league), 12 mappings
canonical ids now on 11 headers, 258 team facts, 258 standings facts
coverage: 100% teams and stages mapped
v_latest_*: 258 rows each; v_points_adjustments still 1 (Southampton -4)
```

## Deviations and open items

- Plan deck slide 08 says "unknown team/stage blocks". Implementation
  ensures-before-asserts for the bootstrap reason above; the block fires only
  on genuine inconsistency. The deck (a plan artifact) is left as written;
  this report records the change.
- Placeholder `unmapped-{stage}` codes exist only for registry-absent stages;
  none remain live after the repair.
- 1999-2000 EPL pilot not started; needs the human stage-id discovery pass.
- StatsBomb pilot (P3) not started; no fixture exists.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Placeholder stage names leak to consumers | `canonical_name` reviewed in this cutover; registry names verified live |
| Operator edits a mapping by hand | mappings change by script; checksums pattern carries over |
| Rename breaks canonical trust | weekly drift query is P3; `updated_at` already recorded |

## Reviewer checklist

- [ ] 007-009 apply in order on a fresh DB (covered by `migrate` in every new fixture).
- [ ] No existing test deleted or weakened; two call sites updated for new behavior.
- [ ] `stages.toml` untouched; all live stages stay active.
- [ ] Live warehouse verified: 100% coverage, views intact, deduction visible.
- [ ] Index and report links updated.

## References

- Plan: `docs/reports/dim-tables-plan.md`, deck `docs/slides/dim-tables-plan-slides.html`
- ADR: `docs/adr/0011-team-stage-dimensions.md` (mark complete with this report)
- SQL: `sql/007_dim_stage.sql`, `sql/008_assertions_dims.sql`, `sql/009_views_dims.sql`
