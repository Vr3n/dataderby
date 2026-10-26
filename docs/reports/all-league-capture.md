# All-league capture

**Status:** complete
**Date:** 2026-10-26
**Issue:** #5 (reopened for the full sweep)
**Commit:** this change
**Related:** `docs/reports/live-capture.md`, #14

## Goal

The first live capture followed one row in one league. That proved the parser
could read real bytes; it could not prove the contract held across the season.
This sweep captures **all twelve configured stages**, all nine feeds each, parses
and publishes every one, and records what breaks.

The answer: **11 of 12 publish**. One legitimate points deduction was rejected by
the contract, and one competition's feed is empty while its page is not.

## What changed

| File | Change | Why |
|---|---|---|
| `scripts/audit_all_stages.py` | New. Captures every stage, validates, publishes, records failures | one run, all leagues, no fail-fast |
| `sql/002_assertions.sql` | A19 allows a points total below 3W+D; A20 no longer sums points | a deduction is legitimate and applies to the overall total |
| `tests/test_assertions.py` | `test_a_points_deduction_is_not_blocked` | pins the new rule |
| `config/stages.toml` | Conference League `expected_teams` 27 → 36, with a note | the live page has 36 teams, not 27 |
| `docs/reports/README.md` | Index entry | discovery |

## The sweep

- 12 stages, 9 feeds each: **108 feed requests**, 1,095,222 bytes, all validated.
- One shared scratch database, one transaction per stage.
- Total wall time: 295 s (22–33 s per stage), including 1.2 s pacing between feeds.
- Raw payloads under `data/live-audit/` (git-ignored); the table below is the
  committed evidence.

| Stage | Teams | Expected | Outcome | Notes |
|---|---:|---:|---|---|
| Bundesliga | 18 | 18 | accepted | |
| Champions League | 36 | 36 | accepted | league phase |
| Championship | 24 | 24 | accepted | 1 deduction (see below) |
| Conference League | 0 | 36 | **error** | feed empty, page has 36 |
| EFL League One | 24 | 24 | accepted | |
| EFL League Two | 24 | 24 | accepted | |
| Premier League | 20 | 20 | accepted | |
| Eredivisie | 18 | 18 | accepted | |
| Europa League | 36 | 36 | accepted | league phase |
| La Liga | 20 | 20 | accepted | |
| Ligue 1 | 18 | 18 | accepted | |
| Serie A | 20 | 20 | accepted | |

Across the 11 accepted stages: **0 null measures, 0 name mismatches, 0 schema
drift**, and `is_opta = true` everywhere.

## Finding 1 - a points deduction is not a data error

Southampton, Championship, 26 October:

| Split | Played | Won | Drawn | Lost | Points | 3W+D |
|---|---:|---:|---:|---:|---:|---:|
| Overall | 12 | 7 | 3 | 2 | **20** | 24 |
| Home | 6 | 5 | 1 | 0 | 16 | 16 |
| Away | 6 | 2 | 2 | 2 | 8 | 8 |

Overall points are **4 below** the arithmetic maximum, while home + away sum to
24. That is the shape of a points deduction, and English clubs do receive them.

The pipeline rejected it twice:

- **A19** required `points = 3*won + drawn`; the row was blocked.
- **A20** required `points_home + points_away = points_overall`; the row was
  retried.

Both assumptions are wrong for a real league. Points are **reported**, not
derived. A deduction applies to the overall total and is not reflected in the
split tables.

The fix:

- A19 now blocks only an **impossible** total: `points > 3*won + drawn`, or a
  negative total. A lower total is allowed.
- A20 no longer includes points; it still checks played, won, drawn, lost, goals
  for and goals against.
- The audit records the adjustment explicitly:

```json
{"team_id": 18, "name": "Southampton", "points": 20,
 "calculated": 24, "delta": -4}
```

**Recommendation.** Add a WARN assertion (or a `v_points_adjustments` view) so a
deduction is visible without blocking. The audit already proves the value; the
publish contract should not be the only place it can surface.

## Finding 2 - Conference League: 36 on the page, 0 in the feed

The registry expected 27 teams, from an earlier measurement. The live page on
26 October shows **36** teams, each with 2 played. The feeds, for every variant
tried (`numberOfTeamsToPick` 27 and 36, with and without `stageId`), return:

```json
{"teamTableStats": [], "paging": {...}, "statColumns": [8 names]}
```

So the page and the feed disagree about whether this competition has data. This
is the anomaly recorded during P1, now with evidence:

- the **count** was wrong: 36, not 27;
- the **feed** is empty for tournament 715, stage 25802;
- the **page** is not empty.

Actions taken:

- `expected_teams` corrected to 36.
- The stage is marked in `config/stages.toml` as capturable but not publishable,
  with a do-not-schedule note.

**Recommendation.** Do not guess another tournament id. Confirm the feed's
competition/stage identity with the source, or drop the stage from the schedule
until it returns rows. A stage that fails every run is noise, not coverage.

## Finding 3 - every feed says `text/html`

All 108 responses carry `content-type: text/html; charset=utf-8` while the body
is JSON. The parser already validates the body and ignores the header, so this
costs nothing today. It is a trap for any future client that trusts the header:
a `Content-Type` check would reject valid data.

**Recommendation.** Keep body validation; never branch on `content-type` for this
source. Recorded here so the next integration does not "fix" it.

## Finding 4 - the contract holds at scale

Eleven leagues, 18 to 36 teams, 108 payloads: no schema drift, no null measures,
no feed-vs-standings name mismatch. The 60-measure contract and the cohort checks
are not tuned to the Premier League.

That is the useful positive result: the shape generalises. The failures were rules
about *football*, not about parsing.

## Design decisions

- **Points are reported measures.** Do not derive them. The source can carry a
  deduction, and no arithmetic identity can distinguish that from an error
  without a policy.
- **The audit continues after a failure.** One bad league must not hide eleven
  good ones; the report is the product, not a clean exit code.
- **Raw payloads stay in `data/`.** 1.1 MB of source data is not committed;
  `results.json` and this table are.
- **No new tournament id by guesswork.** Conference League is a source problem
  until proven otherwise.

### Rejected alternatives

- **Allow any points value.** A total above 3W+D is impossible; that must still
  block.
- **Keep A20's points sum and add an exception for Southampton.** A team-specific
  exception is not a rule.
- **Store a `points_adjustment` column now.** The source does not label it; the
  audit can derive it. Add the column when a consumer needs it.
- **Remove Conference League silently.** The failure is information; the config
  note records it.

## Test matrix

| Test | Pins |
|---|---|
| `test_a_points_deduction_is_not_blocked` | a 4-point deduction passes A19 and A20 |
| `test_a19_standings_arithmetic_blocks` | points above the maximum still block |
| `test_a20_home_away_standings_must_add_up` | played/won/etc. still sum; points are excluded |
| `test_clean_candidate_passes_every_assertion` | the contract still accepts a clean table |

The sweep itself is an operator tool, not a CI test: CI cannot reach the source.
The committed evidence is the table above plus the audit results file.

## Evidence

```
$ uv run python scripts/audit_all_stages.py --out data/live-audit
11 accepted of 12
108 feed requests, 1,095,222 bytes, all text/html
1 deduction: Southampton -4
```

After the assertion fix:

```
$ uv run python scripts/audit_all_stages.py --stage championship-2026-2027
accepted teams=24
```

After the Conference correction:

```
$ uv run python scripts/audit_all_stages.py --stage conference-league-2026-2027
ERROR IncompleteCohort: expected 36 teams, found 0
```

## Deviations and open items

- **Conference League cannot publish.** Source feed empty. Do not schedule.
- **No WARN for deductions yet.** The audit records them; the publish contract
  accepts them silently. A view or A22 is the next step.
- **Production transport is still #14.** This sweep uses the browser capture tool;
  `dataderby run` still fetches over curl and will fail live.
- **The audit used one browser session for all stages.** It worked; a session that
  expires mid-sweep would surface as a feed error, not a crash.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| A deduction is actually a source error | the audit reports the delta; a human decides |
| Conference stage stays broken and unnoticed | config note and this report; do not schedule |
| A future feed returns HTML with 200 | body validation is already mandatory |
| The sweep hits rate limits | 1.2 s pacing, 108 requests over ~5 minutes |

## Reviewer checklist

- [ ] A points deduction passes; an impossible total still blocks.
- [ ] A20 no longer sums points.
- [ ] Conference League is 36 in config, with the do-not-schedule note.
- [ ] The report table matches the audit results.
- [ ] No raw payloads were committed.

## References

- `scripts/audit_all_stages.py` - the sweep.
- `docs/all-league-capture-slides.html` - companion deck in the paper/editorial
  theme: 25 slides, GSAP motion, talking points on every slide. It defines every
  term in the first four pages, including what a feed, a split, an assertion, and
  issue #14 are.
- `docs/reports/live-capture.md` - the single-league capture and the four defects.
- `sql/002_assertions.sql` - A19 and A20.
- `config/stages.toml` - the Conference note.
- `docs/reports/p1-decisions-config.md` - the original 27-team anomaly.
