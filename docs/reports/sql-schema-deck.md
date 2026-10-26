# SQL and schema deck

**Status:** complete
**Date:** 2026-10-26
**Deck:** `docs/slides/sql-schema-slides.html`

## What it covers

A 28-slide explanation of the database design, in the paper/editorial theme:

1. The three questions the schema answers: what was true, when, and was it the
   same observation.
2. A glossary of grain, key, foreign key, check, unique, snapshot, assertion,
   SCD2, EAV, surrogate key, and materialized view.
3. The seven tables and seven views, with an ER diagram that distinguishes
   declared foreign keys from unconstrained links.
4. The decisions, each with the rejected alternative: the migration ledger vs
   `CREATE IF NOT EXISTS`, snapshots vs SCD2, header + facts vs one flat table,
   wide measures vs EAV/long, natural keys vs surrogate keys, constraints vs
   application validation, `ON CONFLICT` vs check-then-insert, one transaction vs
   a staging table, SQL assertions vs a test framework, views vs materialized
   views, `TIMESTAMPTZ` vs naive timestamps, DuckDB vs PostgreSQL/Parquet, and
   literal inserts vs parameter binding.
5. How it behaves: accepted, `no_change`, reconcile, freshness.
6. Evidence: 216 tests, 11 live leagues, the Southampton −4 deduction.
7. What would change at scale: partitioning, `dim_team`, materialized views,
   PostgreSQL, orchestration.

## Provenance

The HTML was drafted by a background agent, which failed upstream before writing
this report. The deck was reviewed against the SQL and reports, its test count
was corrected from 202 to 216, and the missing report was written here. No SQL,
code, or test was changed for the deck.

## Verification

- 28 `<section class="slide">`, 28 presenter notes, no placeholders.
- No unclosed tags; the inline GSAP script passes `node --check`.
- Rendered every slide at 1600×900: no clipped content. The cover's pitch graphic
  extends beyond the stage by design.
- Links resolve, including this report and `sql/001`–`003`.
- Every number cross-checked against `sql/`, the P3/P6/P7 reports, and the
  all-league sweep.

## Reviewer checklist

- [ ] The ER diagram matches `sql/001_schema.sql`.
- [ ] The transaction slide matches `publish.py`.
- [ ] A1–A21 + A7U are described correctly (22 definitions).
- [ ] Test count is 216.
- [ ] The close links to this report.

## References

- `docs/slides/RULES.md` — deck rules.
- `sql/001_schema.sql`, `002_assertions.sql`, `003_views.sql`.
- `docs/reports/p3-schema.md`, `p6-publish.md`, `p7-views.md`.
- `docs/adr/0003`, `0005`, `0007`, `0008`.
