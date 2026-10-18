# 0003. Key a season on its tournament and its label together

Status: Accepted (2026-10-08)

## Context

Region 206 alone has six tournaments, and LaLiga, Copa del Rey and Segunda
División all label their current season `2026/2027` — with season path ids 11213,
11436 and 11214 and different stages. A canonical `2026-2027` that the domain
model can express is therefore not unique, and the collision is invisible while
only one tournament is in scope.

## Decision

Key a season on the pair `(tournament_id, season_key)`, both in the domain model
and in the output filename (`4_2026-2027.json`), and carry `stage_id` as
provenance rather than as identity.

## Consequences

- The readable season label from the original plan survives, and the key is unique
  without dragging the region into it, since `tournament_id` is globally unique on
  Whoscored.
- Every consumer must treat the pair as the key; the filename stays self-describing
  but `season_key` alone is only half a key.
- A stage change mid-season produces a new `stage_id` against the same key, which
  is intended.
