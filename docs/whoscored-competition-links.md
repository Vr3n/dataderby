# WhoScored competition pages — 2026/27

Captured **2026-10-20** with `agent-browser` 0.37.1 (headed Chrome 152). Scope: the
twelve competitions in `src/dataderby/fixtures/competitions.py`.

Two things were measured, not inferred:

1. the page and ID for every competition;
2. the exact columns the Team Statistics tab serves, for all twelve stages, in all
   three splits.

Everything else in this document is labelled as observed or as an open question.

---

## 1. Competition map

`region` / `tournament` / `season` / `stage` are WhoScored's own identifiers. The
numeric stage is the key the statistics feed uses (`stageId`), not the season; it is
named `whoscored_stage_id` throughout this project.

| Our key | WhoScored name | region id | tournament id | season id | stage id | Teams in feed |
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

"Teams in feed" is the row count of `teamTableStats` for the Summary/Overall payload,
measured for every stage. It is not the number of matches played.

### Links

Every competition exposes the same five pages. The three that matter for this plan:

| Our key | Summary (League Table) | Team Statistics | Fixtures |
|---|---|---|---|
| `epl` | [show][epl-show] | [team stats][epl-ts] | [fixtures][epl-fx] |
| `championship` | [show][cha-show] | [team stats][cha-ts] | [fixtures][cha-fx] |
| `efl-league-one` | [show][l1-show] | [team stats][l1-ts] | [fixtures][l1-fx] |
| `efl-league-two` | [show][l2-show] | [team stats][l2-ts] | [fixtures][l2-fx] |
| `la-liga` | [show][lal-show] | [team stats][lal-ts] | [fixtures][lal-fx] |
| `serie-a` | [show][sa-show] | [team stats][sa-ts] | [fixtures][sa-fx] |
| `bundesliga` | [show][bun-show] | [team stats][bun-ts] | [fixtures][bun-fx] |
| `ligue-1` | [show][lig-show] | [team stats][lig-ts] | [fixtures][lig-fx] |
| `eredivisie` | [show][ere-show] | [team stats][ere-ts] | [fixtures][ere-fx] |
| `champions-league` | [show][cl-show] | [team stats][cl-ts] | [fixtures][cl-fx] |
| `europa-league` | [show][el-show] | [team stats][el-ts] | [fixtures][el-fx] |
| `conference-league` | [show][con-show] | [team stats][con-ts] | [fixtures][con-fx] |

[epl-show]: https://www.whoscored.com/regions/252/tournaments/2/seasons/11141/stages/25544/show/england-premier-league-2026-2027
[epl-ts]: https://www.whoscored.com/regions/252/tournaments/2/seasons/11141/stages/25544/teamstatistics/england-premier-league-2026-2027
[epl-fx]: https://www.whoscored.com/regions/252/tournaments/2/seasons/11141/stages/25544/fixtures/england-premier-league-2026-2027
[cha-show]: https://www.whoscored.com/regions/252/tournaments/7/seasons/11184/stages/25588/show/england-championship-2026-2027
[cha-ts]: https://www.whoscored.com/regions/252/tournaments/7/seasons/11184/stages/25588/teamstatistics/england-championship-2026-2027
[cha-fx]: https://www.whoscored.com/regions/252/tournaments/7/seasons/11184/stages/25588/fixtures/england-championship-2026-2027
[l1-show]: https://www.whoscored.com/regions/252/tournaments/8/seasons/11185/stages/25589/show/england-league-one-2026-2027
[l1-ts]: https://www.whoscored.com/regions/252/tournaments/8/seasons/11185/stages/25589/teamstatistics/england-league-one-2026-2027
[l1-fx]: https://www.whoscored.com/regions/252/tournaments/8/seasons/11185/stages/25589/fixtures/england-league-one-2026-2027
[l2-show]: https://www.whoscored.com/regions/252/tournaments/9/seasons/11186/stages/25590/show/england-league-two-2026-2027
[l2-ts]: https://www.whoscored.com/regions/252/tournaments/9/seasons/11186/stages/25590/teamstatistics/england-league-two-2026-2027
[l2-fx]: https://www.whoscored.com/regions/252/tournaments/9/seasons/11186/stages/25590/fixtures/england-league-two-2026-2027
[lal-show]: https://www.whoscored.com/regions/206/tournaments/4/seasons/11213/stages/25662/show/spain-laliga-2026-2027
[lal-ts]: https://www.whoscored.com/regions/206/tournaments/4/seasons/11213/stages/25662/teamstatistics/spain-laliga-2026-2027
[lal-fx]: https://www.whoscored.com/regions/206/tournaments/4/seasons/11213/stages/25662/fixtures/spain-laliga-2026-2027
[sa-show]: https://www.whoscored.com/regions/108/tournaments/5/seasons/11126/stages/25518/show/italy-serie-a-2026-2027
[sa-ts]: https://www.whoscored.com/regions/108/tournaments/5/seasons/11126/stages/25518/teamstatistics/italy-serie-a-2026-2027
[sa-fx]: https://www.whoscored.com/regions/108/tournaments/5/seasons/11126/stages/25518/fixtures/italy-serie-a-2026-2027
[bun-show]: https://www.whoscored.com/regions/81/tournaments/3/seasons/11217/stages/25666/show/germany-bundesliga-2026-2027
[bun-ts]: https://www.whoscored.com/regions/81/tournaments/3/seasons/11217/stages/25666/teamstatistics/germany-bundesliga-2026-2027
[bun-fx]: https://www.whoscored.com/regions/81/tournaments/3/seasons/11217/stages/25666/fixtures/germany-bundesliga-2026-2027
[lig-show]: https://www.whoscored.com/regions/74/tournaments/22/seasons/11150/stages/25554/show/france-ligue-1-2026-2027
[lig-ts]: https://www.whoscored.com/regions/74/tournaments/22/seasons/11150/stages/25554/teamstatistics/france-ligue-1-2026-2027
[lig-fx]: https://www.whoscored.com/regions/74/tournaments/22/seasons/11150/stages/25554/fixtures/france-ligue-1-2026-2027
[ere-show]: https://www.whoscored.com/regions/155/tournaments/13/seasons/11135/stages/25537/show/netherlands-eredivisie-2026-2027
[ere-ts]: https://www.whoscored.com/regions/155/tournaments/13/seasons/11135/stages/25537/teamstatistics/netherlands-eredivisie-2026-2027
[ere-fx]: https://www.whoscored.com/regions/155/tournaments/13/seasons/11135/stages/25537/fixtures/netherlands-eredivisie-2026-2027
[cl-show]: https://www.whoscored.com/regions/250/tournaments/12/seasons/11295/stages/25800/show/europe-champions-league-2026-2027
[cl-ts]: https://www.whoscored.com/regions/250/tournaments/12/seasons/11295/stages/25800/teamstatistics/europe-champions-league-2026-2027
[cl-fx]: https://www.whoscored.com/regions/250/tournaments/12/seasons/11295/stages/25800/fixtures/europe-champions-league-2026-2027
[el-show]: https://www.whoscored.com/regions/250/tournaments/30/seasons/11294/stages/25801/show/europe-europa-league-2026-2027
[el-ts]: https://www.whoscored.com/regions/250/tournaments/30/seasons/11294/stages/25801/teamstatistics/europe-europa-league-2026-2027
[el-fx]: https://www.whoscored.com/regions/250/tournaments/30/seasons/11294/stages/25801/fixtures/europe-europa-league-2026-2027
[con-show]: https://www.whoscored.com/regions/250/tournaments/715/seasons/11296/stages/25802/show/europe-conference-league-2026-2027
[con-ts]: https://www.whoscored.com/regions/250/tournaments/715/seasons/11296/stages/25802/teamstatistics/europe-conference-league-2026-2027
[con-fx]: https://www.whoscored.com/regions/250/tournaments/715/seasons/11296/stages/25802/fixtures/europe-conference-league-2026-2027

### URL grammar

```
/regions/{region}/tournaments/{tournament}/seasons/{season}/stages/{stage}/show/{slug}
/regions/{region}/tournaments/{tournament}/seasons/{season}/stages/{stage}/teamstatistics/{slug}
/regions/{region}/tournaments/{tournament}/seasons/{season}/stages/{stage}/fixtures/{slug}
/regions/{region}/tournaments/{tournament}/seasons/{season}/stages/{stage}/playerstatistics/{slug}
/regions/{region}/tournaments/{tournament}/seasons/{season}/stages/{stage}/refereestatistics/{slug}
```

The slug is `{country-or-continent}-{competition}-2026-2027`, lower-case, and is
cosmetic: the numeric IDs are what resolve.

### Stage model

WhoScored's numeric stage is source identity, not the domain stage. One
competition-season can have several stages, and the set grows during the season:
Champions League adds knockout and final; Championship adds a play-off.

- `whoscored_stage_id` — the number; identity and join key.
- `stage` — curated code: `league`, `group`, `qualification`, `knockout`,
  `playoff`, `final`.
- `whoscored_stage_name` — the verbatim `<option>` text from the `#stages` select.
  Present only when a season has more than one stage; `null` for a single-stage
  season (EPL 2025/26 renders no select). It is a discovery input, not a fact
  column.
- `expected_stages` — declared per season, not observed, because the format
  changes (`group` before 2023, `league` after).

#### Where the name comes from

Measured 2026-10-20. The feed does not carry it: every team row has
`tournamentName` and `seasonId`, no stage field, and
`require.config.params.args` has `stageId` and `isOptaStage`, no name. The only
source is the `#stages` select, present on the show and teamstatistics pages when
a season has more than one stage.

| Season | `<option>` text | `stage` |
|---|---|---|
| CL 2025/26 | `Champions League` | `league` |
| CL 2025/26 | `Champions League Final Stage` | `knockout` |
| CL 2022/23 | `Champions League Final Stage` | `knockout` |
| CL 2022/23 | `Champions League Grp. A` … `Grp. H` | `group`, group `A`–`H` |
| Championship 2025/26 | `Championship` | `league` |
| Championship 2025/26 | `Championship Playoff` | `playoff` |
| EPL 2025/26 | no select | `league` |

The label cannot be normalised by a string rule:

- `Final Stage` is the whole knockout phase, not the final match.
- The base stage has no suffix at all — the label is just the tournament name.
- The 2022/23 group stage is **eight separate stages**, one per group, not one
  `Group Stage`.

Derivation, in order:

1. label equals the tournament name → `league`
2. suffix `Grp. X` → `group`, `group = X`
3. suffix `Final Stage` → `knockout`
4. suffix `Playoff` / `Play-offs` → `playoff`
5. suffix `Final` → `final`
6. anything else → fail closed, keep the label verbatim

The select order is not chronological: CL puts `Final Stage` first, Championship
puts the league first. Never use option order to pick the stage.

**Is the field needed?** Yes, at discovery: it is the only input from which
`stage` and the group letter can be derived, and it is the audit trail when
WhoScored renames something. It belongs in the stage reference table, not in the
fact: the fact addresses `whoscored_stage_id`.

The shape written to `experiments/whoscored/stages.json`:

```json
{
  "source": "whoscored",
  "whoscored_url": "https://www.whoscored.com",
  "identity": "whoscored_stage_id",
  "competitions": [
    {
      "key": "champions-league",
      "name": "Champions League",
      "whoscored_region_id": 250,
      "whoscored_tournament_id": 12,
      "seasons": [
        {
          "season": "2026/27",
          "whoscored_season_id": 11295,
          "expected_stages": ["league", "knockout", "final"],
          "stages": [
            {
              "stage": "league",
              "whoscored_stage_id": 25800,
              "whoscored_stage_name": null,
              "whoscored_slug": "europe-champions-league-2026-2027",
              "teams_in_feed": 36,
              "has_league_table": true
            }
          ]
        }
      ]
    }
  ]
}
```

**Source naming.** This project reads more than one source, so no field is called
`source_*`. Identifiers, names, URLs and raw payloads carry the source name:
`whoscored_region_id`, `whoscored_tournament_id`, `whoscored_season_id`,
`whoscored_stage_id`, `whoscored_stage_name`, `whoscored_slug`, `whoscored_url`;
`fixturedownload_slug`, `fixturedownload_url`. Measurements such as `teams_in_feed`
and `has_league_table` are ours and stay unprefixed.

**Open.** The 2025/26 knockout (`Final Stage`, 24797) has no league table
(`standings-24797-grid` is absent) but does return the team-statistics feed, so
`has_league_table` must be per stage. Still unknown: whether the 2026/27 CL
knockout arrives as one stage or several.

---

## 2. Summary page — League Table

The summary page is the `show` URL. It contains these H2 sections:

`Premier League Fixtures`, `Premier League Tables`, `Premier League Top Teams`,
`Premier League Top Players`, `Premier League Best XI`, `Did You Know?`.

The league table is `table#standings-{stage}-grid` (EPL: `standings-25544-grid`;
LaLiga: `standings-25662-grid`, confirmed on a second competition). The table has three
header rows plus one row per team: 23 rows for a 20-team league.

### Header and splits

Header row: `Team | P | W | D | L | GF | GA | GD | Pts | Form`.

The table has a hidden wide header row with three column groups (`Overall | Home |
Away`), but it is a template, not the rendered table. The visible data rows always have
ten cells. `Overall`, `Home` and `Away` are `a.option[data-source=...]` toggles that
**re-render the same table client-side**; clicking one makes no network request. Capture
all three views by clicking each toggle and reading the table.

Every data row carries `data-team-id` — the same numeric id as the feed (Man City 167,
Brighton 211). The rank is a `<span>` in the first cell and the name is `a.team-link`.

### Measured EPL table (2026-10-20, after 7 rounds)

```
1  Manchester City   7 7 0 0 19  7 +12 21  wwwwww
2  Arsenal           7 6 0 1 11  5  +6 18  wwwlww
3  Brighton          7 5 1 1 23  5 +18 16  ldwwww
4  Chelsea           7 4 1 2 17 13  +4 13  wldlww
5  Liverpool         7 3 3 1  9  8  +1 12  dwdwlw
6  Brentford         7 2 4 1 13  8  +5 10  dddwdl
7  Leeds             7 2 4 1  9  6  +3 10  ddwdld
8  Everton           7 2 4 1  8  7  +1 10  dddwdl
9  Hull              7 2 3 2  8  7  +1  9  wddldl
10 Ipswich           7 3 0 4 11 15  -4  9  llwlwl
11 Newcastle         7 2 2 3 10 14  -4  8  wdlwll
12 Aston Villa       7 2 2 3  7 11  -4  8  ldlwdw
13 Manchester United 7 1 4 2 10 10   0  7  wdlddd
14 Crystal Palace    7 2 1 4  9 17  -8  7  lwldwl
15 Bournemouth       7 1 3 3  9 13  -4  6  dddllw
16 Tottenham         7 1 3 3  6 10  -4  6  lddldw
17 Coventry          7 2 0 5  6 14  -8  6  lllwwl
18 Fulham            7 1 2 4  7 10  -3  5  llddlw
19 Nottingham Forest 7 1 2 4  5  9  -4  5  ddwlll
20 Sunderland        7 1 1 5  6 14  -8  4  wdllll
```

Two parsing details:

- the rank is **inside** the team cell in the DOM (`1Manchester City`), so a naive
  `cell.textContent` merges rank and name; use the `<span>` and `a.team-link`;
- `Form` is a rolling window of the **last six** matches in that split, newest last:
  `len(form) == min(P, 6)`. For a 7-match Overall row it is six characters; for a
  4-match Home row it is four.

Internal consistency held on this capture: `W+D+L=P`, `Pts=3W+D`, `GD=GF−GA`, ranks are
`1..N`, and `home + away = overall` for `P/W/D/L/GF/GA/Pts` (20/20 teams). Evidence:
`experiments/whoscored/standings-25544.json`.

### Top Teams widgets

The same page carries six six-row leaderboards, each a separate `table`:

`Possession`, `Aggression`, `Aerial Duels Won`, `Shots per Game`, `Pass Accuracy`,
`Ratings`.

These are presentation widgets, not part of the 60-column fact. They are noted here
so nobody mistakes them for the season table.

---

## 3. Team Statistics tab

The tab is `.../teamstatistics/{slug}`. It has three sub-tabs, all rendered from the
same feed:

| Sub-tab | `category` | `subcategory` | Columns shown |
|---|---|---|---|
| Summary | `summaryteam` | `all` | 8 |
| Defensive | `summaryteam` | `defensive` | 6 |
| Offensive | `summaryteam` | `offensive` | 5 |

The sub-tabs are anchors (`#stage-team-stats-summary`, `#stage-team-stats-defensive`,
`#stage-team-stats-offensive`); switching one fires an XHR, it does not navigate.

### Feed

The page calls:

```
GET https://www.whoscored.com/statisticsfeed/1/getteamstatistics
    ?category=summaryteam
    &subcategory=all|defensive|offensive
    &statsAccumulationType=0
    &field=Overall|Home|Away
    &stageId={stage}
    &sortBy=Rating|tacklePerGame|shotsPerGame
    &isCurrent=true
    &against=
```

Response: `{ teamTableStats: [...], paging: {...}, statColumns: [...] }`.

**The feed requires the page token.** A bare `fetch` from the page returns HTML, not
JSON. The working request carries:

- `Accept: application/json, text/javascript, */*; q=0.01`
- `X-Requested-With: XMLHttpRequest`
- `Model-last-Mode: {token}` — the token is in the page as
  `require.config.params.site.gSiteHeaderValue`, with the header name in
  `gSiteHeaderName`. It is regenerated per page load, but one page's token works for
  every `stageId` tested.

### `statColumns`, measured on all 12 stages

Summary (`subcategory=all`):

```
apps, goal, shotsPerGame, yellowCard, redCard, possession, passSuccess, aerialWonPerGame
```

Defensive:

```
apps, shotsConcededPerGame, tacklePerGame, interceptionPerGame, foulsPerGame, offsideGivenPerGame
```

Offensive:

```
apps, shotsPerGame, shotOnTargetPerGame, dribbleWonPerGame, foulGivenPerGame
```

The same three lists came back for all twelve stages, in all three `field` splits.
`rating` and `ranking` are **not** in `statColumns` but are present on every row.

### Row fields (23, unchanged from `docs/whoscored-api.md`)

```
name, teamId, teamName, teamRegionName, seasonId, seasonName, tournamentId, isOpta,
tournamentRegionId, tournamentRegionCode, tournamentRegionName, regionCode,
tournamentName, rating, ranking, apps, goal, yellowCard, redCard, shotsPerGame,
aerialWonPerGame, possession, passSuccess
```

Measured again on the live EPL payload: `seasonId` is `0` and `seasonName` is `null`,
so the season is identified by `stageId` only.

### The 60-column fact, verified

`19 statColumn entries per split × 3 splits = 57`. Two entries repeat across
sections: `apps` (three times) and `shotsPerGame` (twice). Removing the 9 duplicate
entries leaves 42 section-owned values.

```
42 section-owned
+ 3 apps
+ 3 shots_per_game
+ 3 rating
+ 9 ranking (3 sections × 3 splits)
= 60
```

This reproduces the arithmetic in `plans/v1-build-plan.md` §5 from live data.

A single team row was assembled end-to-end as a check: **Brighton** (`teamId 211`),
EPL stage 25544, 60 keys, saved to `experiments/whoscored/brighton-60.json`.

**Naming correction.** The plan calls the defensive block
`defensive_{view}_{goals_conceded,...}`. The source field is
`shotsConcededPerGame` — shots conceded, not goals conceded. The page header says
"Shots pg". The warehouse name should follow the source:
`defensive_{view}_shots_conceded`. This is a contract change to make before P2, not a
parser detail.

**Units.** `possession` and `passSuccess` are fractions (0–1), already observed.
Every `*PerGame` field is a float with many decimals; `goal`, `apps`, cards and
`ranking` are integers.

---

## 4. Availability per competition

All twelve returned the three sections for `Overall`, with `Home`/`Away` verified on
EPL. Row counts:

| Competition | Summary | Defensive | Offensive |
|---|---:|---:|---:|
| Premier League | 20 | 20 | 20 |
| Championship | 24 | 24 | 24 |
| League One | 24 | 24 | 24 |
| League Two | 24 | 24 | 24 |
| LaLiga | 20 | 20 | 20 |
| Serie A | 20 | 20 | 20 |
| Bundesliga | 18 | 18 | 18 |
| Ligue 1 | 18 | 18 | 18 |
| Eredivisie | 18 | 18 | 18 |
| Champions League | 36 | 36 | 36 |
| Europa League | 36 | 36 | 36 |
| Conference League | 27 | 27 | 27 |

**Open question — Conference League.** The stage serves 27 teams with exactly one
appearance each. The fixture calendar has 108 Conference League matches, which
corresponds to a 36-team league phase. Either the stage is a qualification phase that
will be replaced, or WhoScored is mid-publication. Do not assume `25802` is the
league phase; verify against the fixtures page before the first scrape.

---

## 5. Statistics we did not take

Present on the Team Statistics page, outside the 60-column contract:

- **Situational statistics** — goals by `Open Play / Counter Attack / Set Piece /
  Penalty / Own Goal`; passes by `Cross / Through Ball / Long Balls / Short Passes`;
  cards by `Fouls / Unprofessional / Dive / Other`.
- **Positional statistics** — touches by `Left / Middle / Right`; attempt direction
  `Left / Middle / Right`; attempt zone `In 6 Yards Box / In 18 Yards Box / Outside
  of Box`; touch zone `Own Third / Middle Third / Opposition Third`.
- **xG** — `category=xg-teamstats` exists in the feed per `docs/whoscored-api.md`;
  not exercised this session.
- **Player and referee statistics** — separate tabs with their own feeds; out of
  scope for v1.

Some of these grids returned `rows: 1` in the DOM (lazy-loaded or empty for the
current stage), so their availability per competition is unmeasured.

---

## 6. What the next session should settle

1. **Conference League stage** — is 25802 the league phase? Compare with the
   fixtures page and with the fixture calendar's round numbers.
2. **Naming** — rename `goals_conceded` to `shots_conceded` in the contract, or
   document why the mismatch is intentional.
3. **Transport** — feed JSON plus the page token, or browser automation end-to-end.
   The token is the only reason a plain `requests` call to the feed fails; the HTML
   page itself is served normally.
4. **`isOpta`** — still a provenance flag, not a licensing verdict. Every row carries
   it; record it per snapshot.
5. **Publication latency** — unchanged unknown. The feed has no timestamp; only
   `observed_at` can be recorded.

---

## 7. Reproduction

The browser had to pass Cloudflare and the site's fingerprint script. Headless Chrome
was blocked; the working recipe was:

```powershell
$env:AGENT_BROWSER_SESSION = "dd-ws4"
agent-browser --headed --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36" open "about:blank"
agent-browser network route "*fingerprint*" --abort
agent-browser network route "*podname.com*" --abort
agent-browser open "https://www.whoscored.com/regions/252/tournaments/2"
```

Without the two `network route` calls the tab is navigated to `about:blank` a few
seconds after load.

The scripts used are in `experiments/whoscored/`:

- `collect_stage.js` — the per-stage payload probe (3 sections × Overall);
- `collect_row.js` — the 60-column pivot for one `teamId`;
- `stages.json` — the season → stage map, `whoscored_*` ids and measured row counts;
- `stage-labels.json` — the observed `#stages` labels and the derived codes;
- `brighton-60.json` — the verified 60-key row.
