# WhoScored refresh cadence

**Measured 2026-10-20 · EPL stage 25544 · for the schedule decision.**

The user asked how to find the refresh cadence. This is the answer: there is no
source timestamp to read, so the cadence must be measured with a probe around a
match window (experiment E5, already in the plan). Everything below is the
evidence and the provisional schedule to use until E5 reports.

---

## 1. What the source does and does not tell us

Probed from a live page, 2026-10-20 10:32–10:36 UTC:

| Signal | Value | Verdict |
|---|---|---|
| `cache-control` | `private, max-age=120` | 2-minute cache; do not poll faster |
| `expires` | request time + 120 s | same |
| `etag` | absent | no strong validator |
| `last-modified` | request time (10:33:24, then 10:35:24) with an identical body | **response time, not data time — do not store it as an update timestamp** |
| `cf-cache-status` | `DYNAMIC` | not served from a shared edge cache |
| Conditional `If-Modified-Since` | 304 for 10:32:20, 200 for 09:00 and 2020 | works, but see the caveat below |
| Feed top-level keys | `teamTableStats`, `paging`, `statColumns` | no timestamp |
| Page `<time>` / "last updated" / `data-updated` | none | no timestamp |
| Feed latency | 0.5–0.7 s per call | nine calls ≈ 5 s of response time |

**Caveat on 304.** Because `last-modified` is the response time, a 304 proves only
that the server's content build time is at or before the value we sent. Treating a
304 as "no change" is safe only after it is confirmed against a known data change.
Until E5 confirms it, log the 304 and keep the checkpoint row, but do not let it
skip the standings read.

**No timestamp anywhere.** The source publishes no event time. `observed_at` stays
our clock, as §4.2 of the implementation plan already says.

---

## 2. The page is not optional in a sweep

The league table is client-rendered from the page. Clicking `Overall`, `Home` or
`Away` re-renders the same 10-column table **without a network request**, so:

- a plain HTML fetch gives only `Overall`;
- a rank or form change can happen with no feed change;
- a feed change can happen with no rank change.

Therefore a sweep must load the page, read all three standings views and mint the
`Model-last-Mode` token, then make the nine feed calls. The page load is the
expensive part; twelve page loads a day is still trivial.

Measured on the same page:

- `tr[data-team-id]` on every data row — the standings join key, the same numeric
  `teamId` the feed uses (Liverpool 26, Man City 167, Arsenal 13, Brighton 211).
- The rank is a `<span>` inside the first cell; the name is an `a.team-link`.
- Ten columns per split: `P W D L GF GA GD Pts Form` for all three splits.
- `Form` is a rolling window of the **last six** matches in that split
  (`len(form) == min(played, 6)`; NULL only when `played = 0`); it is not one character
  per season match.
- Internal consistency held on the 2026-10-20 capture: `W+D+L=P`, `Pts=3W+D`,
  `GD=GF−GA`, ranks are a permutation of `1..N`, and `home + away = overall` for
  `P/W/D/L/GF/GA/Pts`. The capture is `experiments/whoscored/standings-25544.json`.

---

## 3. How to measure the cadence (E5)

E5 is already in the implementation plan: *"Publication latency after a final
whistle? Probe every 5 min across a match window — a distribution, not a number."*
The probe is now executable.

1. Open one stage page and keep it open (token + DOM).
2. Every 5 minutes from the first kickoff to 6 hours after the last kickoff:
   - read the three standings views;
   - fetch the nine feed payloads;
   - record `observed_at`, the two hashes, `max(played)`, rank and form;
   - record whether the body changed since the previous probe.
3. The first probe that shows a change after a final whistle gives
   `first_change_lag` for that match. Collect one value per competition per
   matchday; E5 closes when there are at least two matchdays.
4. Report p50 and p95, not a single number.

The probe logs **raw hashes** (`standingsHash`, `feedHash`). The published
`content_fingerprint` is canonical and also covers the two facts; use it for the
snapshot decision, not the raw hash.

**Window.** The next EPL round has a 00:30 IST match on 24 Oct
(Ipswich–Nott'm Forest), then 17:00, 19:30 and 22:00 IST (Chelsea–Spurs last). Two
useful windows: 2026-10-23 22:00 → 2026-10-24 04:00 IST for the early match, and
2026-10-24 22:00 → 2026-10-25 04:00 IST for the last one. The second is the better
single run.

An earlier option is the UEFA league phase on 2026-10-22 00:30 IST onward, but one
competition on one matchday is a cleaner sample than several competitions at once.

**Script.** `experiments/whoscored/cadence_probe.ps1` runs the loop and appends
JSONL. The parse prototype is `experiments/whoscored/collect_standings.js`.

**Do not** poll faster than the 2-minute cache; 5 minutes is the practical floor.
Nine feed calls at 1.2 s spacing plus a page load is about 15 s per competition per
sweep — 12 competitions is under 4 minutes.

---

## 4. Provisional schedule (use until E5 reports)

| When | What | Why |
|---|---|---|
| 06:00 IST daily | one snapshot per competition | catches overnight results, late corrections and multi-day moves |
| last kickoff + 2 h, + 6 h | snapshot only for competitions with a fixture in the last 24 h | provisional: catch the result and any late correction; E5 replaces the offsets with a measured p95 |
| weekly | stage discovery (read `#stages`) | new stages appear mid-season (CL knockout, Championship playoff) |
| 24 h after the last fixture | freshness check: `max(played)` vs the fixture calendar | alerts if the source is behind a round; no team-name join needed |

Rules that apply to every sweep:

1. One page load per competition; reuse the token for all nine calls and all
   stages of that competition.
2. Send `If-Modified-Since` from the last **200** response for the nine feed
   calls. On `304`, reuse the last raw payload and still run the canonical
   fingerprint; never skip the standings read. Do not treat `304` as proof of
   no change until E5 checks it against a known match.
3. A new snapshot only when `content_fingerprint` changes; the fingerprint covers
   the 60 stats **and** the three standings views.
4. `observed_at` is our clock; store the capture span (nine feeds plus the page
   read and three toggles).
5. Keep the raw page and the three standings views as raw artifacts (decision 5).

## 5. What to do about it

- Do not hardcode a cadence now. Run E5 on 2026-10-24 and replace the provisional
  schedule with `last_kickoff + p95_lag`, floored at 30 minutes and capped at 6
  hours.
- Until then ship the daily heartbeat plus the post-matchday sweeps above.
- Keep the daily heartbeat even after E5: it is the only detector for retroactive
  corrections (E3) and it is cheap.
- Re-measure if the source changes its cache headers or the gate behaviour
  changes (E6 logs the gate rate).

---

## 6. Reproduce

```powershell
$env:AGENT_BROWSER_SESSION = "dd-whoscored"
agent-browser open "about:blank"
agent-browser network route "*fingerprint*" --abort
agent-browser network route "*podname.com*" --abort
agent-browser open "https://www.whoscored.com/regions/252/tournaments/2/seasons/11141/stages/25544/show/england-premier-league-2026-2027"
$js = Get-Content experiments\whoscored\collect_standings.js -Raw
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($js))
agent-browser eval -b $b64
```

The page must be a stage page, not the tournament page: the tournament page has
no `table[id^="standings-"]`.