# Browser feed transport

**Status:** complete
**Date:** 2026-10-26
**Issue:** #14
**Design:** `docs/design/browser-feed-transport.md`

## Goal

Make `dataderby run` and `dataderby probe` fetch the feeds the way the sweep
does: from inside the site's own browser page. Before this change the commands
used a standalone HTTP client and received a `200` with an HTML page saying the
page did not exist. The pipeline could parse and publish, but it could not
acquire.

## What changed

| File | Change | Why |
|---|---|---|
| `src/dataderby/page.py` | `StageCapture`, `collect_feeds`, `capture_stage`; `_read_page` extracted | one browser session for the page and its feeds |
| `src/dataderby/landing.py` | `feeds=` parameter; `fetcher` is optional | do not fetch twice when the browser already has the bytes |
| `src/dataderby/cli.py` | `Runtime.sweep` replaces `capture` + `make_fetcher`; `run`, `--dry-run`, and `probe` use it | the commands now share the production transport |
| `tests/test_page.py` | four transport tests | retries, pacing, filter, schema drift |
| `tests/test_pipeline_cli.py` | fake sweep instead of fake fetcher | same CLI behaviour, new seam |
| `tests/test_landing.py` | pre-fetched feeds bypass the fetcher; missing source raises | the new contract is pinned |

## Design

One browser per stage, not one per feed. The page is read once (token, labels,
standings), then nine feeds are requested by JavaScript in that page, 1.2 s
apart. Each body is validated against `statColumns` before it becomes a
`Capture`. The browser closes in `finally`.

`collect_feeds` is deliberately separate from the browser:

```python
collect_feeds(spec, token, fetch_one, only=None, pacing=1.2, max_attempts=3)
```

`fetch_one` returns `(status, body, content_type)`. In production it runs
JavaScript in the page; in tests it returns canned bytes. Retry, pacing, and
envelope rules are therefore tested without a browser, and CI never opens one.

Retry semantics match the old client: three attempts, backoff
`2**attempt + jitter`, `403` becomes `FetchBlocked`, a `200` gate page is retried,
and schema drift is raised immediately.

## Evidence

Live, against the source:

```
$ uv run dataderby probe --stage epl-2026-2027
epl-2026-2027: 20 teams, 9810 bytes, sha256 15d5bcc3737cb426

$ uv run dataderby run --stage epl-2026-2027 --dry-run
epl-2026-2027: would publish 20 teams, 20 standings rows, fingerprint ddd500267e1134f8

$ uv run dataderby run --stage epl-2026-2027
epl-2026-2027: accepted (20 teams, run run_a1b52edd...)

$ uv run dataderby run --stage epl-2026-2027
epl-2026-2027: no_change (20 teams, run run_841b3a0b...)

$ uv run dataderby verify
OK headers without team facts 0
OK team facts without a header 0
OK duplicate parent + fingerprint edges 0
OK snapshots with an unexpected team count 0
```

The dry-run fingerprint `ddd50026...` equals the committed live fixture, so the
browser transport and the fixture agree.

The database now holds one snapshot, one `accepted` run and one `no_change` run;
`v_pipeline_freshness` reports `age_seconds = 114`.

Gates: 209 tests pass; `ruff format --check`, `ruff check`, and `mypy main.py`
pass; CI runs on Ubuntu and Windows.

## Deviations and open items

- **`capture_stage` does not abort the fingerprint scripts**, while the older
  `capture_page` still does. The sweep proved the non-aborting path works for the
  feeds; `capture_page` is retained for compatibility.
- **`429`/`Retry-After` and the per-run request ceiling are not here**; they are
  #6. This change keeps the old retry shape.
- **The browser is headed.** A scheduled run needs a desktop session or a
  virtual display; making it headless is a separate decision with its own
  detection risk.
- **`capture_page` now has no production caller.** It stays as the page-only
  API; remove it when nothing else uses it.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Browser leaks on failure | `finally: browser.close()` on every path |
| A feed returns a 200 error page | body validation, not status, decides |
| A retry duplicates data | publish is idempotent; the second live run returned `no_change` |
| Headed browser cannot run on a server | documented; virtual display is the next step |
| Transport logic drifts from the old client | `collect_feeds` tests cover pacing, retries, gate pages, and drift |

## Reviewer checklist

- [ ] `run`, `--dry-run`, and `probe` use `capture_stage`.
- [ ] No code path fetches the feeds twice.
- [ ] `land_stage` rejects a call with neither fetcher nor feeds.
- [ ] A gate page retries; schema drift does not.
- [ ] The live dry-run fingerprint matches the fixture.
- [ ] Browser is closed on success and failure.

## References

- `docs/design/browser-feed-transport.md` — the concept and the design.
- `docs/reports/live-capture.md` — the 200/HTML evidence.
- `docs/reports/all-league-capture.md` — the 108-feed sweep.
- Issue #14 in the repository tracker.
