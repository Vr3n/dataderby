# Experiment: snapshot id scheme

Two candidate schemes for `competition_snapshot.snapshot_id`, measured on the same
harness, the same data, and the same failure cases.

| | **A — derived** | **B — ULID + UNIQUE** |
|---|---|---|
| id | `"snap_" + sha256(parent \| stage \| content_fp)[:32]` | Crockford ULID (26 chars) |
| dedupe key | `PRIMARY KEY (snapshot_id)` | `UNIQUE (parent_snapshot_id, content_fingerprint)` |
| first row parent | `'genesis'` sentinel | `'genesis'` sentinel |
| rebuild from raw | reproduces ids | mints new ids |
| id sortable | no | coarsely (ms), not within a ms |

A third variant, `B-null`, is included only to demonstrate the NULL trap: the same
ULID + `UNIQUE(parent, content)` but with a NULL parent for the first observation.

## Fixed contract

Every implementation is a module exposing:

```python
NAME: str
def create_schema(con) -> None
def new_id(parent: str, stage: str, content_fp: str) -> str
def insert_snapshot(con, sid, parent, stage, fp, observed_at, accepted_at) -> str
```

`insert_snapshot` must be safe to call twice with the same `(parent, content_fp)` and
must return the id that is actually present afterwards.

The pipeline loop, schema except for the approach-specific constraint, fixture loading,
canonicalisation and all tests live in `common.py` / `suite.py` and are **not** editable
per approach. That is what makes the numbers comparable.

## Data

The nine real captures at tag `recon-evidence` (`f5c1e35`), copied to `fixtures/caps/`.
They are parsed into the 60-measure fact (see `common.columns()`). Successive
observations are synthesised by monotonic mutation of `apps`, `goal`, `yellowCard`,
`redCard` and the rate columns, seeded deterministically.

## Tests

| id | case | expected |
|---|---|---|
| T01 | first observation | 1 snapshot |
| T02 | identical publish again | 1 snapshot, 0 new writes |
| T03 | revert A→B→A | 3 snapshots |
| T04 | rollback / process kill inside the transaction | 0 partial rows |
| T05 | stale checkpoint, same `(parent, content)` | still 1 snapshot |
| T06 | rebuild from raw in accepted order | A: identical ids; B: different |
| T07 | same content, different parent | 2 snapshots |
| T08 | NULL parent, first observation twice | B-null: 2 snapshots (trap) |
| T09 | two writers | second is refused by the engine |
| T10 | 1 000 observations | 1 000 distinct ids, no collisions |
| T11 | determinism across processes | A: identical; B: different |
| T12 | latest-state query after N | 20 rows, values match |
| T13 | delta query across history | correct diffs, first row absent |
| T14 | orphan fact row | rejected by FK |
| T15 | id properties | length, sortability, entropy |

## Metrics

```
duplicate_snapshots, writes_on_no_change, rows_after_revert, partial_rows_after_kill,
pinned_report_rows_after_rebuild, id_rebuild_match, id_collisions,
concurrent_writer_refused, fk_enforced, latest_rows, delta_rows,
insert_ms_total, insert_ms_p50, insert_ms_p95, noop_ms_p50,
rebuild_ms_total, latest_query_ms_p50, delta_query_ms_p50, db_bytes, id_length
```

## Results

`suite.py --approach a|b|bnull` writes `results/<approach>.json`. `suite.py --compare`
writes `results/summary.json` + `results/summary.md`.
