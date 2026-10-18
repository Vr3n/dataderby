# 0001. Read the statistics feed, not the rendered DOM

Status: Accepted (2026-10-08)

## Context

`plans/scraper.md` asserted that the API "doesn't give all the data so we need to
scrape the html instead", and `plans/whoscored_competition_scraper.md` was written
around DOM selectors. Both are wrong for team statistics: the team statistics page
is a shell that renders itself from `GET /statisticsfeed/1/getteamstatistics`, which
returns 23 fields per team, while the page prints 7 of them and rounds every figure
to one decimal (`shotsPerGame` 21.428571 arrives as "21.4"; `possession`
0.687285714 arrives as "68.7%").

## Decision

Acquire team statistics from the statistics feed with `curl_cffi`, and use no
browser anywhere in the pipeline — discovery included, since region, tournament,
season and stage are all reachable from server-rendered HTML.

## Consequences

- Stored numbers keep the site's own precision, and 16 fields the page never shows
  (`teamId`, `apps`, `ranking`, `tournamentId`, region fields, `isOpta`) are available.
- The Oddschecker fingerprint gate becomes our problem instead: it returns HTTP 200
  with a ~775-byte HTML body, so the first non-BOM byte must be tested before parsing.
- `Patchright` and `.ws_state.json` are no longer needed for this scope.
