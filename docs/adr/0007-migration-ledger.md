# 0007 - Migration ledger

**Status:** accepted, 2026-10-26
**Decision owner:** project owner
**Supersedes:** the "add a history table before the second one" note in `docs/reports/p3-schema.md`

## Context

`db.migrate()` used to execute every `sql/*.sql` file in lexical order and rely on
`CREATE ... IF NOT EXISTS` to make a second run harmless. Three files in, that is
true. It stops being true at the first `ALTER TABLE`, backfill, `DROP`, or
constraint change: those either fail on the second run or apply twice, and there is
no record of what already ran.

The cost is asymmetric. The ledger costs roughly eighty lines and one table today.
Without it, the first schema change after launch is an incident with no audit trail.

## Decision

A `schema_migration` table records each applied file exactly once:

```sql
CREATE TABLE IF NOT EXISTS schema_migration (
    version     VARCHAR PRIMARY KEY,
    checksum    VARCHAR NOT NULL,
    applied_at  TIMESTAMP NOT NULL
);
```

`migrate()`:

1. creates the ledger if it is absent;
2. hashes each `*.sql` file with SHA-256;
3. skips a version whose recorded checksum matches;
4. refuses a version whose checksum changed;
5. refuses an applied version with no file on disk;
6. runs each new file and inserts its ledger row in one transaction.

The version is the file name, not a number parsed from it. File names already sort
correctly, and a name is what an operator sees in an error message.

## Why not Alembic, Flyway, or a generic migration library

- The project has three migrations and one database engine. The dependency would be
  larger than the problem, and `AGENTS.md` requires asking before adding one.
- DuckDB's transactional DDL is enough to make "run the file and record it" atomic.
- The ledger is deliberately boring: a future tool can read it, and the existing
  tests keep working.

Revisit if migrations start needing Python callbacks, downgrade paths, or branching.
At that point the ledger is still the right substrate.

## Adopting an existing database

A database created before this decision has the tables but no ledger. `migrate()`
re-runs the three idempotent files and records them. That is intentional: the files
are safe to re-run, and refusing to start would strand the only existing database.
The test `test_a_database_without_a_ledger_is_adopted_and_recorded` pins the
behaviour.

## Consequences

- Applied files are immutable. Editing one is an error, not a convenience.
- Deleting an applied file is an error. History is append-only in both directions.
- One file is one change. A multi-statement file is allowed, but a failure rolls
  back the whole file.
- The ledger lives in the same DuckDB file, so it is backed up with the schema it
  describes. `docs/adr/0004-raw-is-system-of-record.md` still governs recovery:
  a lost database is rebuilt from raw, not restored from a ledger.

## Rejected alternatives

- **Rely on idempotent SQL forever.** One `ALTER TABLE` breaks it, and the failure
  appears at the worst time.
- **Record a hash of the whole directory.** A single aggregate cannot tell which
  file changed.
- **Store the checksum inside each SQL file.** Then editing the file to update the
  checksum defeats the check.
