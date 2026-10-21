# P4 - Page, feeds, raw landing, and the run ledger

**Status:** complete
**Date:** 2026-10-21
**Plan:** `plans/v1-build-plan.md` §7

## Goal

Capture one stage page, fetch the nine feed payloads, and land the complete sweep
as raw files with a durable run/raw ledger before any parsing.

## What was built

| Module | Responsibility |
|---|---|
| `src/dataderby/page.py` | Headed Patchright page capture; aborts fingerprint/podname requests; reads the token, stage labels, and the three standings tables. |
| `src/dataderby/standings.py` | Raw-row dataclasses, numeric conversion, rank/team/form validation, and JSON encode/decode for the archive. |
| `src/dataderby/fetch.py` | One feed URL builder, nine-feed scheduler, 1.2 s pacing, 2/4 s retries, BOM handling, gate detection, and schema-drift detection. |
| `src/dataderby/raw.py` | Atomic raw bundle, sidecar metadata, SHA-256, and no-overwrite behaviour. |
| `src/dataderby/landing.py` | One sweep: capture inputs, raw bundle, `ingestion_run`, and `raw_capture` rows. |
| `src/dataderby/lock.py` | Cross-platform exclusive pipeline lock. |
| `src/dataderby/observe.py` | Append-only JSON-lines event log. |

### Page capture

- Chromium is headed; the two known anti-bot endpoints are aborted at the route
  layer.
- The page must expose `require.config.params.site.gSiteHeaderValue`; a missing
  token fails the capture instead of sending unauthenticated feed requests.
- The three standings views are read from `tr[data-team-id]`. Rank comes from the
  first cell's `span`, team name from `a.team-link`, and the remaining cells map
  to P/W/D/L/GF/GA/GD/Pts/Form.
- A stage without a `table[id^="standings-"]` returns an empty standings map.
  That is how a knockout stage is represented; the publish phase will decide
  whether a missing table is acceptable for the configured stage.

### Feed policy

- URLs are `statisticsfeed/1/getteamstatistics?stageId=...&category=...&subcategory=...`.
- Requests are spaced by 1.2 s, including retries.
- Three attempts are allowed; backoff is 2 s then 4 s.
- A 403 becomes `FetchBlocked` after the attempts.
- HTML, empty, truncated, and non-envelope bodies become `GatePage`; a valid
  envelope with changed `statColumns` becomes `SchemaDrift` immediately because
  it is not transient.
- A UTF-8 BOM is stripped before `json.loads`.
- The `Content-Type: text/html` header is not trusted as a gate signal: the real
  JSON response also uses that header.

### Raw bundle

The final path is:

```text
<raw-root>/<whoscored_tournament_id>/<whoscored_season_id>/
  <whoscored_stage_id>/<observed_at>/
```

`observed_at` is the minimum of the page and nine feed capture times and is
formatted as `YYYY-MM-DDTHH-MM-SS.ffffffZ`. The bundle contains:

- `page__show.html` plus `.meta.json`;
- `standings__overall|home|away.json` plus sidecars when a table exists;
- one `summary|defensive|offensive__overall|home|away.json` plus sidecar for
  each feed.

The bundle is written to a temporary sibling directory, fsynced file by file,
and renamed into place. An existing `observed_at` raises `FileExistsError`; a
second sweep with a new timestamp gets a new directory. Sidecars record URL,
status, content type, byte count, SHA-256, attempt, and capture time.

### Run ledger

`land_stage()` opens `ingestion_run` with `outcome='running'`, fetches the nine
feeds, writes the raw bundle, then commits the `raw_capture` rows and updates
`observed_at` and `http_requests`. The run deliberately remains `running`:
P6 owns the publish outcome. A fetch failure marks `fetch_failed`; any other
failure marks `crashed`. `raw_capture` inserts use `ON CONFLICT DO NOTHING`, so
replaying the same run keys does not add duplicate ledger rows.

The successful sweep writes 13 raw files: one page, three standings views, and
nine feeds. `http_requests` is 10: one page load plus nine feeds.

## Verification

`tests/test_fetch.py` runs a local HTTP replay server with the real `curl_cffi`
session and covers:

- nine captures in Summary/Defensive/Offensive order;
- BOM stripping;
- 403 -> `FetchBlocked`;
- empty, HTML, and truncated bodies -> `GatePage`;
- changed columns -> `SchemaDrift` with no retry;
- 500 retry, 2/4 s backoff, and 1.2 s pacing.

`tests/test_standings.py`, `tests/test_raw.py`, `tests/test_lock.py`,
`tests/test_observe.py`, and `tests/test_landing.py` cover:

- all three standings views, team-id preservation, form length/null rules, rank
  range, duplicate teams, and raw round-trip;
- bundle contents, sidecar hashes, no-overwrite, duplicate keys, and naive
  timestamps;
- lock exclusion and reuse;
- JSON-lines and verbose stderr logging;
- a full landed sweep with 13 files, 10 requests, and 13 ledger rows;
- idempotent raw-ledger inserts and failed-run handling.

Run on 2026-10-21:

```text
uv run ruff format --check
62 files already formatted

uv run ruff check
All checks passed!

uv run mypy main.py
Success: no issues found in 1 source file

uv run pytest
86 passed in 11.42s
```

## Open items

- The Patchright selectors and live token path have not been exercised against
  the real site in this phase; the tests use injected page/feed data and a local
  replay server.
- The Conference League 27-team anomaly and the 2026/27 knockout stage ids
  remain open from P1.
- `landing.py` leaves `ingestion_run.outcome='running'` by design; P6 must
  publish or explicitly fail it.
- A second sweep with the same `observed_at` is refused rather than reused. A
  retry policy that reuses the existing bundle needs a deliberate decision.
- E5 cadence measurement still needs the 2026-10-24 EPL window.
- There is no CI; all four gates are local.

## Next

P5: parse the nine feed payloads and three standings views into canonical
candidates, then publish snapshots in P6.
