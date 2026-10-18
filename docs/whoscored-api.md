# WhoScored — API & Site Analysis

Reverse-engineering notes for building a scraper. Focus is the **static season
statistics** (team + player). Match/event data is only summarised at the end.

All findings below were observed live unless explicitly marked
`NEEDS-VERIFICATION` or `INFERRED`.

---

## 0. TL;DR

- WhoScored has a real **JSON API** for season stats: `/statisticsfeed/1/...`.
- It is protected by **Cloudflare (TLS fingerprint)** + an **Oddschecker
  fingerprint gate** (`verify-client.js`, FingerprintJS).
- **Stock `curl`/`requests` get `403`.** Use `curl_cffi` with
  `impersonate="chrome"`, or a real browser.
- The gate returns a **~778-byte HTML page with HTTP 200** when it trips.
  Detect it, back off, retry.
- **Gotcha:** the JSON response starts with a UTF-8 BOM (`\ufeff`) and is served
  with `Content-Type: text/html`. Naive gate detection misreads valid JSON as
  the gate. Strip the BOM before checking.
- Happy path is a **single request, ~0.6s**.

---

## 1. Endpoints at a glance

| Data | Method | URL | Format |
|---|---|---|---|
| Team season stats | GET | `https://www.whoscored.com/statisticsfeed/1/getteamstatistics` | JSON |
| Player season stats | GET | `https://www.whoscored.com/statisticsfeed/1/getplayerstatistics` | JSON |
| Match event data | GET | `https://www.whoscored.com/matches/{matchId}/live/{slug}` | HTML (embedded JS) |
| Team page (embedded tables) | GET | `https://www.whoscored.com/regions/{r}/tournaments/{t}/seasons/{s}/stages/{stage}/teamstatistics/{slug}` | HTML |
| Player page (embedded filters) | GET | `.../playerstatistics/{slug}` | HTML |

Base: `https://www.whoscored.com`

---

## 2. Access, anti-bot, and gotchas

### 2.1 Cloudflare (TLS fingerprint)

Plain `curl` / `python-requests` → **HTTP 403** (Cloudflare block page), regardless
of headers. The block is on the **TLS/JA3 fingerprint**, not the User-Agent.

Fix: use `curl_cffi` with a browser impersonation:

```python
from curl_cffi import requests
s = requests.Session(impersonate="chrome")
```

A real browser (Playwright/agent browser) also works.

### 2.2 Oddschecker fingerprint gate

The `statisticsfeed` endpoints are additionally wrapped by WhoScored/Oddschecker's
own bot gate. When it trips, the API returns **HTTP 200** with a
**~778-byte HTML page**:

```html
<script src="https://cx-resources.oddschecker.com/fingerprint/verify-client.js?v1.0.1" defer></script>
...
The page you requested does not exist in WhoScored.com
```

`verify-client.js` is FingerprintJS + a POST to `/api/v1/ingest`; it issues the
`ua`, `ui`, `ocfp`, `UA-FP-Session-Id` cookies that unlock the feed. Cookies are
effectively **bound to the IP/session and expire**, so replaying a captured
cookie string only works for a while.

**Behaviour observed:** trips after a handful of rapid requests, then persists
for minutes. It comes and goes independently of request shape — identical
requests succeed and fail minutes apart.

**Practical strategy:**
- Happy path: 1 request ≈ 0.6s.
- Pace requests (e.g. 1–3s) and reuse one session.
- On gate: back off (start ~2s, exponential, cap ~20–60s) and retry.
- For volume: refresh `ua/ui` via a real browser context, and/or use residential
  proxies (rotate IP + cookie set together).

### 2.3 The BOM trap (important)

Successful JSON is served as:

```
Content-Type: text/html; charset=utf-8
Body: \ufeff{ "teamTableStats": [ ... ] }
```

The gate page **also** starts with `\ufeff`. So checking `body[:1] == "{"` fails
for both. Correct detection:

```python
def is_gate(content: bytes) -> bool:
    c = content.lstrip(b"\xef\xbb\xbf").lstrip()   # strip BOM + whitespace
    return c[:1] not in (b"{", b"[")
```

Parse with `json.loads(r.text.lstrip("\ufeff"))`.

### 2.4 Headers that worked

```http
Accept: application/json, text/javascript, */*; q=0.01
Accept-Language: en-US,en;q=0.9
X-Requested-With: XMLHttpRequest
Referer: <the stats page URL, e.g. .../teamstatistics/spain-laliga-2026-2027>
Model-last-Mode: <page's gSiteHeaderValue, optional>
Sec-GPC: 1
```

`Model-last-Mode` = the `gSiteHeaderValue` embedded in the page's
`require.config.params` block. Not required in tests, but the site sends it.

### 2.5 Cookies observed

`ocfp`, `UA-FP-Session-Id`, `__cf_bm`, `tzid`, `ui`, `ua`, `ft`, `odt`
(`ua`/`ui`/`ocfp` come from the fingerprint script; `__cf_bm` from Cloudflare).

---

## 3. Team season statistics

### 3.1 Request

```
GET https://www.whoscored.com/statisticsfeed/1/getteamstatistics
    ?category=summaryteam
    &subcategory=all
    &statsAccumulationType=0
    &field=Overall
    &stageId=25662
    &sortBy=Rating
    &isCurrent=true
    &against=
```

### 3.2 Categories / tabs

| Tab | `category` | `subcategory` |
|---|---|---|
| Summary | `summaryteam` | `all` |
| Offensive | `summaryteam` | `offensive` |
| Defensive | `summaryteam` | `defensive` |
| xG | `xg-teamstats` | `summary` |
| Detailed | *lazy-loaded* | `NEEDS-VERIFICATION` |

### 3.3 Query parameters

| Param | Meaning |
|---|---|
| `stageId` | **Which competition stage/season.** Primary key. |
| `category` / `subcategory` | Which table (see above). |
| `field` | Split: `Overall` \| `Home` \| `Away`. |
| `statsAccumulationType` | Accumulation mode; site sends `0` (Total). Others unused in recon. |
| `against` | `""` = For; non-empty = Against split. |
| `formation` | Filter by formation. |
| `incPens` | Include penalties. |
| `isCurrent` | `true` = current season. |
| `teamIds` | Filter to specific team(s), comma-separated. |
| `tournamentOptions` | Tournament filter. |
| `timeOfTheGameStart` / `timeOfTheGameEnd` | Minute range filter. |
| `sortBy` | Sort column (default `Rating`). |
| `sortAscending` | Sort direction (`""` = desc). |
| `page` | Pagination (empty = all). |
| `numberOfTeamsToPick` | UI picker count. |

### 3.4 Response

Top-level keys: `teamTableStats`, `paging`, `statColumns`.

```json
{
  "teamTableStats": [ { ...23 fields... } ],
  "paging": { "currentPage": 1, "totalPages": 0, "resultsPerPage": 0,
              "totalResults": 0, "firstRecordIndex": 0, "lastRecordIndex": 0 },
  "statColumns": ["apps","goal","shotsPerGame","yellowCard","redCard",
                  "possession","passSuccess","aerialWonPerGame"]
}
```

`statColumns` = the stat fields shown for this category (excludes metadata,
`rating`, `ranking`).

**Row fields (23):**

```
name, teamId, teamName, teamRegionName,
seasonId, seasonName, tournamentId, isOpta,
tournamentRegionId, tournamentRegionCode, tournamentRegionName,
regionCode, tournamentName,
rating, ranking, apps, goal, yellowCard, redCard,
shotsPerGame, aerialWonPerGame, possession, passSuccess
```

Notes:
- `possession` and `passSuccess` are **fractions 0–1** (×100 for %).
- `rating` ≈ 6.0–7.5.
- `seasonId` is `0` and `seasonName` is `null` even for a real season — don't
  rely on them; identify the season by `stageId`.

Example row:

```json
{"name":"Barcelona","teamId":65,"teamName":"Barcelona","teamRegionName":"Spain",
 "seasonId":0,"seasonName":null,"tournamentId":4,"isOpta":true,
 "tournamentRegionId":206,"tournamentRegionCode":"es","tournamentRegionName":"Spain",
 "regionCode":"es","tournamentName":"LaLiga","rating":7.22,"ranking":1,"apps":7,
 "goal":31.0,"yellowCard":8.0,"redCard":0.0,"shotsPerGame":21.43,
 "aerialWonPerGame":10.71,"possession":0.687,"passSuccess":0.904}
```

---

## 4. Player season statistics

### 4.1 Request

```
GET https://www.whoscored.com/statisticsfeed/1/getplayerstatistics
    ?category=summary
    &subcategory=all
    &statsAccumulationType=0
    &isCurrent=true
    &stageId=25662
    &tournamentOptions=4
    &field=Overall
    &sortBy=Rating
    &isMinApp=true
    &numberOfPlayersToPick=10
```

### 4.2 Categories / tabs

| Tab | `category` | `subcategory` |
|---|---|---|
| Summary | `summary` | `all` |
| Offensive | `summary` | `offensive` |
| Defensive | `summary` | `defensive` |
| Passing | `summary` | `passing` |
| xG | `xg-stats` | `summary` |
| Detailed | *lazy-loaded* | `NEEDS-VERIFICATION` |

### 4.3 Query parameters

All team params, plus player-specific:

| Param | Meaning |
|---|---|
| `playerId` | Filter to one player. |
| `matchId` | Restrict to a single match. |
| `age`, `ageComparisonType` | Age filter (e.g. `>`/`<`). |
| `appearances`, `appearancesComparisonType` | Min/max appearances. |
| `nationality` | Nationality filter. |
| `positionOptions` | Position filter. |
| `isMinApp` | Only players meeting a min-apps threshold. |
| `includeZeroValues` | Include players with zero for the stat. |
| `numberOfPlayersToPick` | UI picker count. |
| `page` | Pagination. |

### 4.4 Response

Top-level keys: `playerTableStats`, `paging`, `statColumns`.

La Liga 2026/27 `summary/all` returned **321 players**, 38 fields each.

**Row fields (38):**

```
height, weight, age, isManOfTheMatch, isActive,
playedPositions, playedPositionsShort,
teamRegionName, regionCode, tournamentShortName,
apps, subOn, manOfTheMatch, goal, assistTotal,
shotsPerGame, aerialWonPerGame,
name, firstName, lastName, playerId, positionText,
teamId, teamName, seasonId, seasonName, isOpta,
tournamentId, tournamentRegionId, tournamentRegionCode, tournamentRegionName,
tournamentName, rating, minsPlayed, yellowCard, redCard, passSuccess, ranking
```

Notes:
- `playedPositions` is a dash string, e.g. `-AMC-AML-AMR-FW-`;
  `playedPositionsShort` e.g. `AM(CLR),FW`.
- Example row: Raphinha, `playerId` 300447, `rating` top of table, `goal` 12,
  `assistTotal` 3.

---

## 5. Embedded page data (no API call)

The team page HTML embeds extra tables directly in
`require.config.params['args']`:

- `touchChannels` — Action Zones / touch data:
  `[[teamId, "Team", regionId, [values...]], ...]`
- `goalTypes` — Goal Types (situational): nested `[goalType, qualifier, foot, [count]]`
- `teamsPlayed` — Home/Away played split.

So the default Situational / Positional tables (Goal Types, Pass Types, Card
Situations, Attack Sides, Shot Directions, Shot Zones, Action Zones) need **no
API request** for the default `Overall`/`For` view.

Non-default views go through a datasource named **`ws-teams-stage-stat`**
(params: `{stageId, type, teamId, against, field}`; `type` seen: `2, 8, 11, 18, 25`).
**Endpoint URL: NEEDS-VERIFICATION** (not in the team bundle; likely a shared chunk).

---

## 6. Match data (appendix — not an API)

There is no JSON feed for match stats. `GET /matches/{id}/live/{slug}` returns a
full HTML page (≈1.2 MB) with `matchCentreData: {...}` embedded as a JS object
literal. It is **not** gated the same way.

Top-level keys include: `events` (all Opta events), `home`, `away`, `score`,
`htScore`, `ftScore`, `incidentEvents`, `playerIdNameDictionary`, `formations`,
`shotZones`, `referee`, `venueName`, `attendance`.

A parser that brace-matches from `matchCentreData:` is in
`src/dataderby/client.py::_extract_match_centre_data`. Full event/qualifier
enumeration is in `recon/analyze_match.py` and the sample
`samples/match_1914253.json`.

---

## 7. Reference IDs (La Liga 2026/2027, verified)

| Item | Value |
|---|---|
| `tournamentId` | `4` |
| `stageId` | `25662` |
| `tournamentRegionId` | `206` |
| `regionCode` | `es` |
| `tournamentName` | `LaLiga` |
| season slug | `spain-laliga-2026-2027` |
| season path id | `11213` |

`stageId` is the key you need for stats calls. Find it from the tournament page
URL: `/regions/{regionId}/tournaments/{tournamentId}/seasons/{seasonId}/stages/{stageId}/...`

---

## 8. Minimal scraper

```python
import json, time
from curl_cffi import requests

API = "https://www.whoscored.com/statisticsfeed/1/getteamstatistics"

def is_gate(b: bytes) -> bool:
    c = b.lstrip(b"\xef\xbb\xbf").lstrip()
    return c[:1] not in (b"{", b"[")

s = requests.Session(impersonate="chrome")
s.headers.update({
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.whoscored.com/",
})

params = {"category": "summaryteam", "subcategory": "all",
          "statsAccumulationType": "0", "field": "Overall",
          "stageId": 25662, "sortBy": "Rating", "isCurrent": "true", "against": ""}

for attempt in range(5):
    r = s.get(API, params=params, timeout=20)
    if r.status_code == 200 and not is_gate(r.content):
        data = json.loads(r.text.lstrip("\ufeff"))
        break
    time.sleep(min(20, 2 * 2 ** attempt))       # gate / rate limit
else:
    raise SystemExit("gated out")

teams = data["teamTableStats"]                   # list[dict], 20 rows for La Liga
```

Runnable example: `examples/team_season_stats.py`.

---

## 9. Open questions

- `detailed` tab `category`/`subcategory` for both team and player pages.
- `ws-teams-stage-stat` endpoint URL (situational/positional non-default views).
- Values/meaning of `statsAccumulationType` other than `0`.
- Rate-limit thresholds per IP and reset window (empirically: a few requests,
  then minutes of gating).

---

## 10. Repo artifacts

| Path | What |
|---|---|
| `src/dataderby/client.py` | Working client (session, team/player/match, gate detection + backoff) |
| `examples/team_season_stats.py` | Runnable team-stats example with logging |
| `samples/team_summaryteam_all.json` | Raw team response (La Liga 2026/27) |
| `samples/match_1914253.json` | Raw `matchCentreData` sample |
| `recon/tables-tournament-team.js` | Team page bundle (tabs/params) |
| `recon/ttp.js` | Player page bundle |
| `recon/verify-client.js` | Oddschecker fingerprint script |
| `recon/analyze_match.py` | Dumps full match schema/event/qualifier enumeration |
| `recon/capture_samples.py` | Batch capture helper |
