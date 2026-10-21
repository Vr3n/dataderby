# 0005 - DuckDB as the store

**Status:** accepted, 2026-10-21
**Measured on:** DuckDB 1.5.6, Python 3.12.13
**Evidence:** `experiments/id-scheme/results/perf.json`,
`experiments/id-scheme/probes/duckdb_tx_abort.py`

## Context

The v1 workload is one local writer, small snapshots (20 teams x 60 measures),
and analytical reads. DuckDB gives a single-file analytical store with SQL
constraints and a transaction, without a server. The risky parts are its
transaction and insert behaviour, so they were measured rather than assumed.

## Decision

- Use one DuckDB file, one writer, and a process lock in addition to DuckDB's
  own file lock.
- Enforce the fact-to-header relationship with a foreign key on insert.
- Do not rely on cascade deletes. No delete path is part of v1.
- Use `ON CONFLICT (parent_snapshot_id, content_fingerprint) DO NOTHING
  RETURNING snapshot_id` to decide whether the snapshot is new.
- On a constraint error, issue an explicit `ROLLBACK`. A bare `COMMIT` after an
  abort does not raise and silently commits nothing.
- Write multi-row facts with escaped SQL literals, not parameters. On 1.5.6,
  the measured bulk insert was about 90x slower with parameter binding than
  with escaped literals; `COPY` is the third option but is not the v1 path.
- Pin the DuckDB version in `uv.lock`; re-run the contract probes before a
  version change.

## Consequences

- Readers can open the database read-only while no writer is active.
- A second writer fails fast with exit 5 instead of interleaving.
- The literal builder is security-sensitive; it must reject `NaN`/`inf` and
  escape `'` as `''`, with a property test.
- A DuckDB upgrade is a schema/transaction compatibility review, not a routine
  bump.

## Rejected alternatives

- **SQLite.** Weaker analytical SQL and no direct fit for the columnar reads.
- **Postgres.** Operationally heavier than the v1 workload justifies.
- **Parameter binding for the bulk fact insert.** Correct but about 90x slower
  on the measured shape; use literals inside the transaction.
- **Cascade deletes.** The v1 model is append-only; a cascade would hide a
  history decision.
