# v1 build plan — step by step

**Status:** execution plan · 20 Oct 2026
**Design source of truth:** `plans/v1-implementation-plan.md`
**Research input:** `docs/research/production-patterns-research.md`
**Decision record:** `experiments/id-scheme/results/summary.md`, `docs/reference/snapshot-identity-review.html`, `docs/research/whoscored-decisions.md`

This document is the *order of work*. The v1 plan says what the system is; this says what
I create, in which sequence, and how each step is proven before the next one starts.

---

## 0. How to read this

Each phase has four parts:

1. **Goal** — one sentence.
2. **Tasks** — the concrete files and functions.
3. **Proof** — the tests that must pass before the phase closes.
4. **Exit** — the observable condition a reviewer can check without reading the code.

A phase is not done because the code runs. It is done when the proof passes on a clean
checkout.

Phases are sequential. P6 depends on P3 and P5; nothing else has a hard dependency, but I
will not reorder anyway — each phase de-risks the next.

---

## 1. Ground rules

These hold for every phase.

| Rule | Consequence |
|---|---|
| `uv` only, no `pip`, no `requirements.txt` | `uv add`, `uv run` |
| Quality gates before any phase closes | `ruff format`, `ruff check`, `mypy main.py`, `pytest` |
| No new dependency without a recorded reason | the six in §2 are the whole list |
| Raw is immutable | nothing under `data/raw/` is ever rewritten |
| `data/` is git-ignored before the first run | raw payloads are not redistributable |
| No `print` for operations | structured JSON via `observe.py` |
| Public functions typed, docstrings Google-style | `mypy` is configured strict |
| One writer | process lock plus DuckDB's own file lock |

**Proposed** (v1 §20, item 1; owner approval pending): `duckdb`, `pydantic`, `pytest`,
`ruff`, `mypy`, plus `hypothesis` as a **dev-only** sixth. The extra one needs its own
justification:
canonicalisation is the one function where "row order must not matter" is a property, not
an example, and property-based testing is the cheapest way to prove it. If it is declined,
P5 falls back to 20 table-driven cases — workable, but weaker. Nothing else in the plan
adds a dependency.

---

## 2. What exists, what we create

```
main.py                         NEW   entrypoint for the mypy gate
pyproject.toml                  EDIT  deps + tool config
config/stages.toml              NEW   stage registry
sql/
  001_schema.sql                NEW   six tables
  002_assertions.sql            NEW   A1–A21
  003_views.sql                 NEW   latest / delta / freshness
src/dataderby/
  __init__.py                   NEW
  cli.py                        NEW   run | probe | replay | verify | freshness | stages
  config.py                     NEW   StageSpec, Settings (pydantic)
  contract.py                   NEW   sections, views, 60 columns, ownership
  db.py                         NEW   connect, migrate, transaction protocol
  page.py                       NEW   stage page load, token, stage labels
  standings.py                  NEW   three splits from tr[data-team-id]
  fetch.py                      NEW   session, retries, gate detection
  raw.py                        NEW   atomic write + sidecar + path builder
  parse.py                      NEW   bytes -> CandidateRows (pure)
  parse_standings.py            NEW   three views -> standings rows
  canonical.py                  NEW   candidate + standings -> fingerprint (pure)
  publish.py                    NEW   transaction: assert -> header -> facts -> checkpoint
  validate.py                   NEW   A1–A21 execution + action dispatch
  lock.py                       NEW   cross-platform exclusive lock
  observe.py                    NEW   structured JSON logging
  ulid.py                       NEW   26-char Crockford ULID
tests/
  conftest.py                   NEW   temp DB, fixture paths
  golden/                       COPIED from experiments/id-scheme/fixtures/caps
  fixtures/                     NEW   trap/clean cohorts
  test_config.py                NEW
  test_contract.py              NEW
  test_schema.py                NEW
  test_parse.py                 NEW
  test_standings.py             NEW
  test_canonical.py             NEW
  test_fetch.py                 NEW
  test_publish.py               NEW
  test_views.py                 NEW
  test_cli.py                   NEW
docs/research/whoscored-decisions.md     NEW   licence + scope decisions (2026-10-20)
data/                           IGNORED  raw/ dataderby.duckdb logs/ state/
```

`main.py` is six lines. It exists because `AGENTS.md` names it literally in the gate, and
amending the gate for convenience is how gates die.

---

## 3. P0 — Skeleton and gates (½ day)

**Goal:** a repository where every quality gate runs and passes before there is any logic.

### Tasks

1. Add tool config to `pyproject.toml`:
   - `[tool.ruff] line-length = 100`, `target-version = "py312"`
   - `[tool.mypy] strict = true`, `mypy_path = "src"`,
     `explicit_package_bases = true`, `files = ["main.py", "src", "tests"]`
   - `[tool.pytest.ini_options] testpaths = ["tests"]`,
     `markers = ["live: hits the network"]`
2. Make the project an installable package: remove `[tool.uv] package = false` (or set it
   to `true`). The `src/` layout only catches import mistakes if the package is installed;
   leaving it as a flat script would make `from dataderby...` work by accident.
3. `uv add duckdb pydantic`; `uv add --dev pytest ruff mypy hypothesis`.
4. Create `main.py`:
   ```python
   from dataderby.cli import main

   if __name__ == "__main__":
       raise SystemExit(main())
   ```
5. Create `src/dataderby/__init__.py` with `__version__`.
6. Extend `.gitignore`: `data/`, `*.duckdb`, `*.duckdb.wal`, `.pytest_cache/`, `.mypy_cache/`.
7. `uv sync`.

### Proof

- `uv run ruff format` → no changes.
- `uv run ruff check` → clean.
- `uv run mypy main.py` → success.
- `uv run pytest` → no tests collected, exit 5 is acceptable *only* here; add one trivial
  test so it exits 0.

### Exit

A fresh clone runs the four gates green with no `data/` directory present.

**Risk:** `mypy main.py` does not follow imports by default in a `src/` layout. Mitigation:
`mypy_path = "src"` and `explicit_package_bases = true` in `[tool.mypy]`, verified by
intentionally breaking a type in `cli.py` and seeing the gate fail.

---

## 4. P1 — Decisions and configuration (½ day)

**Goal:** the six ADRs exist and the stage registry loads with validation.

### Tasks

1. `docs/adr/0001-history-model.md` — immutable snapshot fact; ULID + unique edge; report
   address is the stage triple + `observed_at`.
2. `0002-precision.md` — store full precision; round at presentation; `goal` is `DOUBLE`
   because the source sends `31.0`.
3. `0003-two-clocks.md` — `observed_at` vs `accepted_at`; ordering uses `observed_at`.
4. `0004-raw-is-system-of-record.md` — backup policy is raw, not the `.duckdb`.
5. `0005-duckdb-as-store.md` — single writer, FK on insert, measured binding cost, and
   the transaction gotchas recorded in `docs/research/production-patterns-research.md` §2.
   Record the exact DuckDB version; the `RETURNING`/abort behaviour was measured on 1.5.6.
6. `0006-source-use.md` — **decided 2026-10-20**: `isOpta` accepted by the owner;
   link to `docs/research/whoscored-decisions.md` and keep the local/private/non-redistributed
   posture.
7. `config/stages.toml` with the LaLiga 2026-27 stage.
8. `config.py`:
   - `StageSpec` (frozen pydantic model): ids, `season_key`, `competition`,
     `expected_teams`, `whoscored_page_url`, `has_league_table`.
   - `Settings`: `db_path`, `raw_dir`, `log_dir`, `stages`.
   - `load_settings(path) -> Settings`, `load_stages(path) -> dict[str, StageSpec]`.
   - Validation: ids positive, `expected_teams == 20` is *data*, not a constant — but the
     config must state it.

### Proof

- `test_config.py`: valid file loads; missing key raises with the field name; duplicate
  stage id raises; unknown key in TOML raises (`extra="forbid"`).
- One test asserts the config file in the repo parses.

### Exit

`uv run python -c "from dataderby.config import load_settings; print(load_settings())"`
prints the stage and nothing else.

---

## 5. P2 — The contract (½ day)

**Goal:** one module owns the 60 columns, the standings columns and the source's
expected shape.

### Tasks

1. `contract.py`:
   - `SECTIONS = ("summary", "defensive", "offensive")`
   - `VIEWS = ("overall", "home", "away")`
   - `EXPECTED_STAT_COLUMNS: dict[tuple[str, str], tuple[str, ...]]` — derived from the
     nine captures, not from the document.
   - `MEASURE_COLUMNS: tuple[str, ...]` — the 60 warehouse names.
   - `STANDINGS_MEASURES: tuple[str, ...]` — `rank, played, won, drawn, lost, goals_for,
     goals_against, goal_difference, points, form`, each suffixed by view.
   - `OWNERSHIP: dict[str, str]` — which section supplies `apps`, `shots_per_game`,
     `rating`.
   - `WHOSCORED_TO_WAREHOUSE: dict[str, str]` — camelCase → snake_case.
2. The 60 columns, by block:

   | Block | Pattern | Count |
   |---|---|---|
   | Apps | `apps_{view}` | 3 |
   | Rating | `rating_{view}` | 3 |
   | Shots per game | `shots_per_game_{view}` | 3 |
   | Summary-owned | `summary_{view}_{goal, yellow_card, red_card, possession, pass_success, aerial_won_per_game}` | 18 |
   | Defensive-owned | `defensive_{view}_{goals_conceded, tackles, interceptions, fouls, offsides}` | 15 |
   | Offensive-owned | `offensive_{view}_{shots_on_target_per_game, dribble_won_per_game, foul_given_per_game}` | 9 |
   | Ranking | `ranking_{section}_{view}` | 9 |
   | | **Total** | **60** |

3. `test_contract.py`:
   - `len(MEASURE_COLUMNS) == 60` and `len(set(...)) == 60`.
   - Every `EXPECTED_STAT_COLUMNS` entry matches the corresponding golden capture's actual
     `statColumns`, in order.
   - Every measure column maps to exactly one owner section or to the shared block.
   - `OWNERSHIP` covers `apps`, `shots_per_game`, `rating` and nothing else.
   - `len(STANDINGS_MEASURES) == 30` (10 fields × 3 splits).

### Exit

The document's arithmetic (`57 − 9 − 6 + 3 + 3 + 3 + 9 = 60`) is reproduced by a test that
counts, rather than by a test that trusts the number.

---

## 6. P3 — Schema (1 day)

**Goal:** six tables that enforce the invariants without any application code.

### Tasks

1. `sql/001_schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS ingestion_run (
    run_id               VARCHAR PRIMARY KEY,
    mode                 VARCHAR NOT NULL,
    started_at           TIMESTAMP NOT NULL,
    finished_at          TIMESTAMP,
    outcome              VARCHAR NOT NULL DEFAULT 'running',
    tournament_id        INTEGER NOT NULL,
    whoscored_season_id     INTEGER NOT NULL,
    whoscored_stage_id      INTEGER NOT NULL,
    observed_at          TIMESTAMP,
    accepted_snapshot_id VARCHAR,
    http_requests        INTEGER NOT NULL DEFAULT 0,
    error_code           VARCHAR,
    error_detail         VARCHAR,
    CHECK (outcome IN ('running','accepted','no_change','fetch_failed',
                       'blocked','abandoned','crashed'))
);

CREATE TABLE IF NOT EXISTS raw_capture (
    run_id        VARCHAR NOT NULL,
    section       VARCHAR NOT NULL,
    view          VARCHAR NOT NULL,
    attempt       INTEGER NOT NULL,
    captured_at   TIMESTAMP NOT NULL,
    path          VARCHAR NOT NULL,
    bytes         INTEGER NOT NULL,
    sha256        VARCHAR NOT NULL,
    content_type  VARCHAR,
    is_gate       BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (run_id, section, view)
);

CREATE TABLE IF NOT EXISTS competition_snapshot (
    snapshot_id          VARCHAR PRIMARY KEY,
    parent_snapshot_id   VARCHAR NOT NULL DEFAULT 'genesis',
    tournament_id        INTEGER NOT NULL,
    whoscored_season_id     INTEGER NOT NULL,
    whoscored_stage_id      INTEGER NOT NULL,
    season_key           VARCHAR NOT NULL,
    content_fingerprint  VARCHAR NOT NULL,
    canonical_version    INTEGER NOT NULL,
    observed_at          TIMESTAMP NOT NULL,
    accepted_at          TIMESTAMP NOT NULL,
    capture_span_seconds DOUBLE NOT NULL,
    is_opta              BOOLEAN NOT NULL,
    whoscored_page_url      VARCHAR NOT NULL,
    run_id               VARCHAR NOT NULL,
    UNIQUE (parent_snapshot_id, content_fingerprint),
    UNIQUE (tournament_id, whoscored_season_id, whoscored_stage_id, observed_at)
);

CREATE TABLE IF NOT EXISTS fact_team_snapshot (
    snapshot_id  VARCHAR NOT NULL,
    team_id      INTEGER NOT NULL,
    team_name    VARCHAR NOT NULL,
    -- 60 measure columns, each: DOUBLE or INTEGER, nullable,
    -- CHECK (col >= 0) where a negative is meaningless
    PRIMARY KEY (snapshot_id, team_id),
    FOREIGN KEY (snapshot_id) REFERENCES competition_snapshot(snapshot_id)
);

CREATE TABLE IF NOT EXISTS fact_standings_snapshot (
    snapshot_id       VARCHAR NOT NULL,
    team_id           INTEGER NOT NULL,
    team_name         VARCHAR NOT NULL,
    rank_overall      INTEGER,
    played_overall    INTEGER,
    won_overall       INTEGER,
    drawn_overall     INTEGER,
    lost_overall      INTEGER,
    goals_for_overall INTEGER,
    goals_against_overall INTEGER,
    goal_difference_overall INTEGER,
    points_overall    INTEGER,
    form_overall      VARCHAR,
    rank_home         INTEGER,
    played_home       INTEGER,
    won_home          INTEGER,
    drawn_home        INTEGER,
    lost_home         INTEGER,
    goals_for_home    INTEGER,
    goals_against_home INTEGER,
    goal_difference_home INTEGER,
    points_home       INTEGER,
    form_home         VARCHAR,
    rank_away         INTEGER,
    played_away       INTEGER,
    won_away          INTEGER,
    drawn_away        INTEGER,
    lost_away         INTEGER,
    goals_for_away    INTEGER,
    goals_against_away INTEGER,
    goal_difference_away INTEGER,
    points_away       INTEGER,
    form_away         VARCHAR,
    PRIMARY KEY (snapshot_id, team_id),
    FOREIGN KEY (snapshot_id) REFERENCES competition_snapshot(snapshot_id)
);

CREATE TABLE IF NOT EXISTS pipeline_checkpoint (
    tournament_id              INTEGER NOT NULL,
    whoscored_season_id           INTEGER NOT NULL,
    whoscored_stage_id            INTEGER NOT NULL,
    last_accepted_snapshot_id  VARCHAR,
    last_committed_fingerprint VARCHAR,
    last_probe_at              TIMESTAMP,
    last_success_at            TIMESTAMP,
    last_outcome               VARCHAR,
    attempt_count              INTEGER NOT NULL DEFAULT 0,
    abandoned_runs             INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tournament_id, whoscored_season_id, whoscored_stage_id)
);
```

Two details that are easy to get wrong:

- **`CHECK (col >= 0)` permits `NULL`.** In SQL, `NULL >= 0` evaluates to `NULL`, and a
  check passes on `NULL`. That is what we want: a missing measure is not a negative one.
- **`UNIQUE (parent, content)` is the dedupe.** The primary key is only a name. If someone
  later "optimises" the unique constraint away, every idempotency test must fail — that is
  the point.

2. `db.py`:
   - `connect(path, read_only=False)` with `PRAGMA threads=4`.
   - `migrate(con)` applies `sql/*.sql` in order, idempotently.
   - `transaction(con)` context manager: `BEGIN` / `COMMIT` / `ROLLBACK`, **no `COMMIT`
     in `finally`**.
3. `test_schema.py`:
   - applying `001_schema.sql` twice succeeds;
   - inserting a fact row with no header raises `ConstraintException`;
   - inserting a standings row with no header raises;
   - a stage with `has_league_table = false` may have zero standings rows;
   - inserting two headers with the same `(parent, content)` raises;
   - inserting two headers with the same `(stage, observed_at)` raises;
   - a `NULL` parent permits duplicate `(NULL, content)` — the trap, asserted as a
     *negative* test with a separate throwaway table;
   - `CHECK` rejects a negative count and accepts `NULL`.

### Exit

`pytest tests/test_schema.py` green. Every constraint has a test that proves it fires.

---

## 7. P4 — Fetch and raw landing (1 day)

**Goal:** the page, three standings views and nine feed payloads on disk, atomically,
with a ledger row and no partial state.

### Tasks

1. `observe.py`: `log(event, **fields)` writing one JSON object per line to
   `data/logs/<date>.jsonl`, plus stderr when `--verbose`.
2. `lock.py`: exclusive lock using `msvcrt.locking` on Windows, `fcntl.flock` elsewhere.
   The OS releases it when the process dies, so there are no stale locks. `LockHeld`
   exception → exit 5.
3. `page.py`:
   - `patchright` headed Chromium (Cloudflare rejects headless); abort `*fingerprint*`
     and `*podname.com*`;
   - load the stage `show` URL, wait for `table[id^="standings-"]`;
   - read `require.config.params.site.gSiteHeaderValue` (the `Model-last-Mode` token)
     and the `#stages` labels;
   - click `Overall`, `Home`, `Away` and return the three tables;
   - return `PageCapture(html, token, stages, standings, captured_at, url)`.
4. `standings.py`: parse the three views from `tr[data-team-id]`; rank from the first
   cell's `<span>`, name from `a.team-link`, ten values per row; form is the raw string.
5. `fetch.py`:
   - one `curl_cffi` session, browser impersonation;
   - nine URLs built from `StageSpec`, ordered Summary first;
   - the token from `page.py` is sent as `Model-last-Mode`;
   - 1.2 s minimum spacing, retries 2/4/8 s with jitter, 3 attempts;
   - gate detection by **structure**, not status: `200` with `text/html` or a body that
     is not the expected JSON envelope → `GatePage`;
   - `403` → `FetchBlocked`;
   - returns `Capture(section, view, body, captured_at, content_type, url)`.
6. `raw.py`:
   - path `data/raw/<tournament>/<season>/<stage>/<observed_at>/<section>__<view>.<ext>`;
   - `page__show.html` for the page, `standings__overall|home|away.json` for the tables,
     `summary|defensive|offensive__<view>.json` for the feeds;
   - `observed_at` is the run's start timestamp, fixed before the first request;
   - write with `open(..., "xb")` (exclusive create) to a temp name then `os.replace`;
   - sidecar `.meta.json` with url, status, content type, sha256, bytes, attempt;
   - never overwrite: a second run with the same `observed_at` gets a different directory
     because `observed_at` includes microseconds.
7. `test_fetch.py`: a local HTTP server replaying the nine goldens, plus broken variants
   (gate page, 403, truncated body, BOM, empty body). No live calls.
8. `test_standings.py`: parse the saved EPL page (`standings-25544.json`) and assert the
   shape, the `data-team-id` join and the form rule; a `has_league_table = false` fixture
   yields zero rows. No live calls.

### Exit

A sweep against the replay server writes the page, three standings views and nine feed
files whose SHA-256 match the goldens; a second sweep writes the same set again and zero
duplicate ledger rows.

---

## 8. P5 — Parse and canonicalise (1 day)

**Goal:** nine payloads and three standings views become 20 × 60 rows, one standings
fact and one stable fingerprint.

### Tasks

1. `parse.py`:
   - pure functions: `parse_capture(section, view, body) -> list[SourceRow]`;
   - `build_candidate(captures: list[Capture], spec: StageSpec) -> Candidate`;
   - missing measure → `None`, never `0`;
   - unknown `statColumns` → `SchemaDrift` (the caller maps it to A15);
   - `team_id` set must be identical across all nine (A4);
   - ownership: `apps`, `shots_per_game`, `rating` come from Summary and are asserted
     equal in the other two (A6).
2. `parse_standings.py`:
   - `parse_views(page: PageCapture) -> StandingsCandidate`;
   - one row per `team_id`, three splits;
   - `team_id` set must equal the feed set (A18);
   - `has_league_table = false` → zero rows; any table present is ignored.
3. `canonical.py`:
   - `canonical_bytes(candidate, standings, version=1) -> bytes`;
   - rows sorted by `team_id`, keys sorted, floats via `repr`, `None` as `null`;
   - includes `tournament_id`, `is_opta`, `team_id`, the 60 measures and the three
     standings views;
   - excludes `paging`, `name`, presentation order, `seasonId`;
   - `fingerprint = sha256(canonical_bytes).hexdigest()`.
4. Golden files: copy the nine captures and the three standings views into
   `tests/golden/caps/`; store `tests/golden/expected.json` with the 20-row checksum.
5. `test_parse.py`: golden parse, drift trap, missing value → `None`, 19-team cohort →
   `IncompleteCohort`.
6. `test_canonical.py` (property tests with `hypothesis`):
   - shuffling rows does not change the fingerprint;
   - shuffling dict keys does not change it;
   - changing one measure by `1.0` always changes it;
   - changing a rank or a form character changes it;
   - `repr` round-trip is stable for the full float range present;
   - the same candidate on a different machine/Python patch is byte-identical (golden
     hash).

### Exit

`pytest tests/test_parse.py tests/test_canonical.py tests/test_standings.py` green, and
the golden checksum in `expected.json` matches.

**Risk:** float `repr` is stable across CPython versions in practice, but not guaranteed
by the language. Mitigation: `canonical_version` is stored on the header, and the test
pins a hash so a change is caught rather than silent.

---

## 9. P6 — Publish (1.5 days)

**Goal:** one transaction that is safe to retry, crash, and backfill.

### Tasks

1. `validate.py`: `run_assertions(con, candidate, standings, spec) -> list[AssertionFailure]`.
   Each assertion is a SQL string in `sql/002_assertions.sql` returning offending rows.
   `validate.py` maps an assertion id to an action (`BLOCK`, `RETRY`, `WARN`).
2. `publish.py`:

```python
def publish(con, candidate, standings, spec, run) -> Outcome:
    con.execute("BEGIN")
    try:
        inserted = con.execute(
            """
            INSERT INTO competition_snapshot (...) VALUES (...)
            ON CONFLICT (parent_snapshot_id, content_fingerprint) DO NOTHING
            RETURNING snapshot_id
            """,
            header_params,
        ).fetchall()

        if not inserted:
            update_checkpoint(con, spec, "no_change")
            con.execute("COMMIT")
            return Outcome.NO_CHANGE

        insert_facts(con, candidate, standings, inserted[0][0])
        update_checkpoint(con, spec, "accepted")
        con.execute("COMMIT")
        return Outcome.ACCEPTED
    except Exception:
        con.execute("ROLLBACK")
        raise
```

Three measured facts drive this shape:

- `RETURNING` is empty when the conflict is confirmed, so "did I create this?" needs no
  second query and no race.
- A constraint error **aborts** the transaction; the explicit `ROLLBACK` is required.
- A bare `COMMIT` after an abort does **not** raise — it silently commits nothing. Never
  put `COMMIT` in a `finally`.

3. `insert_facts` writes the 20 team rows **and** the standings rows in the same
   transaction, using a single multi-row `INSERT ... VALUES` with **escaped literals**,
   not parameters. Measured on DuckDB 1.5.6: 20 × 62 rows take ~2,485 ms parameterised,
   ~27 ms as literals, ~73 ms via `COPY`.

   A single `sql_literal()` helper handles `int`, `float`, `str`, `None`, rejects `NaN`
   and `inf`, and escapes `'` as `''`. A property test round-trips adversarial strings.

4. Parent selection: `parent_snapshot_id` is the `snapshot_id` of the latest accepted
   snapshot **by `observed_at`**, or `'genesis'`. Not by `accepted_at`: a backfill would
   otherwise claim to be the newest state.
5. `reconcile(con)` at startup:
   - runs still `running` that have a snapshot in `competition_snapshot` → `accepted`;
   - the rest → `abandoned`.
6. `test_publish.py` — the five must-haves plus:
   - publish twice → one snapshot;
   - crash after header, before facts → zero snapshots, run `abandoned`;
   - a standings insert failure rolls back the header and the team facts;
   - a `has_league_table = false` stage publishes the header and 20 team facts with zero
     standings rows;
   - revert A→B→A → three snapshots;
   - a backfilled older snapshot does **not** become latest;
   - a constraint error mid-transaction leaves zero rows and a clean connection.

### Exit

`pytest tests/test_publish.py` green. The suite runs against a temp DuckDB file, not
`:memory:`, so WAL and reopen behaviour are exercised.

---

## 10. P7 — Views (½ day)

**Goal:** the three questions the data can answer, with the known bugs designed out.

### Tasks

1. `sql/003_views.sql`:
   - `v_latest_team_state` — pick the snapshot first, then join. Order by
     `observed_at DESC`; a backfill must not change "latest".
   - `v_latest_standings` — the same snapshot selection, joined to
     `fact_standings_snapshot` on `(snapshot_id, team_id)`.
   - `v_latest_team_with_standings` — one row per team at the latest snapshot: the 60
     measures plus the 30 standings measures. This is the consumer view; the join is
     never on `team_name`.
   - `v_snapshot_delta` — `lag()` over the **full history**, partitioned by
     `(tournament, season, stage, team_id)`, ordered by `observed_at`. Delta only for
     `apps`, `goal`, `yellow_card`, `red_card`; `is_correction` when `d_apps < 0`.
   - `v_pipeline_freshness` — one row per stage with `last_success_at`,
     `age_seconds`, `accepted_snapshots`, `last_outcome`.
2. `test_views.py`:
   - **latest-state leak:** delete a team from the newest snapshot; it must not reappear
     from an older one.
   - **delta partition:** a team absent in the middle snapshot must produce a gap, not a
     silently joined diff.
   - **backfill:** insert an older observation; `v_latest_team_state` is unchanged.
   - **standings join:** `v_latest_team_with_standings` has one row per team, and a
     knockout stage has zero standings columns populated.
   - **freshness:** one row per configured stage, `age_seconds >= 0`.

### Exit

All five tests green. The latest-state query is a view, not a CTE copied into three
dashboards.

---

## 11. P8 — CLI and operations (1 day)

**Goal:** an operator can run, inspect, and recover without opening Python.

### Tasks

1. `cli.py` (argparse, no new dependency):
   ```
   dataderby run       [--stage KEY] [--allow-apps-decrease] [--dry-run]
   dataderby probe     [--stage KEY]
   dataderby replay    --run-id ID | --raw-dir PATH [--check]
   dataderby verify    [--snapshot ID] [--address STAGE OBSERVED_AT]
   dataderby freshness [--json]
   dataderby stages    list
   ```
2. Exit codes: `0` ok/no_change · `2` fetch_failed · `3` blocked · `4` config ·
   `5` locked · `6` internal.
3. `run` wires the ten steps: lock → config → run row → fetch → raw → parse → validate →
   publish → checkpoint → exit.
4. `replay` rebuilds from raw into a scratch DB and compares
   `(tournament, season, stage, observed_at) → content_fingerprint`. It does **not**
   compare ids.
5. `verify` checks the header/fact anti-join, the unique edge, and the address uniqueness.
6. `test_cli.py`: exit codes, `--dry-run` writes nothing, `replay --check` passes on the
   goldens and fails on a mutated raw file.

### Exit

`uv run python main.py run --dry-run` exits 0 and writes nothing; `uv run python main.py
freshness` prints one row per stage.

---

## 12. P9 — Measurement harness (½ day)

**Goal:** the open questions become commands, not blog posts.

### Tasks

1. `dataderby measure e1|e3|e5` with the protocols from v1 §14.
2. E2 gets a written protocol and a report template, not code — it needs a live matchday.
3. `docs/open-questions.md` seeded with E1–E6, owner, and current status.

### Exit

E1 and E3 produce a written result from live data; E2 has a scheduled window.

---

## 13. P10 — The v1 gate (1 day)

**Goal:** prove it runs unattended, with the licence decision already recorded.

### Tasks

1. Schedule: daily heartbeat plus a post-match window (`docs/research/whoscored-cadence.md`).
2. Backup: `data/raw/` to a second location; restore drill documented.
3. `docs/adr/0006-source-use.md` points at the 2026-10-20 decision in
   `docs/research/whoscored-decisions.md`; no licence question remains open.
4. README: what the data can and cannot answer (v1 §8.3).

### Exit — the v1 gate

1. Two consecutive scheduled runs, no manual intervention.
2. The second reports `no_change` and writes nothing.
3. A poisoned cohort (19 teams) is refused; the previous snapshot stays latest.
4. `v_pipeline_freshness` shows both runs.
5. A raw file restored from backup replays to the same content map.
6. All four `AGENTS.md` gates pass.

---

## 14. Test matrix

| Area | Tests | Level |
|---|---|---|
| Config | 4 | unit |
| Contract | 4 | unit, against goldens |
| Schema | 7 | integration |
| Fetch | 6 | integration, replay server |
| Parse | 6 | golden + traps |
| Standings | 6 | golden DOM + traps |
| Canonical | 6 | property-based |
| Publish | 10 | integration |
| Views | 5 | integration |
| CLI | 4 | integration |
| **Total** | **58** | |

The five must-haves from v1 §11.1 are a subset of the publish row; they are not optional
and they are not replaced by the larger count.

---

## 15. Risks, and what I do about them

| Risk | Likelihood | Mitigation |
|---|---|---|
| `mypy main.py` does not follow `src/` | medium | `mypy_path`, verified by breaking a type in P0 |
| DuckDB transaction semantics differ from Postgres | measured | explicit `ROLLBACK`, no `COMMIT` in `finally`; `uv.lock` pins 1.5.6 |
| Parameter binding makes the load 90× slower | measured | literal builder + escape property test |
| Float `repr` changes across Python versions | low | `canonical_version` + pinned golden hash |
| Raw payloads are not redistributable | certain | `data/` ignored before the first run |
| Source changes shape mid-season | likely | A15 blocks; raw keeps the evidence |
| Standings DOM changes or the split toggle changes | medium | A18–A21 block; the page HTML is raw, so the parser can be repaired and replayed |
| Page load is gated while the feed is not (or vice versa) | medium | the page is one request per stage; a gate is `blocked`, not a partial snapshot |
| `team_id` unstable across seasons | unknown | E4; `dim_team` is deferred, not designed away |
| Single-writer lock blocks a dashboard | low | readers open `READ_ONLY`; trigger is a second writer |

---

## 16. First 48 hours

If I start now, in order:

1. P0 skeleton; gates green. (2 h)
2. P1 ADRs 0001–0005 and `config/stages.toml`. (2 h)
3. P2 contract; the 60-column and 30-standings-column tests. (3 h)
4. P3 schema and `db.py`; schema tests. (5 h)
5. P4 page + standings + fetch against the replay server. (6 h)
6. P5 parse + canonical, goldens, property tests. (6 h)

That is the first two days. P6 is where the system becomes safe; nothing before it is
allowed to write to the real database.

---

## 17. What this plan does not cover

- v2 features (per-match events, xG, `dim_team`).
- A public API or dashboard.
- Multi-source ingestion.
- Historical backfill beyond the nine captures.

Each is listed in v1 §1.3 and stays out until the v1 gate passes.
