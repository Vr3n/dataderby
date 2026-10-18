# WhoScored team statistics scraper

Scope: LaLiga-family team statistics, acquired from the statistics feed, stored as
one wide row per team per season.

Vocabulary is defined in `CONTEXT.md`. Decisions with a real cost are recorded in
`docs/adr/`.

## Scope

**In scope**

- One region list as input; tournaments, seasons and stage ids discovered from
  server-rendered HTML.
- The last 3 seasons of every tournament in a region.
- The **Summary**, **Defensive** and **Offensive** sections, each in the
  **Overall**, **Home** and **Away** views. Nine requests per season.
- One JSON file per (tournament, season), wide rows, raw feed precision.

**Out of scope, deferred by name**

- The **xG** section (same endpoint, adds a category, two filters and a penalties
  switch).
- The **Detailed** section (16 categories × 4 breakdowns × 4 units per view; volume
  unmeasured).
- The situation and pitch tables. These are a **second endpoint**
  (`/stagestatfeed/<stage_id>/stageteams/`) whose payloads are positional arrays
  with no field names, so they need their own mapping before they can be stored.
- Player statistics, match and event-level data.
- Ingestion into the columnar store. This plan ends at typed rows on disk.

## Corrections to the earlier plans

These were verified against the live site on 2026-10-08 and replace what
`plans/scraper.md` and the previous revision of this file said.

| Earlier claim | Verified reality |
| --- | --- |
| Tournaments are read from `MainNavigation > tournamentsDropdownContainer > tournamentNavButtons > a.TournamentNavButton` | No such elements exist. `TournamentNavButton` does not appear in the HTML at all. Tournaments come from `select#tournaments`. |
| "The api doesn't give all the data so we need to scrape the html instead" | Inverted. The feed returns 23 fields per team; the page renders 7. See ADR 0001. |
| Season id is the option's `<start_year>-<end_year>` text | The option text is `2026/2027` (slash). Separately, that label is not unique across tournaments. See ADR 0003. |
| A stage's statistics are reached from the season select | The `stageId` is in no select. It appears only in the `require.config.params.args` block embedded in a stage's own page. |
| All three table families come from one endpoint | Families 1 and 2/3 use different endpoints. See Deferred. |

## Verified facts

### Discovery

All of the following is reachable with the existing `curl_cffi` session, plain
HTTP 200, no browser.

- A tournament page, e.g.
  `https://www.whoscored.com/regions/206/tournaments/14/spain-copa-del-rey`,
  carries `select#tournaments` and `select#seasons`.
- `select#tournaments` is **region-scoped**: on a Spanish page it holds 6 options
  (`LaLiga`=4, `Copa del Rey`=14, `Supercopa de Espana`=61, `Segunda División`=63,
  `Liga F`=744, `Primera Division RFEF`=318).
- `select#seasons` holds ~27-28 options. Option value shape:
  `/Regions/<region_id>/Tournaments/<tournament_id>/Seasons/<season_path_id>/<country>-<tournament>`
  and text `2026/2027`. This is the **only** place `season_path_id` appears.
- Option values are HTML-entity-escaped *and* percent-encoded, e.g. Segunda División
  arrives as `.../spain-segunda-divisi&#37;C3&#37;B3n`. Unescape, then unquote.
- `stageId` comes from the embedded args block on a stage's page:
  `require.config.params['args'] = { tournamentId: 4, stageId: 25662, touchChannels: [...], goalTypes: [...], teamsPlayed: [...] }`
- No regions list exists in the HTML: `id="regions"` count is 0, `regionId` count is
  0, and the only 5 `/regions/` links all point at region 206. Hence ADR 0004.

### The statistics feed

```
GET https://www.whoscored.com/statisticsfeed/1/getteamstatistics
    ?stageId=25662
    &category=summaryteam
    &subcategory=defensive|offensive|...
    &statsAccumulationType=0
    &field=Overall|Home|Away
    &sortBy=<section's default metric>&sortAscending=false
    &isCurrent=true
    &formation=&timeOfTheGameStart=&timeOfTheGameEnd=
    &teamIds=&against=&tournamentOptions=&incPens=
    &page=&numberOfTeamsToPick=
```

- Requests captured live for Defensive and Offensive confirm this shape
  (`sortBy=tacklePerGame` and `sortBy=shotsPerGame` respectively).
- Response: `{"teamTableStats": [...], "paging": {...}, "statColumns": [...]}`.
- 20 team rows, 23 fields each:
  `name, teamId, teamName, teamRegionName, seasonId, seasonName, tournamentId,
  isOpta, tournamentRegionId, tournamentRegionCode, tournamentRegionName,
  regionCode, tournamentName, rating, ranking, apps, goal, yellowCard, redCard,
  shotsPerGame, aerialWonPerGame, possession, passSuccess`
- `seasonId` is always `0` and `seasonName` always `null` — the feed never names
  its own season. `paging` is all zeros and must not be relied on.
- `statColumns` for the summary category is
  `["apps","goal","shotsPerGame","yellowCard","redCard","possession","passSuccess","aerialWonPerGame"]`
  — note it **excludes** `rating` and **includes** `apps`. Treat it as authoritative
  for the metric field list of that response, and carry `rating` and `ranking`
  alongside.
- `possession` and `passSuccess` are fractions (0..1); the page renders them as
  percentages.

### Source behaviour

- **Gate**: HTTP 200 with a ~775-byte HTML body for the feed. The body and the real
  payload both begin with a UTF-8 BOM, so strip the BOM first and then require the
  first byte to be `{` or `[`. The existing `_is_gate` in `src/dataderby/client.py`
  does exactly this.
- Observed during this session: the gate returned for some requests while sibling
  requests in the same session returned real data, and once engaged it did not clear
  within 30s of backoff. Treat it as intermittent, not as a per-IP constant.
- **Block**: sustained browsing of the site triggered a hard Cloudflare block
  (`Sorry, you have been blocked` / `Attention Required! | Cloudflare`) with zero
  tables in the DOM. The feed was unaffected at the time. This is a second failure
  mode and must not be mistaken for the gate.

## Design

### Identity

- `season_key` = the season label with `/` replaced by `-` (`2026-2027`).
- Season identity is the pair `(tournament_id, season_key)`, and the output filename
  is the same pair: `4_2026-2027.json`.
- Carried as provenance, not as identity: `region_id`, `country_slug`,
  `tournament_id`, `tournament_name`, `season_path_id`, `stage_id`.

### Requests

Sections in scope, all under `category=summaryteam`:

| Section | subcategory | Notes |
| --- | --- | --- |
| Summary | `all` | unverified — `statsAccumulationType=0`, `field=Overall` |
| Defensive | `defensive` | captured live |
| Offensive | `offensive` | captured live |

Views: `field=Overall`, `field=Home`, `field=Away`.

Nine requests per season. Do **not** trust a hardcoded field list: take
`statColumns` from each response and assert that the field set is non-empty and that
`rating` is present on each row.

### Row shape

One row per team, keyed by `teamId`:

```
{
  "team_id": 65,
  "team_name": "Barcelona",
  "ranking": 1,
  "summary_rating": 7.22,
  "summary_overall_goal": 31.0,
  ...one column per statColumns entry, per section, per view...
  "defensive_overall_tacklesPerGame": 20.0,
  "offensive_overall_shotsOnTargetPerGame": 8.3
}
```

- Column name = `<section>_<view>_<field>` where `field` is the feed's own field
  name, verbatim. Prefixing every column means no section can silently overwrite
  another; `rating` exists in all three sections and would otherwise collide.
- Values are stored exactly as the feed sends them, unrounded. See ADR 0002.
- A metric the feed omits or sends as null is stored as JSON `null`, never as `0`.

### Pacing and failure

- Sequential, with a jittered pause between requests. Single-flight, never a
  fan-out. Reuse the existing gate retry in `get_json`.
- If any of the nine requests still fails after its retries, the season fails and
  **nothing** is written for it. Partial seasons are not written.
- Detect the hard block as well as the gate, and distinguish them in the error:
  they have different remedies, and a block will not clear by retrying.

## Implementation

1. **Discovery** (`src/dataderby/discovery.py`)
   - `tournaments(session, region_id, region_slug) -> list[Tournament]` from
     `select#tournaments` on the region's page.
   - `seasons(session, tournament) -> list[Season]` from `select#seasons`.
   - `stage_id(session, season) -> int` by fetching the season's team statistics page
     and reading `stageId` out of the embedded args block.
   - One helper to unescape + unquote option values, used by all three.
2. **Feed access** — `get_team_statistics` in `src/dataderby/client.py` already
   accepts `category`, `subcategory`, `field`, `against` and `sort_by`. No change
   needed beyond pacing.
3. **Assembly** — for each section and view, fetch, read `statColumns` from the
   response, and fold rows into the wide row keyed by `teamId`. Fail the season if
   the team set differs between views.
4. **Output** — one JSON file per `(tournament_id, season_key)`.
5. **CLI** — arguments for the region list and the season window (default 3).

Keep the season window as a parameter with a documented default, so a backfill is
configuration rather than a code change.

## Verification

- `uv run ruff format`, `uv run ruff check`, `uv run mypy main.py`, `uv run pytest`
  per `AGENTS.md`.
- The cross-check test compares our wide rows against `get_team_statistics` called
  directly, so a field-name or section-mapping mistake fails loudly rather than
  writing plausible numbers. Mark it and **skip it by default**, because the gate
  refuses requests for minutes at a time and `pytest` must pass offline.
- Assert per season: 20 teams, identical team sets across all nine views, no column
  entirely null, `rating` present, percentages in 0..1.
- Leave one runnable check behind for the parse of option values, since that
  double-encoding (`&#37;C3&#37;B3n`) is the single most breakable detail here.

### To confirm on first live run

Two facts are taken from the earlier design deck rather than verified by direct
request, and the implementation should assert rather than assume them:

- the **Summary** section's `subcategory` (`all` vs `summary`);
- the field lists `statColumns` returns for **Defensive** and **Offensive**, which
  the deck claims are 6 and 5 columns against Summary's 8.

Taking `statColumns` from each response makes both self-resolving: the assertion
records what actually arrived.
