# Detailed team statistics ingestion plan

**Status:** proposal · **Date:** 2026-10-27
**Scope:** add WhoScored `Detailed` team tab (23 category/subcategory pairs x 3 venues, `statsAccumulationType=1`) alongside the existing 9-feed v1 path. No change to the 60-column v1 contract.
**Evidence:** live `patchright` probes 2026-10-27 on LaLiga `stageId=25662` (`teamstatistics/spain-laliga-2026-2027`).

## 0. Measured facts (do not re-derive)

- Detailed URL: `/regions/{r}/tournaments/{t}/seasons/{s}/stages/{stage}/teamstatistics/{slug}`. Tab `#stage-team-stats-detailed` lazy-loads; first detailed fetch is `category=shots&subcategory=zones`.
- Category select `#category` (16 values): `tackles, interception, fouls, cards, offsides, clearances, blocks, saves, shots, goals, dribbles, possession-loss, aerial, passes, key-passes, assists`.
- Subcategory matrix (measured by selecting every category):
  - single (`#subcategory` disabled, value implied): tackles/success, interception/success, fouls/type, cards/type, offsides/type, clearances/success, blocks/type, saves/shotzone, dribbles/success, possession-loss/type, aerial/success, assists/type (12 pairs).
  - multi: shots/zones,situations,accuracy,bodyparts (4); goals/zones,situations,bodyparts (3); passes/length,type (2); key-passes/length,type (2).
  - Total: **23 pairs**. Full header list captured in probe `show_matrix.py` run (e.g. shots/zones -> Total/OutOfBox/SixYardBox/PenaltyArea).
- Feed template (all 23 fire identically):
  `GET /statisticsfeed/1/getteamstatistics?category=<cat>&subcategory=<sub>&statsAccumulationType=1&field=<Overall|Home|Away>&tournamentOptions=&timeOfTheGameStart=0&timeOfTheGameEnd=5&teamIds=&stageId=<id>&sortBy=Rating&sortAscending=&page=1&numberOfTeamsToPick=&isCurrent=true&formation=&incPens=&against=`
- `statsAccumulationType=1` = Per 90. Changing `#statsAccumulationType` alone fires **0 requests**; it persists and applies to the next fetch. Spider sets the query param directly.
- `field`: `Overall|Home|Away` via `.field-option` links (`data-option-value`). Default `field=""` is only the pre-click state; request `Overall` explicitly.
- Fixed: `formation=""` (All), `time 0-5` (= 0-90), `teamIds=""` (all teams, one call), `page=1`, `sortBy=Rating`, `against=""`, `incPens=""`.
- Gate behaviour (unchanged, `docs/research/whoscored-api.md`): Cloudflare TLS + Oddschecker fingerprint; 200-with-HTML gate page; trips after a handful of rapid requests, persists minutes. `403` terminal, `429` honours `Retry-After` (cap 60s).

## 1. Volume and pacing budget

- Per stage: 23 x 3 = **69 requests**. Full registry (12 stages): **828 requests**.
- At 1.5-2.0s + jitter: ~2 min/stage, ~25 min/full sweep plus backoff. Never parallelise per IP; one browser session, strictly sequential.
- Cap: one stage per run by default; multi-stage runs split across windows. Resume at `(stage, category, subcategory, view)` granularity.

## 2. Spider design (senior rules)

1. **One session per run.** `capture_stage`-style headed Chromium (`src/dataderby/page.py:340`), abort `*fingerprint*`, load `teamstatistics` URL, click `#stage-team-stats-detailed`, read `gSiteHeaderValue` token once. All 69 feeds via `page.evaluate(fetch)` (`_FEED_JS`) reusing cookies + `Model-last-Mode`. No `curl_cffi` second session, no per-combo page reloads, no UI clicking per combo (UI clicks cost the same request but add flakiness; single-subcategory selects are disabled anyway).
2. **Request order:** fixed pair order (alphabetical category, then subcategory as listed), venues inner loop `Overall, Home, Away`. Deterministic order = resumable + diffable logs.
3. **Politeness:** `collect_feeds` pacing (`src/dataderby/page.py:228`): 1.5-2.0s, jitter, `RequestBudget(limit=80)` per stage, max 3 attempts, exp backoff, `Retry-After` cap, `FetchBlocked` on 403 aborts the run (no retry storm). First request has no pre-sleep; every subsequent one sleeps.
4. **No amplification:** never set `teamIds`, `formation`, `timeOfTheGame`, `page`, `sortBy` per-team/per-minute. One call returns all ~18-36 teams.
5. **Contract-first validation:** `parse_envelope`-style check per pair: envelope keys + ordered `statColumns` pinned per pair (from the header capture above). Mismatch -> `SchemaDrift` (block, keep raw as evidence). Team-id set must equal the v1 cohort for the stage.
6. **Raw is system of record:** extend `raw.py` naming to `detailed__<category>__<subcategory>__<view>.json` (new `(section, view)` keys, no overwrite of v1 files). Same atomic bundle + sidecar (`url, sha256, attempt, captured_at`). V1 `summary/defensive/offensive` path untouched.
7. **Separate facts, shared header:** v1 `fact_team_snapshot` (60 cols) is immutable. Detailed lands in a new `fact_team_detailed_snapshot(snapshot_id, whoscored_team_id, category, subcategory, view, stat_name, stat_value)` long/narrow table (one `sql/00N` file, never edit `001`). Avoids a 300+ column wide table when `statColumns` differ per pair and drift often.

## 3. Work phases

- **D0 lock matrix.** Commit the 23-pair table + per-pair `statColumns` from one `statsAccumulationType=1/Overall` pass as `tests/golden/detailed/`. One stage, paced, ~23 reqs. Human confirms headers match §0.
- **D1 contract + feed.** `contract.py`: `DETAILED_PAIRS`, `DETAILED_VIEWS`; `fetch.py`/`page.py`: generalise `feed_url` to accept `(category, subcategory, accumulation, field)` with defaults preserving the v1 9-feed signature. Unit tests against replay server; no live calls.
- **D2 landing.** Extend `_payloads`/`_read_bundle` keys to the `detailed__*` namespace; per-pair budget accounting in `RequestBudget`. Test: bundle round-trip, duplicate key rejected, resume skips completed pairs.
- **D3 parse.** Pure `parse_detailed.py`: envelope -> long rows; `None` for missing, never `0`; unknown column -> `SchemaDrift`. Golden tests per pair + team-set equality vs v1 cohort.
- **D4 store.** `sql/006_detailed.sql`: narrow fact table + FK to `competition_snapshot`; share `snapshot_id`/`observed_at` with the v1 run so detailed and summary stay joinable. `publish` inserts in the same transaction; conflict on `(parent, fingerprint)` still yields `no_change`.
- **D5 ops.** `cli run --stage X [--detailed-only|--skip-detailed]` (defaults: v1 only; detailed opt-in until stable). Preserve exit codes and `run/probe/replay/verify/freshness` signatures. `probe` gains `--detailed-pair category/subcategory` (1 feed).
- **D6 measure.** Night-window full sweep of 1 stage; record req count, gate hits, wall time in `docs/research/`. Sets the multi-stage schedule.

## 4. Reuse of previous scrapes

- V1 9 feeds stay the source of truth for cohort (`expected_teams`), `observed_at`, `snapshot_id`, and assertions A1-A22. Detailed never creates a snapshot alone; it attaches to the v1 run's snapshot.
- Token, session, raw-bundle, ledger, lock, and `replay --check` machinery reused unchanged.

## 5. Risks

| Risk | Mitigation |
|---|---|
| 828-req sweep trips the gate mid-run | per-stage runs, resume keys, stop on 403, `Retry-After` cap |
| `statColumns` drift per pair | pinned per-pair contract, `SchemaDrift` blocks publish, raw kept |
| Wide-table explosion | narrow `(category, subcategory, view, stat, value)` fact table |
| Breaking v1 | additive code paths, default `run` without detailed, existing tests untouched |
| UI-only quirks (disabled sub-select) | spider calls the feed API directly, never depends on select enabled state |

## 6. Acceptance

- `tests/test_detailed_*.py` green on replay server; no live test in suite.
- One LaLiga detailed stage lands 69 files, replays to the same fingerprint, publishes alongside v1 snapshot.
- Gates: `ruff format`, `ruff check`, `mypy main.py`, `pytest` (new tests mirror `src/dataderby/` modules).
