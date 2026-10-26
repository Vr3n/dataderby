# 0003 - Two clocks

**Status:** accepted, 2026-10-21
**Evidence:** `docs/research/whoscored-cadence.md`, header probes from 2026-10-20

## Context

WhoScored publishes no timestamp in the page, the JSON feed, or the HTTP
headers that describe the content. `Last-Modified` is the response time, not the
observation time. A single sweep also spans several requests, so there is no
single instant at which the whole observation existed.

## Decision

Use two clocks with different jobs:

- `observed_at` is the minimum capture time across the page, the three
  standings views, and the nine feed calls. It is an interval, not an instant.
  Store `capture_span_seconds` beside it. Order history and select "latest" by
  `observed_at`.
- `accepted_at` records when the database transaction committed. It is an
  audit value, is not reproducible, and never orders history.

`observed_at` is fixed before the first request for a run. A run whose span
exceeds 180 seconds is retried rather than accepted.

## Consequences

- A backfill with an older `observed_at` does not become latest.
- A delayed commit does not reorder a snapshot.
- The report address is reproducible from the capture times.
- The raw archive and the header agree on the interval that produced the row.

## Rejected alternatives

- **One `created_at`.** Confuses observation with commit and makes a backfill
  silently win.
- **Use HTTP `Date`.** It is the server's clock and the response time, not the
  publication time.
- **Use the match kickoff.** The feed has no match grain and no source event
  time; kickoff would be an invented attribution.
