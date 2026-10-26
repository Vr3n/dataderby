# 0009 - Fetch policy

**Status:** accepted, 2026-10-26
**Issue:** #6
**Related:** `docs/adr/0006-source-use.md`, `docs/design/browser-feed-transport.md`

## Context

The feed is a session-bound source: it returns JSON inside the site's own page
and a `200` HTML error page to a standalone client (`docs/reports/live-capture.md`).
That makes the fetch path part of the data contract, not an implementation
detail.

Three failure modes needed a written policy:

1. **A denied request (403)** was retried three times. A denial is a policy
   answer, not a transient error; repeating it is impolite and wastes the budget.
2. **A rate limit (429)** was treated as a generic failure, so `Retry-After` was
   ignored.
3. **A loop bug** could turn nine requests into ninety. The run recorded a count
   after the fact but had no ceiling.

## Decision

### Status handling

| Status | Action | Why |
|---|---|---|
| `200` + valid envelope | accept | the normal path |
| `200` + gate page | retry, up to 3 attempts | a gate can be transient |
| `200` + changed `statColumns` | fail immediately | a schema change is not transient |
| `403` | fail immediately (`FetchBlocked`) | a denial is a policy answer |
| `429` | wait `Retry-After`, capped at 60 s, then retry | the server named the delay |
| other `4xx` | fail immediately | the request is wrong; retrying repeats it |
| `5xx`, timeout, connection error | retry with `2**attempt + jitter` | transient |

`Retry-After` accepts both HTTP forms: a number of seconds and an HTTP-date. The
60-second cap prevents a hostile or mistaken header from stalling a run.

### Request budget

Every run carries a `RequestBudget`. The CLI sets it to
`max(20, 9 × stages × 2)`:

- 9 feeds per stage;
- a factor of two for one retry per feed;
- a floor of 20 for a single stage or a probe.

A budget exhaustion raises `FetchBudgetExceeded` and exits `2` (`fetch_failed`).
The budget counts attempts, including retries, so a retry storm stops at the
ceiling rather than at the end of the sweep.

### Politeness floor

- 1.2 seconds between requests, including retries (retry delay is additional).
- At most three attempts per feed.
- No bulk historical scrape. The registry covers the current season only
  (`docs/adr/0006-source-use.md`).

### Robots

The file was checked on **2026-10-26** with `scripts/check_robots.py`:

```
status: 200
bytes: 79
sha256: b19a61778e61dd3360ee3a5bc23b70790d8d05cd0538bb8ec8e6c294d9d2823f
User-agent: *
Disallow: /accounts/
Disallow: /predictions/
Disallow: /users/
```

The stage pages and the statistics feed are **not** in the disallowed list. This
is evidence, not a licence verdict; the licence posture stays in ADR 0006.

The check is **not** performed per request. It is a recorded position, re-checked
with one command before a new season or when the source changes:

```bash
uv run python scripts/check_robots.py
```

### Client identity

The production feed request is made by the site's own page in a headed browser,
because the endpoint requires that session. The legacy `curl_cffi` client
impersonates Chrome. Both are recorded here rather than left as a surprise in
code. If the project ever publishes derived data, this decision must be reviewed
with ADR 0006.

## Consequences

- A `403` now stops the run after one request; the ledger records `fetch_failed`
  or `blocked` according to the CLI mapping.
- A `429` respects the server's delay instead of guessing.
- A retry storm is bounded.
- The robots position has a date, a hash, and a command to refresh it.
- A source that returns a valid but empty payload is still accepted; emptiness is
  a data problem, not a transport problem (see the Conference League case in
  `docs/reports/all-league-capture.md`).

## Rejected alternatives

- **Retry 403.** A denial repeated is still a denial.
- **Ignore `Retry-After` and use the fixed backoff.** The server told us the
  delay; guessing is worse.
- **Fetch robots.txt before every request.** It would double the request count
  and add a failure mode for no benefit. Record it, re-check on a schedule.
- **No budget, rely on the sweep finishing.** The budget is the guard against a
  loop, which is exactly when nobody is watching.
- **Treat an empty payload as a transport failure.** It is a valid envelope with
  zero rows; the cohort assertion is the right place to decide.

## Review

Re-run `scripts/check_robots.py` before a new season, after a long pause, or when
the source changes its access rules. Update the hash and date in this ADR if the
file changes.
