# 0010 - Append-only assertion contract

**Status:** accepted, 2026-10-27
**Related:** `docs/adr/0007-migration-ledger.md`, `docs/reports/all-league-capture.md`,
`docs/reports/points-adjustments.md`

## Context

The publish contract is loaded from comment-delimited SQL in
`sql/002_assertions.sql` (`docs/adr/0007-migration-ledger.md`). That file is also
a migration: `migrate()` records a SHA-256 of its bytes, executes it, and refuses
to run when the bytes change.

Adding the A22 deduction warning during the points-adjustment work exposed the
consequence:

```text
migration error: 002_assertions.sql changed after it was applied
(recorded 0d21c51f4943, now cebfbad5fa70)
```

The live database was correct; the working tree was not. Two separate effects
had changed the bytes:

1. the assertion SQL itself was edited;
2. a checkout on Windows rewrote the file with CRLF, while the ledger had
   recorded the LF form.

A ledger that hashes bytes is only useful if the bytes are reproducible. The
contract therefore needs a growth rule and a line-ending rule.

## Decision

### 1. The contract is append-only

A new assertion is a new comment-only migration file named
`NNN_assertions_<slug>.sql`. An applied file is never edited. A22 therefore lives
in `sql/005_assertions_a22.sql`; the history in `002_assertions.sql` stays
byte-identical.

The files are comment-only so `migrate()` can execute them without side effects,
exactly as `002` already is.

### 2. The loader reads the whole contract set

`load_assertions()` reads every `sql/*assertions*.sql` in lexical order by
default. A caller may still pass one file, or a directory, for a focused test.

Two malformed contracts fail closed:

- a marker with no SQL raises `ValueError`;
- an assertion id that appears in two files raises `ValueError`.

Assertion order is file order, then line order. A22 is last because `005` sorts
after `002`.

### 3. SQL files are LF on every host

`.gitattributes` declares:

```text
*.sql text eol=lf
```

The ledger hashes bytes, so the working tree must not depend on
`core.autocrlf`. LF is the form the live ledger already recorded for
`001`–`003`, and it is the form every new migration uses.

### 4. A migration is the deployment unit

An assertion addition is applied by the same `migrate()` call as a table or a
view. There is no second deployment path for the contract. The
`schema_migration` table is the record of what the database is running.

## Consequences

- Adding an assertion costs one migration file and one loader test, not an edit
  to a frozen file.
- The live ledger stays valid: `002` remains at `0d21c51f4943`; `004` and `005`
  are appended.
- A Windows checkout cannot change a migration checksum.
- The contract is spread across files. `ls sql/*assertions*.sql` is the index;
  duplicate ids are rejected rather than silently shadowed.
- A future assertion that must replace an old one needs an explicit disable
  mechanism, not an edit. That mechanism does not exist yet and is not needed for
  an additive WARN.

## Rejected alternatives

- **Edit `002` and update the ledger row.** It rewrites the record of what was
  applied and makes the ledger decorative.
- **Exempt `*assertions*.sql` from the checksum.** The contract would then be the
  one migration that can change under a running database. That is the failure
  the ledger exists to prevent.
- **Move assertions out of `sql/` into `src/`.** It would orphan the applied
  `002` row and create a second deployment path for one contract. A larger
  change for no benefit at this size.
- **Hash the normalised text instead of the bytes.** The ledger would no longer
  describe the file that was executed. Forcing LF at checkout is simpler and
  keeps the hash honest.
- **Load every `*.sql` file and ignore files without markers.** It works today,
  but a stray marker in a schema file would silently become a publish rule. The
  explicit `*assertions*.sql` glob keeps the contract boundary visible.

## Review

Before adding an assertion:

1. create a new `NNN_assertions_<slug>.sql`;
2. do not edit an applied file;
3. confirm the file is LF (`git diff --check`, then `git ls-files --eol`);
4. run `uv run pytest` and a live `dataderby run` so `migrate()` records the new
   version.

If an assertion must be removed or replaced, design that mechanism explicitly.
Do not delete the file or rewrite the ledger.
