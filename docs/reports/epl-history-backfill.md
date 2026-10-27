# EPL history backfill (2009/10-2025/26)

**Status:** complete
**Date:** 2026-10-27
**Branch:** `p2-dim-stage-cutover` (registry + report only; no code changed)

## Goal

Give the warehouse every capturable Premier League season: 2009/2010 through
2025/2026, one snapshot each, validated by the same 25 assertions as live data.
 seasons 1999/2000-2008/2009 cannot be captured (source serves no team rows)
and are documented, not worked around.

## What changed

| File | Change | Why |
|---|---|---|
| `config/stages.toml` | 27 EPL history `[[stage]]` entries, all `active = false`, plus the cutoff comment | Human discovery is never a guess; archived stages stay out of the polling set |
| `scripts/discover_epl_seasons.py` | Browser discovery: seasons dropdown, per-season show/stage links, JSON out | Reproducible discovery without hand-copying ids |
| `scripts/README.md` | Script table row | Repo rule: every script is listed |
| `docs/reports/epl-history-backfill.md` | This report | AGENTS.md: one report per non-phase change |
| `docs/reports/README.md` | Index row | Keep the index complete |

No DDL, no pipeline code, no test changes. History is data, and the schema
already partitions by stage.

## Design decisions

- **Oldest first.** 2009/2010 piloted alone: oldest feed format is the riskiest
  unknown. It accepted, so the batch ran oldest-to-newest with no format
  surprises.
- **Active split before any backfill.** All 27 entries landed `active = false`.
  Default `run` and `freshness --check` never see them; explicit `--stage`
  one-shots do. Verified: check passes on the 11 live stages only.
- **No standings-only backfill.** 1999-2008 team feeds return
  `teamTableStats: []` while standings serve fine. A11/A1 correctly refuse a
  0-team publish; inventing a team-less snapshot would corrupt the cohort
  contract. Same gap class as the conference league, same response: document
  and do not schedule.
- **Cutoff found by probe, not by assumption.** `probe --stage` costs 3
  requests per season: 2008/2009 empty (same empty-payload hash as 1999/2000),
  2009/2010 full 20 teams.

### Rejected alternatives

- **Guessing stage ids from a pattern.** Old ids (2, 89, 213) follow no
  rule; every id in the registry was read from the live page.
- **Batching newest-first.** A format break would surface after the easy wins
  instead of before them.
- **Retrying 1999/2000 repeatedly.** Empty `teamTableStats` with
  `totalResults: 0` is a source answer, not a transient failure.

## Test matrix

| Test | Pins |
|---|---|
| Pilot `run --stage epl-1999-2000` | blocks with 0 teams (A1); raw evidence landed |
| Probes epl-2008-2009 / epl-2009-2010 | 0 vs 20 teams; cutoff pinned |
| 17 × `run --stage epl-YYYY-YYYY` | 15 accepted first pass; 2 transient token flakes accepted on retry; 17/17 final |
| Live verification query | 18 EPL snapshots (2009-2026), 20+20 facts each, 0 NULL canonicals, 0 unmapped |
| `dims backfill` | 0 new rows (publish auto-mapped), coverage 100% |
| `freshness --check --max-age-hours 36` | 0 of 11 stale; archived invisible |

What this deliberately does not assert: pre-2009 team data (does not exist
in the feeds); future-season drift (assertions run per publish).

## Evidence

```text
$ uv run dataderby run --stage epl-1999-2000
blocked: expected 20 teams, found 0            # exit 3
$ uv run dataderby probe --stage epl-2008-2009
epl-2008-2009: 0 teams, 298 bytes, sha256 b687001b7603...
$ uv run dataderby probe --stage epl-2009-2010
epl-2009-2010: 20 teams, 10462 bytes, sha256 cde44e08ea0512ba
$ <17-season batch, oldest to newest>
15 × accepted (20 teams); 2 × token flake, both accepted on retry
$ uv run dataderby dims backfill
dim_team: 0 teams, 0 mappings added
dim_stage: 0 stages, 0 mappings added
canonical ids now on 28 headers, 598 team facts, 598 standings facts
coverage: 100% teams and stages mapped
$ uv run dataderby freshness --check --max-age-hours 36
0 of 11 stages stale (older than 36 h)
```

Warehouse after: 28 snapshots, 598 team facts, 598 standings facts,
221 distinct clubs (no new ids: every 2009-2025 club already mapped),
0 unmapped, 0 NULL canonical ids.

Deductions surfaced by the backfill (A19/A22 working on real history):

| Season | Club | Reported | 3W+D | Delta |
|---|---|---|---|---|
| 2009-2010 | Portsmouth | 19 | 28 | -9 |
| 2023-2024 | Everton | 40 | 48 | -8 |
| 2023-2024 | Nottingham Forest | 32 | 36 | -4 |
| 2026-2027 | Southampton | 20 | 24 | -4 |

Spot check (rank 1 per season): Chelsea 09/10 86, Man Utd 10/11 80,
Man City 11/12 89, Man Utd 12/13 89, Man City 13/14 86, Chelsea 14/15 87,
Leicester 15/16 81, Chelsea 16/17 93, Man City 17/18 100, Man City 18/19 98,
Liverpool 19/20 99, Man City 20/21 86, 21/22 93, 22/23 89, 23/24 91,
Liverpool 24/25 84.

## Deviations and open items

- Two token flakes (`page did not expose gSiteHeaderValue`, 2019/20 and
  2020/21) accepted on plain retry. Known transient, no code change.
- The blocked 1999/2000 run left a `running` row; `reconcile()` marks it
  `abandoned` on the next start by design.
- Pre-2009 EPL (10 seasons) and the conference league stay unscheduled for
  the same source-side reason.
- 1999/2000-2008/2009 standings feeds serve data, but standings-only
  snapshots are rejected by design (see above).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| A future season changes feed shape | A1-A24 block; the pilot-oldest-first order repeats per era |
| Archived stage accidentally polled | `active = false` is validated config; freshness check filters to active |
| Old club name collides in dims | names verified stable; `map-team` + drift review own corrections |

## Reviewer checklist

- [ ] All 27 stage ids match the discovery JSON (kept at the temp path in the log, not committed).
- [ ] No existing test modified; no code changed in this step.
- [ ] `stages.toml` comment states the cutoff and the reason.
- [ ] Index updated; deck links untouched (no deck for a data backfill).

## References

- Discovery: `scripts/discover_epl_seasons.py`
- Registry: `config/stages.toml` (27 entries + cutoff comment)
- Dims: `docs/reports/dim-team-p1.md`, `docs/reports/dim-stage-p2.md`
- Rules: `docs/slides/RULES.md` (no deck: a backfill is not an argument)
