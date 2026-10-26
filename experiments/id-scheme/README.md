# Snapshot identity experiment

Two candidate schemes for `competition_snapshot.snapshot_id`, run through the same
pipeline, the same data and the same 24 failure cases. Everything except the id and the
uniqueness constraint is shared code.

Read `SPEC.md` first, then `results/summary.md`. Two narrative versions exist:

* `docs/reference/snapshot-identity-review.html` — the review deck: built to be presented to
  senior engineers and to close the decision. Press `N` in the deck for talking points.
* `docs/reference/id-scheme-report.html` — the original, shorter write-up of the same results.

## Layout

```
SPEC.md              protocol, KPI definitions, test list
common.py            fixtures, canonicalisation, schema, publish loop
suite.py             24 tests -> results/<scheme>.json ; --compare -> summary.md
final_metrics.py     one coherent perf/storage/address pass -> results/final.json
backfill.py          mid-chain insert -> results/backfill.json
perf.py              repeated insert timing -> results/perf.json
analysis.py          canonicalisation + spurious-version checks
approaches/
  a_derived/         hash(parent, stage, content), PK dedupe
  b_ulid/            ULID, UNIQUE(parent, content), genesis sentinel
  b_null/            trap variant: NULL parent at the root
probes/              one-off measurements (DuckDB parameter binding, file size)
fixtures/caps/       the nine real captures from tag recon-evidence (f5c1e35)
results/             committed outputs; work/ is generated and ignored
```

## Run

```powershell
cd experiments/id-scheme
uv run --no-project --with duckdb python suite.py --approach a
uv run --no-project --with duckdb python suite.py --approach b
uv run --no-project --with duckdb python suite.py --approach bnull
uv run --no-project --with duckdb python suite.py --compare
uv run --no-project --with duckdb python final_metrics.py
uv run --no-project --with duckdb python backfill.py
```

`--no-project` keeps the benchmark out of the application's dependency set. DuckDB 1.5.6,
Python 3.12.13.

## Result

| | A-derived | B-ulid | B-null |
|---|---|---|---|
| tests | 24/24 | 21/24 | 20/24 |
| exact rebuild reproduces ids | yes | no | no |
| report pinned to `snapshot_id` after rebuild | 20 rows | 0 rows | 0 rows |
| report pinned to `(stage, observed_at)` after rebuild | 20 rows | 20 rows | 20 rows |
| downstream ids changed by one backfill | 5/5 | 5/5 | 5/5 |
| storage per snapshot (300) | 14 022 B | 14 896 B | not measured |
| insert p50 (300) | 76.1 ms | 83.3 ms | — |
| id length | 37 | 26 | 26 |

## Findings

1. **Idempotency is the transaction, not the id.** All eight retry/crash cases pass for
   every scheme. Header, fact and checkpoint commit together.
2. **A derived id reproduces only an identical replay.** Insert one missed observation in
   the middle and every later id changes, because each child hashes its parent's id.
3. **No row id is an address.** A report pinned to `snapshot_id` returns 0 rows after a
   backfill in both schemes. The same report pinned to `(stage, observed_at)` returns all
   20 rows in both. The observation is the address; the id is lineage.
4. **A NULL parent silently duplicates the first row.** Measured 2 rows for one
   observation. `parent_snapshot_id NOT NULL DEFAULT 'genesis'` is mandatory.
5. **Dedupe must be on the edge, not the content.** A→B→A is three observations; a
   content-only key loses the revert.
6. **Insert path beats id design.** On this DuckDB build, parameter binding costs ~4 ms
   per value: a 20×62 insert is 2 485 ms parameterised, 27 ms as literals, 73 ms via
   `COPY`. Fix the load path first.

## Adopted

ULID `snapshot_id` + `UNIQUE (parent_snapshot_id, content_fingerprint)`, genesis sentinel,
and reports pinned to `(stage_id, observed_at)`. See plan §4.4.
