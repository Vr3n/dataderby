# 0001 - Immutable snapshot facts

**Status:** accepted, 2026-10-21
**Decision owner:** project owner
**Evidence:** `experiments/id-scheme/results/summary.md`,
`docs/snapshot-identity-review.html`

## Context

The WhoScored feed has no event timestamp and no match-level grain. One sweep
returns the current cumulative state of one stage. A team can disappear from the
feed, a value can be corrected, and a re-fetch can return the same bytes again.
The warehouse needs to preserve every accepted observation without pretending
that an update in place is a history.

## Decision

Store one immutable `competition_snapshot` header per accepted observation,
with one `fact_team_snapshot` row per team and one
`fact_standings_snapshot` row per team in the same transaction.

The snapshot has:

- a ULID `snapshot_id`, used as a stable name in the database;
- `parent_snapshot_id`, the previous accepted snapshot for the same address, or
  `'genesis'`;
- `UNIQUE (parent_snapshot_id, content_fingerprint)` as the idempotency guard;
- `UNIQUE (tournament_id, whoscored_season_id, whoscored_stage_id, observed_at)`
  as the address guard;
- `observed_at` as the ordering key and `accepted_at` as the commit record.

Facts address the header by `snapshot_id`. They never carry `observed_at`.
Reports address `(tournament_id, whoscored_season_id, whoscored_stage_id,
observed_at)` and never persist `snapshot_id`.

## Consequences

- A retry of the same content against the same parent writes nothing.
- A revert A -> B -> A is three snapshots, not a collapsed pair.
- A backfilled older observation cannot become "latest".
- A rebuild can produce different ids but the same content fingerprint.
- A report is stable across rebuilds because it does not depend on the id.

## Rejected alternatives

- **Mutable current-state table.** Loses history and makes a correction
  indistinguishable from a new observation.
- **Content hash as the primary key.** A revert and a duplicate become
  indistinguishable; the edge is the dedupe, not the id.
- **Report stores `snapshot_id`.** A rebuild would silently break the report.
