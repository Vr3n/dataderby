# ADR 0011: Conformed team and stage dimensions with source mappings

**Status:** complete (P1 team half + P2 stage half merged)
**Date:** 2026-10-27
**Decides:** `dim_team` + `dim_stage` shape for multi-source support
**Builds:** `docs/reports/dim-team-p1.md` (team half), `docs/reports/dim-stage-p2.md` (stage half)

## Context

The warehouse holds 11 accepted snapshots (one per stage), 258 `fact_team_snapshot`
rows, 258 `fact_standings_snapshot` rows, 221 distinct `whoscored_team_id`s.
37 clubs appear in two stages each (domestic league plus a UEFA phase), e.g.
Arsenal (13) in tournaments 2 and 12. Team names are stable today: no id maps to
two names, no name maps to two ids. Every fact row repeats
`(whoscored_team_id, whoscored_team_name)`; every header repeats the
`(tournament, season, stage)` address. A second source (StatsBomb) uses different
team and competition ids, so joining on WhoScored ids stops working the day it
arrives.

## Decision

Add canonical dimensions plus per-source key mappings, keep source columns on
facts and headers for lineage:

- `dim_team (dataderby_team_id PK, canonical_name, first_seen_at, updated_at)`
- `team_source_key (dataderby_team_id, source, source_team_id)` with
  `PRIMARY KEY (source, source_team_id)` and `UNIQUE (dataderby_team_id, source)`
- `dim_stage (dataderby_stage_id PK, tournament_name, season_key, stage_code,
  canonical_name)` with `UNIQUE (tournament_name, season_key, stage_code)`
- `stage_source_key (dataderby_stage_id, source, source_tournament_id,
  source_season_id, source_stage_id)` with the analogous two constraints
- Facts and headers keep all `whoscored_*` columns and gain
  `dataderby_team_id` / `dataderby_stage_id`. Consumers join on the canonical ids.

## Rejected alternatives

- **Wide columns (`statsbomb_id` on facts).** Breaks on the third source, repeats
  the mapping per snapshot (258 copies today), and cannot forbid one WhoScored id
  mapping to two StatsBomb ids across snapshots.
- **`team_snapshot` (one row per team per snapshot).** Same grain as the facts,
  so it stores no new information, only a second copy of the name.
- **Replacing WhoScored ids with canonical ids on facts.** Destroys lineage to
  the raw archive, which is the system of record (ADR 0004).

## Consequences

- Backfill from current data: 221 `dim_team` rows, 11 `dim_stage` rows,
  221 + 11 mapping rows, all `source = 'whoscored'`.
- New assertion per publish: every fact team and every header stage resolves in
  the mapping tables (block on miss, with a curation path for genuinely new
  teams).
- Views gain one join each to expose canonical names; `whoscored_*` columns stay
  for audit.
- SCD2 only on rename: `updated_at` suffices until a club actually renames, then
  add validity columns rather than snapshotting per observation.
