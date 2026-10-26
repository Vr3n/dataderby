# 0002 - Store full precision, round at presentation

**Status:** accepted, 2026-10-21
**Evidence:** `docs/research/whoscored-api.md`, the nine captures at `recon-evidence`

## Context

The source sends whole-number counts as JSON numbers, but some of them arrive as
floats (`31.0` for goals, yellow cards, and red cards). Ratings and per-game
averages have decimals. Rounding at ingestion would make two different source
observations compare equal and would hide a correction.

## Decision

- Store the value as it arrived, at the type declared by the contract:
  - counts as `INTEGER`;
  - goals, cards, ratings, possession, pass success, and per-game averages as
    `DOUBLE`;
  - form as `VARCHAR`.
- Never coerce a float count to an integer at ingestion.
- Round only in a presentation layer or a query, never in the fact.
- A missing value is `NULL`; a zero is a real zero.
- `NaN` and `inf` are rejected before they reach SQL.

## Consequences

- `31.0` and `31` are the same value and are stored consistently.
- A correction of `0.1` is visible in the fingerprint.
- A consumer that wants one decimal applies `round()` at read time.
- The schema's `CHECK (col >= 0)` allows `NULL`, because a missing measure is
  not a negative one.

## Rejected alternatives

- **Round at ingestion.** Loses the evidence and makes canonicalisation
  machine-dependent.
- **Store only text.** Pushes numeric semantics to every consumer and defeats
  the 60-column contract.
- **Treat `NULL` as `0`.** Invents a measurement the source did not publish.
