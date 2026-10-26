# WhoScored reconnaissance — 2026-10-20

What was measured, and how to repeat it. The readable summary is
`docs/research/whoscored-competition-links.md`; this folder holds the raw bits.

## Files

| File | What it is |
|---|---|
| `stages.json` | The 12 competitions, nested as season → stage, with `whoscored_*` ids, stage codes and the measured feed row count |
| `stage-labels.json` | Observed `#stages` labels for CL 2025/26, CL 2022/23, Championship 2025/26 and the no-select EPL case |
| `brighton-60.json` | One fully assembled 60-column row (Brighton, EPL, stage 25544) |
| `collect_stage.js` | Fetches the three Overall sections for one stage |
| `collect_row.js` | Fetches 9 payloads and pivots one team into the 60-column shape |
| `collect_standings.js` | Reads Overall/Home/Away from the stage page into JSON |
| `standings-25544.json` | Verified EPL standings capture, 3 splits, 20 teams |
| `cadence_probe.js` | One fingerprint of standings + 9 feeds, for E5 |
| `cadence_probe.ps1` | Runs the fingerprint every N minutes, appends JSONL |
| `cadence-sample.json` | One probe result (hashes, leader, byte count) |

`collect_stage.js`, `collect_row.js`, `collect_standings.js` and `cadence_probe.js` run
**inside** a whoscored.com tab, not in Node. `collect_stage.js` and `collect_row.js`
need `__STAGE__` / `__TEAM__` replaced; the other two run as-is on a stage page. Base64
the text and pass it to `agent-browser eval -b`.

## Why the browser

The feed rejects a plain request: without the page token the response is HTML. The
working recipe:

```powershell
$env:AGENT_BROWSER_SESSION = "dd-whoscored"
agent-browser --headed --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36" open "about:blank"
agent-browser network route "*fingerprint*" --abort
agent-browser network route "*podname.com*" --abort
agent-browser open "https://www.whoscored.com/regions/252/tournaments/2"
```

Then, inside the page:

```js
const site = require.config.params.site;
// site.gSiteHeaderName  === "Model-last-Mode"
// site.gSiteHeaderValue === per-page token
```

The token is regenerated per page load but works for every `stageId` tested.

## The page is also the standings source

The stage page is not just the token dispenser. It carries the league table, and the
table is client-rendered:

- `table[id^="standings-"]`, 10 columns per split (`P W D L GF GA GD Pts Form`);
- `Overall / Home / Away` are `a.option[data-source=...]` toggles; clicking one
  re-renders the table without a network request;
- `tr[data-team-id]` is the join key — the same numeric id as the feed;
- rank is a `<span>` in the first cell, the name is `a.team-link`;
- `Form` is the last six matches in that split, so `len(form) == min(P, 6)`.

A knockout stage has no table; that is zero rows, not an error. The verified capture
is `standings-25544.json`. Do not use the tournament page for this: it has no
`table[id^="standings-"]`.

## Cadence

There is no source timestamp. The feed has no time field, the page has no "last
updated", and `Last-Modified` is the response time (two identical bodies returned
different values). `cache-control: private, max-age=120` sets a 2-minute floor.

`cadence_probe.ps1` is the E5 instrument: it reads the three standings views, fetches
the nine feed payloads, hashes both, and appends one JSON line every 5 minutes. Run it
on a matchday. The method, the evidence and the provisional schedule are in
`docs/research/whoscored-cadence.md`.

## Findings that changed the plan

1. **`shotsConcededPerGame`, not goals conceded.** The defensive block is shots
   conceded. `defensive_{view}_goals_conceded` in `plans/v1-build-plan.md` is a
   misnomer; use `shots_conceded`.
2. **The 60-column arithmetic reproduces on live data** — 42 + 3 + 3 + 3 + 9 = 60.
   No extra fields were needed and no `statColumns` entry was missing.
3. **Conference League is suspicious** — 27 teams with one appearance each, while
   the fixture calendar has 108 matches. Verify the stage before trusting it.
4. **Source fields name the source.** `whoscored_stage_id` is identity; `stage` is
   the domain code (`league`, `group`, `knockout`, `playoff`, `final`). No field is
   called `source_*`, because the project reads more than one source.
5. **The stage name is only in the page, not the feed.** The `#stages` select
   carries `Champions League Final Stage`, `Championship Playoff`, `Grp. A`, and so
   on. It exists only when a season has more than one stage. `Final Stage` maps to
   `knockout`, not `final`; the 2022/23 group stage is eight separate stages.
   See `stage-labels.json`.

## What was not measured

- Conference League stage mapping.
- Situational / positional grids (some rendered with one row).
- xG feed (`xg-teamstats`).
- Player and referee statistics.
- Publication latency and retroactive corrections. E5 is the measurement; the
  provisional schedule is in `docs/research/whoscored-cadence.md`.
