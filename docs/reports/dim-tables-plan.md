# Dim tables plan (team + stage)

**Status:** proposed (P0 of rollout)
**Date:** 2026-10-27
**Deck:** `docs/slides/dim-tables-plan-slides.html`
**Decision:** `docs/adr/0011-team-stage-dimensions.md`

## Goal

Give every club and every stage one canonical row so a second source (StatsBomb,
different team and competition ids) joins without rewriting facts. Backfill from
the 11 live snapshots, check mappings on every publish, keep views
byte-identical until source two arrives.

## What changed

| File | Change | Why |
|---|---|---|
| `docs/adr/0011-team-stage-dimensions.md` | Shape decision: dims plus source-key maps, lineage kept | Hard-to-reverse; records the choice and the rejected wide-column and team-snapshot options |
| `docs/slides/dim-tables-plan-slides.html` | 14-slide animated plan deck, paper theme | The plan must be reviewable without the presenter; RULES.md requires notes, numbers, and links |
| `docs/reports/dim-tables-plan.md` | This report | AGENTS.md: one report per non-phase change |
| `docs/reports/README.md` | Index row | Keep the index complete |

No Python, SQL, or tests changed in this step. Implementation lands in P1/P2.

## Design decisions

- Canonical dims plus mapping tables, not wide `statsbomb_id` columns: N sources
  without DDL per source; the mapping pair (PK on source ids, UNIQUE on
  canonical plus source) forbids double mapping in both directions.
- `dim_stage` grain is (tournament, season, stage code); UEFA splits become extra
  mapping rows, never redesigns.
- Nullable canonical columns during rollout, NOT NULL after verified backfill,
  so no phase blocks publishing.
- SCD2 deferred: names are stable (no id maps to two names today); rename path
  is update plus weekly drift query until the first real rename.

### Rejected alternatives

- **`statsbomb_id` on facts.** 258 copies, no cross-snapshot guarantee, breaks on
  source three.
- **Replacing WhoScored ids on facts.** Destroys raw-archive lineage (ADR 0004).
- **Implementing now without a plan.** Stage equivalence (UCL league vs knockout)
  needs agreement first; the deck forces that conversation.

## Test matrix

| Test | Pins |
|---|---|
| `test_dim_backfill_counts` | 221 teams, 11 stages from live data |
| `test_team_key_uniqueness` | duplicate source id rejected |
| `test_team_double_mapping` | one club, two StatsBomb ids rejected |
| `test_stage_key_uniqueness` | duplicate stage address rejected |
| `test_a23_unknown_team` | unmapped team blocks publish |
| `test_a24_unknown_stage` | unmapped stage blocks publish |
| `test_views_equivalent` | canonical join returns today's rows |
| `test_shared_club_collapses` | team 13 has one dim row, two fact rows |
| `test_rename_updates` | rename without SCD2 |
| `test_new_team_curation` | promoted club via curation path |
| `test_rollback_006_only` | publishing works if 007 never ran |
| `test_no_fact_rewrite` | `whoscored_*` columns untouched |

Deliberately not tested: StatsBomb mapping values (no fixture exists).

## Evidence

Warehouse state read 27 Oct 2026 (`data/dataderby.duckdb`):

```text
snapshots: 11 (one per stage) | fact_team: 258 | fact_standings: 258
distinct clubs: 221 | clubs in 2 stages: 37 | null measures: 0
runs: 15 (11 accepted, 4 no_change) | checkpoints: 11
v_latest_*: 258 each | v_snapshot_delta: 0 | v_points_adjustments: 1 (Southampton -4)
```

```text
$ uv run python check_deck.py   # dim-tables-plan-slides.html
slides: 14
notes: 14
section close: 14
div open/close: balanced
```

`node --check` on the extracted inline script passed.

## Deviations and open items

- Stage names for the canonical `dim_stage` rows (tournament display names) need
  one review pass against `config/stages.toml` before P1.
- StatsBomb competition and season ids are unknown; P3 starts when a real
  fixture exists.
- Performance budgets (publish p95 under +5%, views under +10%, file under +2%)
  are declared in the deck; baselines get committed in P1.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Promoted clubs arrive unmapped | A23 blocks; curation adds the dim row; publish retries |
| Mid-season rename | weekly drift query; update path; SCD2 only if it recurs |
| StatsBomb splits a stage | second mapping row, no DDL |
| Hand-edited mappings | mappings change by script with recorded checksums |

## Reviewer checklist

- [ ] Backfill counts (221/11) reproduce from the live file.
- [ ] No existing test rewritten; new tests target the new constraints.
- [ ] Deck numbers match this report; every slide has a note.
- [ ] Deck links to report and ADR; report links to deck.
- [ ] Index updated.

## References

- Deck: `docs/slides/dim-tables-plan-slides.html`
- Rules: `docs/slides/RULES.md`
- ADR: `docs/adr/0011-team-stage-dimensions.md`
- SQL: `sql/001_schema.sql`, `sql/003_views.sql`
- Reports: `docs/reports/p3-schema.md`, `p6-publish.md`, `p7-views.md`
