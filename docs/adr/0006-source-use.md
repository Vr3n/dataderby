# 0006 - Source use and licence posture

**Status:** accepted, 2026-10-20
**Decision owner:** project owner
**Evidence:** `docs/whoscored-decisions.md`

## Context

WhoScored marks some stages with `isOpta`. The project owner reviewed the use of
the data and accepted it for this project on 2026-10-20. `isOpta` is provenance,
not a licensing verdict and not a failure condition.

## Decision

- The data may be used for this project under the owner's accepted decision.
- The operational posture is local and private:
  - raw payloads are never committed;
  - there is no public redistribution of the raw feed;
  - there is no bulk historical scrape beyond the configured seasons;
  - `isOpta` is stored as a boolean on the snapshot header.
- `isOpta` never gates ingestion. It is recorded and reported.
- If the project later publishes derived data, the redistribution terms must be
  re-checked; this decision covers the internal pipeline, not a public data
  product.
- The v1 licence gate is closed. The remaining M6 work is the written record,
  the backup/replay drill, and the scheduled-run evidence.

## Consequences

- A new season or a new use requires a new review, not a silent extension.
- Raw capture paths stay under `data/`, which is git-ignored.
- The README and the runbook must repeat the local/private posture.
- The source name remains in every source-derived identifier, including
  `whoscored_stage_id`, `whoscored_page_url`, and `whoscored_tournament_id`.

## Rejected alternatives

- **Treat `isOpta` as a licence failure.** It is not a licence verdict; doing so
  would block stages that are in scope.
- **Publish the raw feed.** Outside the accepted posture.
- **Leave the licence question implicit.** The owner's decision is recorded and
  linked from the plan and this ADR.
