# Live WhoScored fixture

One real capture of the 2026/27 Premier League stage, taken on 2026-10-26.

| Field | Value |
|---|---|
| Stage key | `epl-2026-2027` |
| `whoscored_tournament_id` | 2 |
| `whoscored_season_id` | 11141 |
| `whoscored_stage_id` | 25544 |
| Teams | 20 |
| Captured at | 2026-10-26T07:34:46Z |

## What is here

- `summary__{overall,home,away}.json` — the three summary feeds.
- `defensive__…` and `offensive__…` — the other six feeds.
- `standings__{overall,home,away}.json` — the page's league table for each split.
- `manifest.json` — the stage address, capture time, and a SHA-256 per file.

## Redaction

The fixture contains no token, cookie, request header, or session identifier. The
capture tool refuses to write a file containing any of those markers. Team names and
match statistics are public data; the payloads are the feed bodies the parser
consumes, not a browser session.

This is **not** a raw bundle. Raw bundles live under `data/raw/` and stay
git-ignored (`docs/adr/0004-raw-is-system-of-record.md`). The fixture is a
redacted, minimal extract kept so the parser has a real input in CI.

## Regenerating

```bash
uv run python scripts/capture_live_stage.py \
  --stage epl-2026-2027 \
  --out tests/fixtures/whoscored/epl-2026-2027-25544 \
  --force
```

The tool needs a headed browser and a live session. When the capture changes, the
fingerprint pinned in `tests/test_live_fixture.py` must be updated deliberately —
a change means the source content changed, not that the test is flaky.
