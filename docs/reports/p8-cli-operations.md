# P8 - CLI, migration ledger, and CI

**Status:** complete
**Date:** 2026-10-26
**Plan:** `plans/v1-build-plan.md` §11
**Issues:** #1 (ledger), #2 (CI), #3 (CLI)
**Previous:** `docs/reports/p7-views.md`

## Goal

An operator can run, inspect, and recover the pipeline without opening Python, and
the repository can prove it on a clean checkout instead of on one developer's
machine.

That is three pieces of work, not one:

1. a migration ledger, so the schema can change safely (issue #1);
2. a CI workflow, so the four gates are enforced rather than remembered (issue #2);
3. the CLI, so the pipeline has an entry point (issue #3).

They land together because each one is a prerequisite for trusting the others: the
CLI calls `migrate()`, CI runs the CLI tests, and the ledger is what makes a future
`004_*.sql` routine.

## What was built

| File | Change |
|---|---|
| `src/dataderby/db.py` | `schema_migration` table, `MigrationError`, checksummed `migrate()` |
| `src/dataderby/cli.py` | New. Six commands, exit codes, lock, run/replay/verify orchestration |
| `src/dataderby/__main__.py` | New. `python -m dataderby` |
| `pyproject.toml` | `[project.scripts] dataderby = "dataderby.cli:main"` |
| `.github/workflows/ci.yml` | New. Four gates on Ubuntu and Windows |
| `tests/test_migrations.py` | New. Seven ledger tests |
| `tests/test_pipeline_cli.py` | New. Seventeen CLI tests |
| `tests/test_schema.py` | One expected-table list extended with `schema_migration` |
| `docs/adr/0007-migration-ledger.md` | New. Why the ledger exists and what it refuses |
| `docs/reports/p8-cli-operations.md` | This report |

No runtime dependency was added. `argparse`, `hashlib`, `json`, `tempfile`, and
`duckdb` were already available.

## 1. The migration ledger

Before:

```python
for sql_path in sorted(sql_dir.glob("*.sql")):
    con.execute(sql_path.read_text(encoding="utf-8"))
```

After:

```python
con.execute(_LEDGER_DDL)
applied = _applied(con)
for sql_path in sorted(sql_dir.glob("*.sql")):
    checksum = _checksum(sql_path)
    if version in applied:
        if applied[version] != checksum:
            raise MigrationError(f"{version} changed after it was applied")
        continue
    with transaction(con):
        con.execute(sql_path.read_text(encoding="utf-8"))
        con.execute("INSERT INTO schema_migration ...")
```

The version is the file name. The checksum is SHA-256 of the file's bytes. The
insert and the migration share one transaction, so a half-applied file cannot leave
a ledger row behind.

Three failure modes are now named instead of silent:

| Situation | Behaviour |
|---|---|
| Second `migrate()` call | applies nothing, keeps the original `applied_at` |
| Applied file edited | `MigrationError` naming the version and both checksums |
| Applied file deleted | `MigrationError` listing the missing versions |
| New file fails halfway | rollback; no ledger row; earlier files stay applied |
| Database predates the ledger | the three idempotent files re-run and are recorded |

The adoption case matters: the repository had no database when this landed, but a
contributor may already have one from P7. Refusing to start would strand it.

## 2. CI

`.github/workflows/ci.yml`:

- triggers on `push` to `master` and on every `pull_request`;
- runs a matrix of `ubuntu-latest` and `windows-latest`;
- installs with `uv sync --frozen`, so `uv.lock` is authoritative;
- runs the four gates as four named steps:
  `ruff format --check`, `ruff check`, `mypy main.py`, `pytest -q`;
- cancels superseded runs on the same ref;
- has `permissions: contents: read` and a 20-minute timeout.

The Windows leg is not decoration. `lock.py` has a real `msvcrt` branch and a real
`flock` branch; a Linux-only pipeline would never execute the branch this machine
uses. The same applies to path handling in `raw.py` and to `tempfile` in `replay`.

## 3. The CLI

```
dataderby run       [--stage KEY] [--allow-apps-decrease] [--dry-run]
dataderby probe     [--stage KEY]
dataderby replay    --run-id ID | --raw-dir PATH [--check]
dataderby verify    [--snapshot ID] [--address STAGE OBSERVED_AT]
dataderby freshness [--json]
dataderby stages    list
```

Every command accepts `--config PATH`, defaulting to `config/stages.toml`.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | ok, or `no_change` |
| 2 | a feed could not be fetched |
| 3 | publish or parse was blocked (including HTTP 403) |
| 4 | configuration or usage |
| 5 | another process holds the pipeline lock |
| 6 | internal failure, or a verification mismatch |

`argparse` normally exits `2` on a usage error, which collides with `fetch_failed`.
The parser subclass raises `ConfigError` instead, so usage errors return `4`. This
is tested.

### `run`

The only writer. It acquires the lock **before** reading config, then:

1. `connect()` → `migrate()` → `reconcile()`;
2. capture the page;
3. land nine feeds and the raw bundle;
4. parse into a candidate and a standings companion;
5. require the team sets to agree;
6. validate A1–A21 and publish in one transaction;
7. print the outcome and release the lock in `finally`.

`--stage` selects one stage; without it, every configured stage runs in sorted key
order. The first failure stops the run, so the operator sees one cause rather than
twelve cascading ones.

`--dry-run` captures and parses, then runs the assertions against an **in-memory**
DuckDB. It writes no raw bundle, no run row, and no snapshot. It prints the
fingerprint it would publish. This is the honest version of "would this pass?" —
it does not touch the real database.

### `replay`

Two sources: `--run-id` resolves the bundle from `raw_capture.path`, and
`--raw-dir` takes one directly. The bundle's address
(`tournament/season/stage/stamp`) is matched back to a configured stage, so a
mislabelled directory is a config error rather than a wrong publish.

Replay rebuilds `PageCapture` and the nine `Capture` objects from bytes, then:

- with `--check`: computes the fingerprint and compares it with the published
  snapshot at that exact `observed_at`; mismatch returns `6`;
- without `--check`: publishes into a temporary DuckDB file, reads the stored
  fingerprint back, and compares.

Ids are never compared; only content. That is the same rule the P6 tests use.

### `verify`

Five integrity checks plus one contract check:

1. headers with no team facts;
2. team facts with no header;
3. standings facts with no header;
4. duplicate `(parent_snapshot_id, content_fingerprint)` edges;
5. duplicate stage addresses;
6. snapshots whose team count disagrees with `expected_teams`.

`--snapshot` and `--address` scope the per-snapshot checks. The orphan checks are
global on purpose: an orphan is a global integrity failure, not a local one. Any
failure returns `6`.

### `freshness`

Reads `v_pipeline_freshness` with `read_only=True`. `--json` emits a stable list of
objects; the human table prints `-` for a stage that has never succeeded.

### `probe`

Captures the page, fetches only `summary/overall`, and prints the team count, byte
count, and SHA-256. No database, no raw write. This is the cheap smoke test for the
page selectors and the feed token, and it is the shape E1 needs.

### `stages list`

Prints the registry without opening a database. This is the command a new
contributor runs first.

## Design notes

**The lock is acquired before config.** If config is broken while another run holds
the lock, the answer should be "locked", not "your config is wrong". Precedence is
a feature.

**`main.py` is untouched.** It still delegates to `dataderby.fixtures.cli`. The
fixture pipeline is a separate, working product with its own tests
(`tests/test_cli.py`). The new CLI is exposed as a console script and as
`python -m dataderby`, so neither entry point is ambiguous:

```
uv run dataderby stages list
uv run python -m dataderby stages list
uv run python main.py competitions        # fixture pipeline, unchanged
```

**No double fetch.** `run` calls `land_stage` once and reuses `run.feeds`; it does
not fetch, then fetch again for parsing. `--dry-run` fetches once and never lands.

**`replay` does not need the ledger.** `competition_snapshot.run_id` has no foreign
key, so a replay can publish into a scratch database without inventing an
`ingestion_run` row.

## Test strategy

The tests are written at the level where the behaviour lives.

| File | Proves | Level |
|---|---|---|
| `tests/test_migrations.py` | ordering, idempotence, checksum tamper, missing file, rollback, adoption | integration, real DuckDB |
| `tests/test_pipeline_cli.py` | exit codes, lock precedence, dry-run writes nothing, end-to-end publish, no-change, replay match and mismatch, verify failure | integration, real DuckDB + canned payloads |
| `tests/test_schema.py` | the table list still matches the contract | schema |

What the migration tests deliberately do **not** do: assert the SQL text of
`migrate()`, or mock the filesystem. They create real files in `tmp_path`, run real
SQL against a real DuckDB file, and assert on observable state (tables, ledger rows).
A test that mocks the database would pass with the ledger deleted.

What the CLI tests deliberately do **not** do: assert the full help text or every
column width. They assert the contract an operator or a script depends on — exit
codes, whether a file exists, whether a snapshot was written, what `--json` parses
to.

The end-to-end CLI test is a real pipeline run with canned bytes: a 20-team
candidate enters through `run`, is validated by the actual assertions, and is
published by the actual transaction. Only two effects are injected: the page
capture and the feed client. Everything between them is production code.

Two specific traps are pinned:

- `test_a_held_lock_refuses_the_run_before_any_write` asserts the database file does
  not exist afterwards, so "returned 5" cannot hide a partial write.
- `test_a_dry_run_writes_nothing` asserts both the database and `data/raw` are
  absent, not just that the exit code is 0.

Replay is tested three ways: a matching fingerprint (`MATCH`), a tampered payload
(`MISMATCH`, exit 6), and a scratch rebuild (`REPLAYED`). The tamper changes one
non-shared measure, so the mismatch is a content difference, not a parse error.

Fixtures are reused from the existing suite (`_captures`, `_page`, `_SPEC`) rather
than duplicated. That is intentional: the CLI is tested against the same golden
payloads as the parser and publisher, so a fixture change cannot silently disagree
with the parser.

## Evidence

```
$ uv run ruff format --check
82 files already formatted

$ uv run ruff check
All checks passed!

$ uv run mypy main.py
Success: no issues found in 1 source file

$ uv run pytest -q
189 passed
```

CI on `901eb7b`: `gates (ubuntu-latest)` and `gates (windows-latest)` both pass.
The first attempt failed at action resolution (`astral-sh/setup-uv@v10` does not
exist as a moving tag); the pin to `v10.3.2` is the only change between the two
runs.

Live smoke checks:

```
$ uv run dataderby stages list --config config/stages.toml
KEY                      COMPETITION            SEASON     STAGE        TEAMS STAGE_ID
bundesliga-2026-2027     Bundesliga             2026-2027  league          18    25666
...

$ uv run dataderby verify --config config/stages.toml
error: database does not exist: data\dataderby.duckdb
$ echo $LASTEXITCODE
4
```

The second is the correct answer: there is no pipeline database yet. It is a config
error, not a crash.

## Deviations and open items

- **Issue #4 (timestamp type) is not in this change.** It touches the schema and
  the assertion staging columns; it deserves its own commit and test sweep. It is
  still open and still cheaper before the first real capture.
- **No real capture was parsed.** Every payload in these tests is synthetic. Issue
  #5 remains the gate on that claim.
- **No 429/`Retry-After` handling.** The fetch policy is unchanged; issue #6 owns it.
- **`migrate()` still executes a whole file in one `execute()`.** A future migration
  that cannot share a transaction needs a different runner. Recorded in
  `docs/reports/p3-schema.md` and still true.
- **CI is pinned to `setup-uv@v10.3.2`.** The repository publishes release tags but
  no moving `v10` tag; the first run failed at action resolution. Pinning the exact
  tag is also the safer default. If the action's inputs change, the workflow is the
  thing to fix, not the code.
- **`tests/test_schema.py` changed by one line.** Adding a real table to the schema
  makes the closed table list wrong; the list now includes `schema_migration`. No
  assertion was removed.

## Operator quickstart

```bash
uv sync
uv run dataderby stages list

# smoke the source without writing anything
uv run dataderby probe --stage epl-2026-2027

# see what would happen, against an in-memory database
uv run dataderby run --stage epl-2026-2027 --dry-run

# the real thing
uv run dataderby run --stage epl-2026-2027
uv run dataderby freshness
uv run dataderby verify
```

If `run` returns `5`, another process holds `data/pipeline.lock`. If it returns `3`,
read the assertion id in the error and look it up in `sql/002_assertions.sql`. If it
returns `4`, check `--config` and the stage key.
