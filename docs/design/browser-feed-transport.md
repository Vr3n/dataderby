# Browser feed transport

**Status:** implemented in this change
**Issue:** #14
**Related:** `docs/reports/live-capture.md`, `docs/reports/all-league-capture.md`

## The short version

"Browser feed transport" is our name for **fetching the nine JSON feeds from
inside the site's own browser page**, instead of asking for them from a
standalone Python HTTP client. It is not an industry term; it is the mechanism
issue #14 is about.

## What "transport" means

Transport is **how the bytes travel from the source to our code**. It is separate
from:

- **what the bytes mean** — the JSON envelope, the 60 measures;
- **what we do with them** — parse, validate, publish.

The same data can arrive by file download, REST API, database connection, message
queue, or a browser session. The transport is the adapter.

## The two paths

| Path | Who asks | Result |
|---|---|---|
| The sweep (`scripts/audit_all_stages.py`) | JavaScript running inside the WhoScored page | `200` + JSON, 20 teams |
| `dataderby run` / `probe` before #14 | Python `curl_cffi` | `200` + an HTML page: "The page you requested does not exist" |

The second is the trap: **the status code is 200, but the body is an error page**.
A status check passes; only body validation catches it. The site binds the feed to
the session its own page created. Copying cookies and the user agent into `curl`
did not help; the verified page session is the transport.

## Why it matters

Without it, the pipeline can **parse and publish**, but it cannot **acquire**:

1. **No scheduled run.** `run` stops at the fetch step.
2. **No new snapshots.** The database only holds what was captured by hand.
3. **No freshness.** `v_pipeline_freshness` has nothing new to report.
4. **No coverage.** The 11-league result came from the sweep, not the product.

The sweep proved the data path. This change makes it the production path.

## The core data-engineering concepts

1. **The transport is part of the source contract.** A schema is not the whole
   contract; access is part of it. A source that only answers a verified session
   is a different integration problem from an open API.
2. **Separate acquisition from interpretation.** Capture bytes, store them raw,
   then parse. If the parser is wrong, replay; do not re-scrape.
3. **Classify failures correctly.** A `403`, a `429`, a timeout, a `200` with an
   error body, and a valid but empty payload are five different failures with
   five different responses.
4. **Validate the body, not the status.** The `200`/HTML case is the canonical
   example.
5. **Idempotency and backpressure.** Retries are safe because the publish is
   idempotent; pacing keeps the source healthy.
6. **Observability.** Record the URL, status, byte count, hash, attempt, and
   whether the body was a gate page.
7. **Adapters keep the domain portable.** `contract.py`, `parse.py`, and
   `publish.py` do not know whether bytes came from `curl` or a browser.

## What it does not solve

- It does not make the source stable; the HTML/JSON shape can still change.
- It does not remove the need for robots/ToS review or rate limits.
- It does not make the browser cheap; it makes it correct.
- It does not replace raw storage or assertions; it feeds them.

## Design

The browser is opened once per stage, not once per feed.

```
capture_stage(url, spec)
  open headed Chromium
  read the page: token, stage labels, three standings views
  for each feed:
      pace (1.2 s)
      page.evaluate(fetch(url))     # same session, same origin
      validate the envelope
      build a Capture
  close the browser in finally
  return StageCapture(page, feeds)
```

Key points:

- `collect_feeds` is a separate function with an injected `fetch_one` callable.
  The browser wiring is thin; the retry, pacing, and validation logic is tested
  with fakes, so CI never launches a browser.
- Retries follow the existing policy: at most three attempts, backoff
  `2**attempt + jitter`. A `200` with a gate page is retried; schema drift is
  raised immediately because a changed column list is not transient.
- `land_stage` accepts the already-fetched feeds, so `run` does not fetch twice.
- `probe` uses the same path with a one-feed filter (`summary/overall`).
- The browser is closed on every path, including failure.

## What is still open

- `429`/`Retry-After` handling and the request ceiling are implemented in
  `docs/adr/0009-fetch-policy.md` (#6).
- The robots position is recorded in the ADR, not checked at runtime. Re-check
  it with `scripts/check_robots.py`.

## Sources

- `docs/reports/live-capture.md` — the 200/HTML evidence.
- `docs/reports/all-league-capture.md` — the 108-feed sweep.
- Issue #14 in the repository tracker.
- `src/dataderby/page.py`, `src/dataderby/fetch.py`.
