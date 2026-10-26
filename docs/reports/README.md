# Phase reports

One report per build phase, written before that phase is committed.

| Phase | Report | Status |
|---|---|---|
| P0 | [Skeleton and gates](p0-skeleton.md) | complete |
| P1 | [Decisions and stage registry](p1-decisions-config.md) | complete |
| P2 | [The contract](p2-contract.md) | complete |
| P3 | [Schema and DuckDB helpers](p3-schema.md) | complete |
| P4 | [Page, feeds, raw landing, and the run ledger](p4-fetch-raw.md) | complete |
| P5 | [Parse and canonicalise](p5-parse-canonical.md) | complete |
| P6 | [Publish, validate, and reconcile](p6-publish.md) | complete |
| P7 | [Consumer views](p7-views.md) | complete |
| P8 | [CLI, migration ledger, and CI](p8-cli-operations.md) | complete |

The reports record the commands that were run, the evidence they produced, and
any deviation from `plans/v1-build-plan.md`.

## Change reports

Reports for a single change that is not a build phase.

| Change | Report | Status |
|---|---|---|
| Timestamps | [TIMESTAMPTZ migration](timestamptz-migration.md) | complete |
| Live capture | [One real capture, and what it broke](live-capture.md) | complete |
| Live capture (deck) | [Companion slides](../live-capture-slides.html) | complete |
| All-league capture | [All-league capture](all-league-capture.md) | complete |

Every report follows [`TEMPLATE.md`](TEMPLATE.md). The rule is in
[`AGENTS.md`](../../AGENTS.md#documentation): a change without a report is not done.
