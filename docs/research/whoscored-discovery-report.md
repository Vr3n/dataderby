# WhoScored discovery report

**Measured 2026-10-20 · 12 competitions · decision recorded 20 Oct 2026.**

Everything below was captured live with `agent-browser` (headed Chrome 152). Measured
facts are marked as such; the few inferences are labelled. The raw captures are in
`experiments/whoscored/`.

---

## 0. The short version

- **12 competitions, one feed contract.** Every competition exposes the same five
  tabs and the same team-statistics payload.
- **60 measures per team, per stage.** Three sections × three splits
  (Overall/Home/Away) pivot into a 60-column row. Verified end-to-end on one team.
- **The feed is small and regular.** 9 JSON calls per stage; 108 for all twelve
  competitions. One page load per competition supplies the token for every stage.
- **The stage is a second axis.** League, group, playoff, knockout. A season can
  have one stage or nine; the set grows during the season.
- **The licence gate is cleared.** On 2026-10-20 the owner accepted the `isOpta`
  provenance for internal use. The posture stays local, private and non-redistributed.
- **One source anomaly:** Conference League currently serves 27 teams with one
  appearance each, against 108 fixtures in our calendar. Verify before trusting it.

Decision in one line: **ship the 60-column team-stat fact plus a companion standings
fact at the same `(snapshot, team)` grain, over the stage axis.** Standings are in
scope; player and referee stats remain out.

**Decision update (2026-10-20):** the five questions are answered in
`docs/research/whoscored-decisions.md`. Home/away is in scope, standings are in scope at the
same grain, raw payloads are persisted, and the refresh cadence is being measured
(E5, `docs/research/whoscored-cadence.md`).

---

## 1. Access and transport

Measured, not inferred:

- Headless Chrome is blocked by Cloudflare (`Attention Required!`). Headed Chrome
  with a normal desktop UA works.
- The site runs a fingerprint script that navigates the tab to `about:blank` a few
  seconds after load. Blocking `*fingerprint*` and `*podname.com*` before navigation
  keeps the page alive.
- No login is required for the pages and feeds used here.
- The statistics feed rejects a bare request: without the page token it returns
  HTML instead of JSON.
- The token is in the page:

  ```js
  const site = require.config.params.site;
  site.gSiteHeaderName;   // "Model-last-Mode"
  site.gSiteHeaderValue;  // per-page token
  ```

- A working feed request carries `Accept: application/json`,
  `X-Requested-With: XMLHttpRequest` and `Model-last-Mode: {token}`.
- The token is regenerated per page load but **works for every `stageId` tested**.
  One loaded page can therefore serve all stages of that competition.

What this means for a pipeline: browser automation is needed for the page load and
stage discovery, not for each data fetch. The feed calls can be plain requests once
the token and cookies are in hand.

---

## 2. Competition map

`region` / `tournament` / `season` / `stage` are WhoScored's numeric ids.
`whoscored_stage_id` is the identity used by the feed.

| Our key | WhoScored name | region | tournament | season | stage | Teams |
|---|---|---:|---:|---:|---:|---:|
| `epl` | Premier League | 252 | 2 | 11141 | 25544 | 20 |
| `championship` | Championship | 252 | 7 | 11184 | 25588 | 24 |
| `efl-league-one` | League One | 252 | 8 | 11185 | 25589 | 24 |
| `efl-league-two` | League Two | 252 | 9 | 11186 | 25590 | 24 |
| `la-liga` | LaLiga | 206 | 4 | 11213 | 25662 | 20 |
| `serie-a` | Serie A | 108 | 5 | 11126 | 25518 | 20 |
| `bundesliga` | Bundesliga | 81 | 3 | 11217 | 25666 | 18 |
| `ligue-1` | Ligue 1 | 74 | 22 | 11150 | 25554 | 18 |
| `eredivisie` | Eredivisie | 155 | 13 | 11135 | 25537 | 18 |
| `champions-league` | Champions League | 250 | 12 | 11295 | 25800 | 36 |
| `europa-league` | Europa League | 250 | 30 | 11294 | 25801 | 36 |
| `conference-league` | Conference League | 250 | 715 | 11296 | 25802 | 27 |

The full URL for every competition is in `docs/research/whoscored-competition-links.md`.

---

## 3. Page map

Five tabs, same URL grammar:

```
/regions/{region}/tournaments/{tournament}/seasons/{season}/stages/{stage}/show/{slug}
/regions/{region}/tournaments/{tournament}/seasons/{season}/stages/{stage}/fixtures/{slug}
/regions/{region}/tournaments/{tournament}/seasons/{season}/stages/{stage}/teamstatistics/{slug}
/regions/{region}/tournaments/{tournament}/seasons/{season}/stages/{stage}/playerstatistics/{slug}
/regions/{region}/tournaments/{tournament}/seasons/{season}/stages/{stage}/refereestatistics/{slug}
```

The slug is cosmetic. The numeric ids resolve.

---

## 4. Summary page — the League Table

Measured shape:

- Table id: `standings-{stage}-grid` (EPL `standings-25544-grid`, LaLiga
  `standings-25662-grid`).
- Columns: `Team | P | W | D | L | GF | GA | GD | Pts | Form` — ten cells per data row.
- Splits `Overall / Home / Away` are **client-side re-renders** of the same table.
  Clicking a split makes no network request; the hidden wide header is a template, not
  the rendered table.
- 3 header rows + one row per team. A 20-team league has 23 `<tr>` rows.
- Every data row carries `data-team-id` — the same numeric id as the feed (Man City 167,
  Brighton 211). This is the join key; the name is a label.
- The rank is **inside** the team cell (`1Manchester City`). A naive
  `cell.textContent` merges rank and name.
- `Form` is a rolling window of the **last six** matches in that split, newest last:
  `len(form) == min(P, 6)`. It is not one character per season match.
- Internal consistency held on the 2026-10-20 capture: `W+D+L=P`, `Pts=3W+D`,
  `GD=GF−GA`, ranks are `1..N`, and `home + away = overall` for `P/W/D/L/GF/GA/Pts`.
  Evidence: `experiments/whoscored/standings-25544.json`.

Sample, EPL after 7 rounds:

```
1  Manchester City   7 7 0 0 19  7 +12 21  wwwwww
2  Arsenal           7 6 0 1 11  5  +6 18  wwwlww
3  Brighton          7 5 1 1 23  5 +18 16  ldwwww
4  Chelsea           7 4 1 2 17 13  +4 13  wldlww
5  Liverpool         7 3 3 1  9  8  +1 12  dwdwlw
```

Other data on the same page:

- Six **Top Teams** leaderboards: Possession, Aggression, Aerial Duels Won, Shots
  per Game, Pass Accuracy, Ratings. Six rows each.
- Top Players, Best XI, Did You Know.
- **A knockout stage has no league table.** Confirmed on CL 2025/26 `Final Stage`
  (24797): `standings-24797-grid` is absent.

---

## 5. Team Statistics — the main product

The tab has three sub-tabs and three splits:

| | Overall | Home | Away |
|---|---|---|---|
| Summary | payload | payload | payload |
| Defensive | payload | payload | payload |
| Offensive | payload | payload | payload |

Nine feed calls per stage. The sub-tabs are anchors; switching one fires an XHR, it
does not navigate.

### The feed

```
GET https://www.whoscored.com/statisticsfeed/1/getteamstatistics
    ?category=summaryteam
    &subcategory=all|defensive|offensive
    &statsAccumulationType=0
    &field=Overall|Home|Away
    &stageId={stage}
    &sortBy=Rating
    &isCurrent=true
    &against=
```

Envelope:

```json
{
  "teamTableStats": [ { "...": "one row per team" } ],
  "paging": {
    "currentPage": 1,
    "firstRecordIndex": 0,
    "lastRecordIndex": 0,
    "resultsPerPage": 0,
    "totalPages": 0,
    "totalResults": 0
  },
  "statColumns": ["apps", "goal", "shotsPerGame", "yellowCard", "redCard", "possession", "passSuccess", "aerialWonPerGame"]
}
```

### `statColumns`, identical on all 12 stages

| Section | `subcategory` | Columns |
|---|---|---|
| Summary | `all` | `apps, goal, shotsPerGame, yellowCard, redCard, possession, passSuccess, aerialWonPerGame` |
| Defensive | `defensive` | `apps, shotsConcededPerGame, tacklePerGame, interceptionPerGame, foulsPerGame, offsideGivenPerGame` |
| Offensive | `offensive` | `apps, shotsPerGame, shotOnTargetPerGame, dribbleWonPerGame, foulGivenPerGame` |

`rating` and `ranking` are **not** in `statColumns`, but every row carries them.

### A team row (23 fields)

```json
{
  "name": "Brighton",
  "teamId": 211,
  "teamName": "Brighton",
  "teamRegionName": "England",
  "seasonId": 0,
  "seasonName": null,
  "tournamentId": 2,
  "isOpta": true,
  "tournamentRegionId": 252,
  "tournamentRegionCode": "eng",
  "tournamentRegionName": "England",
  "regionCode": "eng",
  "tournamentName": "Premier League",
  "rating": 6.97,
  "ranking": 1,
  "apps": 7,
  "goal": 23,
  "yellowCard": 15,
  "redCard": 1,
  "shotsPerGame": 17.857142857142858,
  "aerialWonPerGame": 17.571428571428573,
  "possession": 0.5993571428571429,
  "passSuccess": 0.8514990193331465
}
```

Notes:

- `seasonId` is **0** and `seasonName` is **null**. The stage is the only season key.
- `isOpta` is present on every row. It is a provenance flag, not a licence verdict.
- `possession` and `passSuccess` are fractions, not percentages.
- `*PerGame` values are floats with many decimals.

### The 60-column pivot

```
raw columns (19 × 3)                              = 57
− duplicate apps (2 × 3)                           = −6
− duplicate shots (1 × 3)                          = −3
unique columns                                    = 48
  42 section-owned + 3 apps + 3 shots             = 48
+ rating (3) + ranking (3 sections × 3)           = +12
                                                    60
```

| Group | Columns |
|---|---:|
| `apps_{overall,home,away}` | 3 |
| `rating_{overall,home,away}` | 3 |
| `shots_per_game_{overall,home,away}` | 3 |
| `summary_{split}_{goal, yellow_card, red_card, possession, pass_success, aerial_won_per_game}` | 18 |
| `defensive_{split}_{shots_conceded, tackles, interceptions, fouls, offsides}` | 15 |
| `offensive_{split}_{shots_on_target, dribbles_won, fouls_given}` | 9 |
| `ranking_{summary,defensive,offensive}_{split}` | 9 |
| **Total** | **60** |

Verified on Brighton (`teamId 211`, EPL 25544): 60 keys, saved to
`experiments/whoscored/brighton-60.json`.

**Naming correction:** the defensive field is `shotsConcededPerGame` — shots
conceded, not goals conceded. The page header says "Shots pg". Use
`defensive_{split}_shots_conceded`.

---

## 6. Stage model

A season has one or more stages. Identity is `whoscored_stage_id`; `stage` is a
curated code.

Codes: `league`, `group`, `qualification`, `knockout`, `playoff`, `final`.
`qualification` and `final` are reserved codes; neither was observed in the
2026/27 set.

### Where the label comes from

- The feed has **no stage name**.
- `require.config.params.args` has `stageId` and `isOptaStage`; no name.
- The only source is the `#stages` select, present on the `show` and
  `teamstatistics` pages **only when the season has more than one stage**.

Measured labels:

| Season | `<option>` text | `stage` |
|---|---|---|
| CL 2025/26 | `Champions League` | `league` |
| CL 2025/26 | `Champions League Final Stage` | `knockout` |
| CL 2022/23 | `Champions League Final Stage` | `knockout` |
| CL 2022/23 | `Champions League Grp. A` … `Grp. H` | `group`, A–H |
| Championship 2025/26 | `Championship` | `league` |
| Championship 2025/26 | `Championship Playoff` | `playoff` |
| EPL 2025/26 | no select | `league` |

### Derivation

1. label equals the tournament name → `league`
2. suffix `Grp. X` → `group`, `group = X`
3. suffix `Final Stage` → `knockout`
4. suffix `Playoff` / `Play-offs` → `playoff`
5. suffix `Final` → `final`
6. anything else → fail closed, keep the label verbatim

Do not normalise by stripping `Stage`:

- `Final Stage` is the whole knockout phase, not the final.
- The base stage has no suffix; the label is just the tournament name.
- CL 2022/23 has **eight separate group stages**, one id per group.

The select order is not chronological. CL lists `Final Stage` first; the
Championship lists the league first. Never use option order.

### What changes per stage

- `has_league_table`: measured true for league/group; measured false for
  knockout. Probe playoff and final stages; do not infer them.
- Team statistics exist for the knockout stage (CL 24797 returns the feed).
- The stage set grows during a season (CL adds knockout; Championship adds
  playoffs), so discovery must run every refresh and append, not replace.

---

## 7. What data you can get

| Dataset | Grain | Shape | Status |
|---|---|---|---|
| League table | team × stage × split | 10 columns (`Team,P,W,D,L,GF,GA,GD,Pts,Form`) | measured |
| Team statistics | team × stage × split | 60 columns | measured, verified |
| Top Teams | leaderboard × stage | 6 boards × 6 rows | measured, presentation |
| Top Players / Best XI | stage | lists | seen, not parsed |
| Player statistics | player × stage × split | separate feed | tab exists, unmeasured |
| Referee statistics | referee × stage | separate feed | tab exists, unmeasured |
| Situational team stats | team × stage | goals by situation, passes, cards | partial, lazy-loaded |
| Positional team stats | team × stage | touch/attempt zones | partial, lazy-loaded |
| xG | team × stage | separate category | endpoint documented, not exercised |

The 60-column fact is the only dataset with a fully measured contract.

### Availability per competition

All twelve returned the same three sections for `Overall`. The full 3 × 3 pivot
was assembled for Brighton; the other competitions' Home/Away payloads were not
individually pivoted. Row counts:

| Competition | Teams | Apps (min/max) | Note |
|---|---:|---|---|
| Premier League | 20 | 6–7 | |
| Championship | 24 | — | |
| League One | 24 | — | |
| League Two | 24 | — | |
| LaLiga | 20 | — | |
| Serie A | 20 | — | |
| Bundesliga | 18 | — | |
| Ligue 1 | 18 | — | |
| Eredivisie | 18 | — | |
| Champions League | 36 | 2–2 | league phase |
| Europa League | 36 | 2–2 | league phase |
| Conference League | 27 | 1–1 | **anomaly — verify** |

Conference League against our fixture calendar: 108 matches implies a 36-team
league phase. 27 teams with one appearance each does not. Either it is a
qualification phase or WhoScored is mid-publication.

---

## 8. Cost

- **Page loads:** 1 per competition (12), for the token and stage discovery.
- **Feed calls:** 9 per stage. 108 for all twelve 2026/27 stages.
- **Payloads:** small JSON; ~20–36 rows each.
- **Storage:** roughly 12 × 24 × 60 ≈ 17k measures per full snapshot. Negligible.
- **Refresh:** a 2-minute cache sets the floor; daily heartbeat plus post-matchday
  sweeps is the provisional schedule (`docs/research/whoscored-cadence.md`).

There is no bulk export. The fixture calendar is a separate source and is not
joined to this data by team name.

---

## 9. Risks and unknowns

| Risk | Status | Consequence |
|---|---|---|
| `isOpta` licensing | **accepted 2026-10-20** | internal use; keep the private/non-redistributed posture |
| Cloudflare / fingerprint | mitigated, fragile | browser recipe can break |
| Publication latency | **being measured (E5)** | `observed_at` is the only timestamp; provisional daily + post-matchday |
| Retroactive corrections | unknown | snapshot model is designed for it |
| `teamId` stability | unknown | identity is `(stage, teamId)` if stable |
| Conference League stage | unresolved | wrong scope if treated as league phase |
| Stage label drift | possible | fail closed on unknown labels |
| Knockout stage count | unknown for 2026/27 | discovery must append |
| Standings vs stats grain | **same grain, separate fact** | join on `(snapshot_id, data-team-id)`; never on name |

The `isOpta` flag is provenance. The owner accepted it on 2026-10-20; the decision and
its scope are in `docs/research/whoscored-decisions.md`. The technical posture is unchanged.

---

## 10. Options

### A. Ship the 60-column team-stat fact (recommended)

- 3 sections × 3 splits × 12 competitions.
- Identity: `(whoscored_stage_id, teamId, observed_at)`.
- Stage reference table with `stage`, `whoscored_stage_name`, group.
- Cost: 108 feed calls, 12 page loads, one browser recipe.
- Unlocks: team-season comparison, home/away splits, rankings, trend over time.

### B. Overall-only subset

- 20 columns instead of 60; 36 feed calls.
- Loses home/away, which is most of the analytical value.
- Only sensible if the product only needs season totals.

### C. Add the league table as a standings fact (now in scope)

- Same grain as the team stats: team × stage, with Overall/Home/Away splits.
- Nearly free: parsed from the page already loaded for the token.
- Keep it as a **companion fact** at the same `(snapshot_id, team_id)` grain, not merged
  into the 60-column fact.
- Join on `tr[data-team-id]`, never on team name.
- A knockout stage has no table: zero rows, not null measures.

### D. Add situational / positional stats

- Goals by situation, passes, cards, touch zones, attempt zones.
- Availability is uneven; some grids were empty/lazy.
- Needs its own schema and more discovery before it can be estimated.

### E. Player and referee statistics

- Separate tabs and feeds, much larger grain.
- Not measured. Treat as a separate project, not a v1 add-on.

---

## 11. Recommendation

1. **Build A + C.** The 60-column team-stat fact plus the companion standings fact at
   the same grain. Both are measured; both fit the snapshot model.
2. **Add the stage reference table.** Without it, a new stage cannot be classified.
3. **Persist the raw payloads** — page HTML, three standings views, nine feeds. Raw is
   the replay source, not a hash.
4. **Skip B** — the split is the point.
5. **Defer D and E** until there is a product requirement.
6. **The licence is accepted (2026-10-20).** Keep the posture: local, private,
   non-redistributed, `data/` ignored.
7. **Measure the cadence before fixing it.** E5 runs on the next matchday; until then,
   daily heartbeat plus post-matchday sweeps.

---

## 12. Questions for the decision meeting — answered

| # | Question | Answer (2026-10-20) |
|---|---|---|
| 1 | Is the `isOpta` licence acceptable? | **Accepted**; private/non-redistributed posture |
| 2 | Is the Conference League stage the league phase or a qualifier? | Still open — verify against the fixtures page |
| 3 | Is home/away in scope? | **Yes** |
| 4 | Are standings a separate product? | **No** — same grain, companion fact |
| 5 | What refresh cadence? | **Measured** (E5); provisional daily + post-matchday |
| 6 | Persist raw JSON? | **Yes**, including the page and standings views |

Full record: `docs/research/whoscored-decisions.md`; cadence evidence:
`docs/research/whoscored-cadence.md`.

---

## Appendix — artefacts

| File | Contents |
|---|---|
| `docs/research/whoscored-competition-links.md` | URLs, stage model, column inventory |
| `experiments/whoscored/stages.json` | 12 competitions → season → stage |
| `experiments/whoscored/stage-labels.json` | observed stage labels and derivation |
| `experiments/whoscored/brighton-60.json` | one verified 60-column row |
| `experiments/whoscored/collect_stage.js` | per-stage payload probe |
| `experiments/whoscored/collect_row.js` | 9-payload pivot for one team |
| `experiments/whoscored/collect_standings.js` | three standings views from the stage page |
| `experiments/whoscored/standings-25544.json` | verified EPL standings capture, 3 splits |
| `experiments/whoscored/cadence_probe.js` | one cadence fingerprint (standings + 9 feeds) |
| `experiments/whoscored/cadence_probe.ps1` | E5 interval loop, JSONL output |
| `experiments/whoscored/README.md` | browser recipe and findings |
| `docs/research/whoscored-decisions.md` | the five decisions, 2026-10-20 |
| `docs/research/whoscored-cadence.md` | header evidence, E5 method, provisional schedule |
| `docs/research/whoscored-api.md` | feed details and the 23 row fields |
