# Fetch policy

**Status:** complete
**Date:** 2026-10-26
**Issue:** #6
**Decision:** `docs/adr/0009-fetch-policy.md`

## Goal

Stop treating every failure the same way, and stop a retry storm from becoming a
flood.

Before this change the transport retried a `403` three times, ignored
`Retry-After` on a `429`, retried every non-200 status, and had no ceiling on the
number of requests a run could make. The browser transport added in #14 inherited
that shape.

## What changed

| File | Change | Why |
|---|---|---|
| `src/dataderby/fetch.py` | `RequestBudget`, `FetchBudgetExceeded`, `retry_after_seconds`; status policy in `FeedFetcher` | one place for the rules, shared by both clients |
| `src/dataderby/page.py` | 429 waits, 403 terminal, other 4xx terminal, budget consumed per attempt; JS returns `Retry-After` | the production transport follows the same rules |
| `src/dataderby/cli.py` | one budget per run: `max(20, 9 × stages × 2)` | a retry storm is bounded per run, not per feed |
| `src/dataderby/landing.py` | optional `requests` records attempts including retries | the ledger reports what was actually sent |
| `scripts/check_robots.py` | one-command robots record | evidence instead of memory |
| `tests/test_page.py`, `tests/test_fetch.py` | 429, 403, 404, budget, pacing | the policy is pinned |
| `docs/adr/0009-fetch-policy.md` | the decision | written once, linked from 0006 |

## Policy

| Status | Action |
|---|---|
| `200` + valid envelope | accept |
| `200` + gate page | retry, up to 3 |
| `200` + schema drift | fail immediately |
| `403` | fail immediately |
| `429` | wait `Retry-After` (cap 60 s), then retry |
| other `4xx` | fail immediately |
| `5xx`, timeout, connection error | retry with `2**attempt + jitter` |

`Retry-After` accepts seconds and HTTP-date. The cap is a safety rail.

The budget is `max(20, 9 × stages × 2)`. A single stage gets 20; all twelve get
216. The factor of two allows one retry per feed. Exhaustion raises
`FetchBudgetExceeded`, which maps to exit code `2`.

## Robots evidence

Checked 2026-10-26 with `scripts/check_robots.py`:

```
status: 200, bytes: 79
sha256: b19a61778e61dd3360ee3a5bc23b70790d8d05cd0538bb8ec8e6c294d9d2823f
Disallow: /accounts/  /predictions/  /users/
```

The stage pages and the feed are not disallowed. This is evidence, not a licence
verdict; ADR 0006 remains the licence record. Re-check with one command before a
new season.

## Tests

- A `429` with `Retry-After: 5` waits five seconds, then succeeds.
- A `403` makes one request and stops.
- A `404` makes one request and stops.
- A `500` still retries with the old backoff.
- A budget of two stops the run after two attempts.
- Pacing still inserts 1.2 s between successful requests.
- The legacy `FeedFetcher` follows the same status policy.

Gates: 216 tests pass; ruff, mypy, and CI are green.

## Evidence

A live `probe` and a `--dry-run` after the change:

```
$ uv run dataderby probe --stage epl-2026-2027
epl-2026-2027: 20 teams, 9810 bytes, sha256 15d5bcc3737cb426

$ uv run dataderby run --stage epl-2026-2027 --dry-run
epl-2026-2027: would publish 20 teams, 20 standings rows, fingerprint ddd500267e1134f8
```

The normal path is unchanged; only the failure policy moved.

## Deviations and open items

- **`FeedFetcher` is legacy.** It has no production caller after #14, but its
  policy was aligned so the two clients cannot disagree. Remove it when the
  replay tests no longer need it.
- **The 60-second cap is a judgement.** It is long enough for a normal rate
  limit and short enough that a bad header cannot stall a run.
- **The budget is per run, not per host or per stage.** One stage failing cannot
  starve the next because the sweep shares the budget across the run.
- **Robots is recorded, not enforced per request.** That is deliberate; a
  per-request fetch would double the traffic.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| A 403 is transient after all | recorded as terminal; a human can re-run |
| `Retry-After` is a date in the past | clamped to zero |
| A retry storm hits the ceiling | `FetchBudgetExceeded`, exit 2 |
| The budget is too small for all leagues | 216 for 12 stages; one retry per feed |
| Robots changes silently | re-check before a season with one command |

## Reviewer checklist

- [ ] 403 terminal; 404 terminal; 500 retried.
- [ ] 429 waits for the header, capped.
- [ ] Budget counts attempts, including retries.
- [ ] The ledger's `http_requests` includes retries.
- [ ] Robots hash and date are in the ADR.
- [ ] Live dry-run still matches the fixture fingerprint.

## References

- `docs/adr/0009-fetch-policy.md`
- `docs/adr/0006-source-use.md`
- `docs/reports/browser-transport.md`
- `scripts/check_robots.py`
