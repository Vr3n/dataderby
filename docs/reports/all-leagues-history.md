# All-leagues history backfill (2009/10–2025/26 plus eras)

**Status:** complete
**Date:** 2026-10-27
**Branch:** `p2-dim-stage-cutover`
**Follows:** `docs/reports/epl-history-backfill.md` (EPL pilot)

## Goal

Extend the warehouse to every capturable WhoScored season for all 11
configured competitions: one snapshot per stage, validated by the same 25
assertions as live data. Where the source cannot supply a cohort, the season
is documented and skipped, never worked around.

## What changed

| File | Change | Why |
|---|---|---|
| `config/stages.toml` | 283 archived `[[stage]]` entries (259 → 295 total with the 12 live) plus per-block reason comments | Human-discovered ids, never guessed; archived stages stay out of polling |
| `scripts/discover_epl_seasons.py` | Tournament seasons dropdown walk, per-season show/stage capture | Reproducible id discovery without hand-copying |
| `scripts/discover_stages.py` | `#stages` dropdown dump for a given season URL | Catches seasons whose URL resolves to a playoff instead of the league |
| `src/dataderby/cli.py` | `check_team_sets` runs only when the stage declares a table | Knockout-style team-only snapshots need no league-table check |
| `tests/test_publish.py` | `test_publish_without_a_table_writes_team_facts_only` | Pins the team-only contract |
| `tests/test_config.py` | Registry assertions updated (295 stages, 12 active, spot checks) | The suite must describe the registry as it is |
| `scripts/README.md` | Both scripts listed | Repo rule |
| `docs/reports/all-leagues-history.md` | This report | AGENTS.md: one report per non-phase change |
| `docs/reports/README.md` | Index row | Keep the index complete |

No DDL, no assertion, and no view change. History is data; the schema
already partitions by stage.

## Coverage

| League | Captured | Skipped | Why skipped |
|---|---|---|---|
| EPL | 2009/10–2026/27 (18) | 1999/2000–2008/09 (10) | empty team feeds |
| Bundesliga | 2009/10–2026/27 (18) | 1999/2000–2008/09 (10) | empty team feeds |
| LaLiga | 2009/10–2026/27 (18) | 1999/2000–2008/09 (10) | empty team feeds |
| Serie A | 2015/16–2026/27 (12) | 1999/2000–2014/15 (16) | pre-2009 feeds empty; 2009/10–2014/15 feeds omit Parma (24341) while the table includes them |
| Championship | 2013/14–2026/27 (14) | 1999/2000–2012/13 (14) | empty team feeds |
| League One | 2019/20–2026/27 (8) | 1999/2000–2018/19 (20) | empty team feeds |
| League Two | 2019/20–2026/27 (8) | 1999/2000–2018/19 (20) | empty team feeds |
| Eredivisie | 2013/14–2026/27 (14) | 1999/2000–2012/13 (14) | empty team feeds |
| Ligue 1 | 2023/24–2026/27 (4) | 1999/2000–2022/23 (24) | systematic feed gaps: split team ids, 18 rows for 20-team seasons |
| UCL group | 2009/10–2023/24 (15) | 1999/2000–2002/03 second group stage (4) + 2003/04–2008/09 (6) | wrong grain / empty team feeds |
| UCL league | 2024/25–2026/27 (3) | — | — |
| UEL league | 2024/25–2026/27 (3) | group era 2009/10–2011/12 (3) empty feeds; 2012/13–2023/24 (12) split team ids | source gaps, e.g. 2247 vs 2647 for Union SG |
| Conference League | — | 2026/27 only, feed empty | source-side gap (pre-existing) |

Team-only seasons (stub pages, full feeds, `has_league_table = false`):
Championship 2013/14–2016/17 and 2018/19–2024/25; Eredivisie 2013/14–2016/17
and 2020/21–2021/22; League One 2019/20–2024/25; League Two 2019/20–2023/24;
UCL group era all 15; UCL league 2024/25–2025/26; UEL 2025/26. League One
2019/20 carries 23 clubs (Bury expelled); all cohorts validated by A1.

## Design decisions

- **Cutoffs are probed, not assumed.** Every league was bisected with 1-feed
  probes (EPL 2009/10 boundary found first, then per-league brackets) before
  any batch ran. Adjacent accepted/empty pairs pin each floor.
- **The playoff-trap check.** Discovery records whatever the season URL
  resolves to; for 5 seasons (Serie A 22/23, Eredivisie 23/24–25/26) that was
  a playoff stage, not the league. `discover_stages.py` exposes the dropdown
  and the registry takes the league stage. Verified by cohort size on publish.
- **Group-era UEFA joins as team-only.** A 32-team group phase is one cohort
  with no single table, exactly the knockout precedent: facts without
  standings, `has_league_table = false`.
- **No per-season exceptions in code.** Every skip is a registry
  non-entry or an archived entry with a reason comment. The pipeline runs
  unchanged; assertions decide per season.

### Rejected alternatives

- **Standings-only backfill for pre-2009 seasons.** The contract is team
  facts plus table rows; a 0-team publish corrupts the cohort invariant.
- **Guessing the missing team (Parma, Union SG id pairs).** Identity is
  never invented; the dim mapping covers observed ids only.
- **Parsing stub pages harder.** The stubs carry no table at all (180 KB,
  zero team rows); there is nothing to parse.

## Test matrix

| Test | Pins |
|---|---|
| 17-season EPL pilot batch, oldest first | feed format holds across 17 years |
| 13 + 15 group-era UCL runs | 32-team cohorts, team-only, all accepted |
| New-club and new-stage mapping on every publish | `dims backfill`: 0 unmapped, 0 NULL canonicals after |
| `test_publish_without_a_table_writes_team_facts_only` | team-only contract pinned |
| Full history batch per league (110 + 28 + 6 runs) | each accepted or blocked with a recorded reason |
| `freshness --check` | 0 of 11 live stages stale; archived invisible |

What this deliberately does not test: seasons documented as unschedulable
(their probes and blocked runs are the evidence).

## Evidence

```text
$ uv run dataderby dims backfill
dim_team: 0 teams, 0 mappings added
dim_stage: 0 stages, 0 mappings added
canonical ids now on 135 headers, 3023 team facts, 1800 standings facts
coverage: 100% teams and stages mapped
$ uv run dataderby freshness --check --max-age-hours 36
0 of 11 stages stale (older than 36 h)
```

Warehouse after: 135 snapshots, 3023 team facts, 1800 standings facts,
348 clubs, 295 mapped stages, 0 unmapped, 0 NULL canonicals.

Deductions surfaced by A19/A22 on real history:

| Season | Club | Reported | 3W+D | Delta |
|---|---|---|---|---|
| EPL 2009/10 | Portsmouth | 19 | 28 | -9 |
| EPL 2023/24 | Everton | 40 | 48 | -8 |
| EPL 2023/24 | Nottm Forest | 32 | 36 | -4 |
| Serie A 2018/19 | Chievo | 17 | 20 | -3 |
| Serie A 2022/23 | Juventus | 62 | 72 | -10 |
| Championship 2025/26 | Leicester | 46 | 52 | -6 |
| EPL 2026/27 | Southampton | 20 | 24 | -4 |
| Eredivisie 2023/24 | Vitesse | 6 | 24 | -18 |

Spot checks: Leicester 15/16 81, Man City 17/18 100, Liverpool 19/20 99,
UCL 09/10 accepted 32 teams, UEL 24/25 accepted with Lazio top.

## Deviations and open items

- Two transient token flakes (2019/20, 2020/21 EPL) accepted on plain retry.
- Pre-2009 EPL/Bundesliga/LaLiga/Serie A/Championship/Eredivisie/L1/L2,
  pre-2013 UEL group, and the 1999-2003 second-group-stage UCL are
  out of scope with probe evidence each.
- Ligue 1 22/23 and a 2022/23 Serie A probe confirmed the gaps before batching.
- `test_repository_stage_registry_loads` updated to 295 stages / 12 active;
  no test deleted.
- UEL group era (14 seasons) and Ligue 1 pre-2023 (24 seasons) documented
  as systematic source gaps; re-probe if the source changes.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| A future season changes feed shape | A1-A24 block; oldest-first order per era |
| Archived stage accidentally polled | `active = false`; freshness filters to active |
| Playoff resolution repeats | `discover_stages.py` + cohort-size check on publish |
| Hand-mapped dim rows | mappings change by script; checksums recorded |

## Reviewer checklist

- [ ] Spot-check two registry blocks against the discovery JSON.
- [ ] No existing test deleted; registry test updated to the new counts.
- [ ] `stages.toml` comments state every cutoff and skip with its reason.
- [ ] Index updated; deck untouched (a backfill is not an argument).

## References

- Discovery: `scripts/discover_epl_seasons.py`, `scripts/discover_stages.py`
- Registry: `config/stages.toml` (295 stages, 12 active)
- Dims: `docs/reports/dim-team-p1.md`, `docs/reports/dim-stage-p2.md`
- EPL pilot: `docs/reports/epl-history-backfill.md`
- Rules: `docs/slides/RULES.md`
