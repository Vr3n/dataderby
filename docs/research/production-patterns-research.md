# Production patterns for a single-source snapshot pipeline

**Status:** research note · 19 Oct 2026
**Feeds:** `plans/v1-build-plan.md`
**Scope:** how teams actually build ingestion → validation → publish pipelines, what is
consensus, what is contested, and which parts apply to a nine-request-per-day football
stats feed stored in DuckDB.

---

## 0. Method, and how much to trust this

Two kinds of claim appear below and they are labelled differently:

- **Measured** — reproduced in this repository. Numbers are in `experiments/id-scheme/`.
- **Borrowed** — industry practice taken from vendor documentation, engineering blogs and
  standards. Useful, but not evidence about *our* data.

The borrowed material is not peer-reviewed. Vendor blogs have an incentive to describe
the problem their product solves. I have preferred primary documentation (DuckDB docs,
Kimball, Databricks) over listicles, and I have rejected several patterns that are
popular but wrong for a single-writer, 1,240-row-per-snapshot workload.

The question for every pattern was not "is this best practice?" but "what breaks if we
skip it, at our size?" A pattern with no failure mode at our volume is ceremony.

---

## 1. The architecture that recurs

Nearly every mature batch pipeline converges on four layers, whatever the vendor calls
them:

| Layer | Job | Our equivalent |
|---|---|---|
| Landing / bronze | Immutable copy of what the source sent | `data/raw/` + `raw_capture` |
| Conformed / silver | Parsed, typed, validated, deduplicated | the candidate row set, in memory |
| Published / gold | Queryable, versioned, documented | `competition_snapshot` + `fact_team_snapshot` |
| Metadata | What ran, when, what happened | `ingestion_run`, `pipeline_checkpoint` |

Two properties are treated as non-negotiable across the sources:

1. **Raw is append-only.** The landing zone is never edited. It is the replay guarantee:
   if silver or gold is wrong, you rebuild from raw rather than from a backup of the
   warehouse. Databricks states it plainly — "Bronze is append-only with full audit
   columns; if Bronze is mutable, you lose the ability to explain historical state."
2. **Every layer has a contract.** The layer promises something specific to the layer
   below it. "Each layer is a contract, not a folder."

What differs between teams is *where validation happens*. The consensus has moved from
"test after the fact" to "refuse to publish" — which is the next section.

> **Applicability.** Both properties are already in the v1 design. The layer names are
> not: our "gold" is a set of views over immutable snapshots, not a materialised
> aggregate. That is a deliberate simplification and should be stated in the README so a
> reviewer does not go looking for a `gold` schema.

---

## 2. Idempotency

### The consensus

- Exactly-once **delivery** is not achievable across a network. The realistic guarantee
  is at-least-once delivery plus an **idempotent write**.
- The race-free mechanism is a **unique constraint plus the write in the same
  transaction**. A check-then-insert leaves a TOCTOU window in which two retries both
  pass the check.
- The stored **idempotency key** is a claim, not a lock. The database constraint is what
  settles the race; the key is how you recognise the retry.
- A **checkpoint is an optimisation**, not the correctness mechanism. It avoids work; it
  does not prevent duplicates. If the checkpoint is lost or stale, the constraint still
  holds.

This is the single most repeated point across the idempotency literature, and it is the
one most often implemented backwards. Teams commonly persist a "last processed" marker
and trust it. That works until the marker is written before the data, or the process
dies between the two.

### What we measured

The `experiments/id-scheme` suite puts eight failure paths through both schemes:

| Path | Result |
|---|---|
| identical retry | 1 row |
| rollback after header + fact | 0 rows |
| kill -9 inside the transaction | 0 rows |
| stale checkpoint, same edge | 2 rows (correct: two observations) |
| same content, different parent | 2 rows (correct: a revert) |
| second writer process | refused by the file lock |

Both schemes scored 8/8. The identifier did not matter; the transaction did. That is the
borrowed consensus reproduced locally, and it is why the plan puts the transaction
boundary before the id format.

### The DuckDB specifics (measured, 1.5.6)

Three behaviours change how the publish loop must be written:

1. `INSERT ... ON CONFLICT DO NOTHING RETURNING snapshot_id` returns the row when it was
   inserted and **an empty result when the conflict was confirmed**. That is a clean,
   race-free "did I create this?" signal — no follow-up `SELECT` and no window.
2. A constraint violation **aborts the transaction**. Later statements raise
   `TransactionException: Current transaction is aborted (please ROLLBACK)`.
3. A bare `COMMIT` after an aborted transaction **does not raise** — it silently commits
   nothing. A `finally: con.execute("COMMIT")` would therefore discard a run and report
   success.

Also: `with duckdb.connect() as con:` **closes the connection** on exit; it is not a
transaction context manager. Using it as one raises `Connection already closed!` on the
next statement.

> **Consequence for the build.** The publisher uses an explicit
> `BEGIN / try / COMMIT / except ROLLBACK / finally close` protocol with no `COMMIT` in
> `finally`. This is one of the few places where a small mistake is silent.

---

## 3. The dedupe key

Three candidate keys, in increasing order of correctness:

| Key | Retry-safe | Preserves a revert | Survives a backfill |
|---|---|---|---|
| content fingerprint alone | yes | **no** — A→B→A collapses | n/a |
| identity alone (UUID/ULID PK) | **no** — new id each retry | yes | yes |
| **edge** `(parent, content)` | yes | yes | yes, as new rows |

Content-only is the naive choice and it is genuinely tempting: "the same numbers are the
same row." It fails the moment a value reverts, which in football data happens constantly
(a goal is discredited, a card is overturned, a manager change is reversed). The revert
is then invisible — history is silently rewritten, which is the exact failure the
snapshot model exists to prevent.

Identity-only is not deduplication at all: a retry mints a new ULID and inserts a second
row.

The edge key is the minimum that satisfies all three. It is also what Kimball-style
periodic snapshots imply: a snapshot is defined by its position in the sequence as well
as its content.

> **Measured:** content-only produced 2 rows for A→B→A where 3 were correct; edge-keyed
> produced 3 in both schemes.

---

## 4. Modelling

### Periodic snapshot fact, not SCD2

Kimball's **periodic snapshot fact table** is the closest published pattern: one row per
entity per observation period, holding cumulative-to-date measures. That is exactly our
grain.

SCD Type 2 solves a different problem: a *dimension* attribute changing over time, with
effective-dating so a fact can join to the version that was current at the fact's event
time. We deferred `dim_team` because we have no dimension yet — team name is the only
attribute, and we store it as observed on the fact.

The distinction that matters operationally:

| | SCD2 dimension | Our snapshot fact |
|---|---|---|
| Rows mutate? | old row gets `valid_to` | never |
| Current state | `where valid_to is null` | a view over the newest snapshot |
| Late-arriving fact | re-point the surrogate key | insert a new snapshot in sequence |
| Cost of a rebuild | update valid windows | recompute ids, content unchanged |

SCD2's mutability is the reason it is the wrong fit here: an update to `valid_to` is a
rewrite of history, and it requires update permissions on the table. Our fact table is
insert-only, which makes the replay guarantee trivial to state.

### Grain must be declared, not implied

Every modelling source says the same thing: declare the grain in one sentence before
writing DDL. If the grain is ambiguous, every downstream aggregate is ambiguous too.

Ours, in two sentences:

- `competition_snapshot`: one row per accepted observation of one stage.
- `fact_team_snapshot`: one row per team per accepted snapshot.

### Late-arriving data: three strategies

The literature offers three, and they differ by data volume:

1. **Rolling window recompute** — keep the last N days open, recompute on every run.
   Cheap, absorbs routine lateness, fails for corrections older than the window.
2. **MERGE / upsert** — update the affected partition in place. Requires mutable storage
   and a reliable business key.
3. **Rebuild from raw** — recompute the affected range from the immutable log. Most
   expensive per run, most correct.

At 1,240 rows per snapshot, strategy 3 is affordable and strategy 2 is unnecessary. The
measured backfill (one late capture inserted mid-chain) moved 5 of 5 downstream ids,
which is the cost we accept: the *content* is reproducible, the *names* are not.

> **Applicability.** Strategy 3 is a consequence of small data, not a universal
> recommendation. If the feed grew to per-match event data, strategy 2 (partition
> overwrite) would become the right answer.

---

## 5. Quality gates

### Write-Audit-Publish

WAP is the industry name for what the v1 design calls the publish contract: write to an
isolated area, audit it, publish only if the audit passes. It was popularised at Netflix
and is now the default framing in dbt, Dagster, lakeFS and Databricks material.

The usual implementation uses a staging table or a branch (Iceberg `wap.id`, zero-copy
clone, schema swap). We do not need one: **uncommitted writes are already invisible to
readers**, so the transaction *is* the staging area. This is a legitimate variant for a
single-writer store and should be written down, because a reviewer will ask where the
staging table is.

### Retry, block, or quarantine

The sources separate transient from permanent failures, and the split is not cosmetic:

| Failure | Class | Action |
|---|---|---|
| source mid-update (19 of 20 teams) | transient | retry with backoff |
| overall published before the splits | transient | retry, then block |
| gate page / 403 | transient | retry, escalate credentials |
| provider added or removed a column | permanent | block, page a human |
| wrong stage in config | permanent | block |
| one value missing | neither | store `NULL` |

The rule that generalises: **never silently drop a row to make a check pass.** A dropped
row is indistinguishable from a team that did not play. `NULL` is honest; absence is a
lie.

Quarantine (write to a side table and continue) is the fourth option. It is right when
partial data is still useful. Here it is not: a 19-team snapshot is not a slightly worse
snapshot, it is a wrong one, and publishing it would poison the delta series.

### Contract testing vs runtime assertion

- **Contract tests** run in CI against fixtures and fail the build.
- **Runtime assertions** run against live data and fail the run.

Both are needed, and they check different things. A contract test cannot know that today
the source returned a gate page; a runtime assertion cannot prevent a bad deploy. The
v1 design's A1–A21 are runtime assertions, and the trap/clean fixtures are contract tests
for the assertions themselves.

Tools like Great Expectations and Soda formalise this, but they are orchestration-shaped:
a suite of expectations, a results store, a docs site. At 21 assertions across two facts,
plain SQL that returns offending rows is smaller, transparent, and has no dependency.
This is a judgement call, not a law — the trigger to adopt a framework is when assertions
span several tables and teams.

---

## 6. Observability

Monte Carlo's five pillars are the most cited framing:

| Pillar | Question | Our signal |
|---|---|---|
| Freshness | is the data current? | `v_pipeline_freshness.age_seconds` |
| Volume | did the row count change? | 20 teams × 60 columns, asserted |
| Schema | did the shape change? | A15 `statColumns`, `canonical_version` |
| Distribution | are the values sane? | A8 ranges, A5 additivity |
| Lineage | where did this come from? | `parent_snapshot_id`, `raw_capture` → snapshot |

The sixth, added later, is **pipeline observability** — job health, latency, retries —
which for us is `ingestion_run`.

Two conclusions from the material:

1. **A run ledger beats log scraping.** Every mature design has an audit table with run
   id, source, status, timestamps, record counts, error. Logs are for debugging; the
   ledger is for operating.
2. **Freshness is an SLI, not a boolean.** "Last success 4 minutes ago" is useful; "OK"
   is not. Store the timestamp and compute the age in the view.

What we deliberately do not need: anomaly detection on distributions. Twenty teams and a
handful of measures do not give a baseline worth fitting. Range checks and additivity
catch the failures that actually occur.

---

## 7. Operations

### Single-writer stores

DuckDB is explicit: one read-write process per database file, enforced by a file lock.
Multiple readers are fine; a second writer gets an error. The documented patterns are:

- one writer process, with an application-level lock so losers exit cleanly;
- readers opened `READ_ONLY`;
- at larger scale, the writer emits immutable Parquet and readers query the files, which
  removes shared mutable state entirely.

We are firmly in category one. The trigger to move to Parquet is a second concurrent
writer or a read load that interferes with ingestion — neither exists at nine requests a
day.

Two operational consequences that are easy to miss:

- **Do not copy a live `.duckdb` file as a backup.** A copy taken mid-transaction is
  undefined. Use `EXPORT DATABASE`, or stop the writer and `CHECKPOINT` first.
- **The WAL hides recent data.** File size measured before `CHECKPOINT` and before the
  connection closes understates the database. Any storage claim must be measured after
  both.

### Backup, or: what is actually the backup?

If raw is immutable and the transform is deterministic, the database is **derived state**.
That makes the backup policy unusually simple: back up `data/raw/`, not the `.duckdb`.
The restore drill is "copy raw, run replay, compare the content map". A database backup is
still worth taking for speed, but it is not the system of record.

This inverts the usual instinct and should be stated in the runbook, because the first
person on call will reach for the `.duckdb`.

### Orchestration

The consensus is not "use Airflow". It is: adopt an orchestrator when you have
cross-pipeline dependencies, backfill as a first-class operation, or more than a handful
of schedules. Below that, cron plus a lock plus a run ledger is smaller and has fewer
failure modes.

We are below that line: one pipeline, one schedule, nine requests. The trigger to revisit
is a second source or a dependency between pipelines.

---

## 8. Testing

The pyramid that recurs for data pipelines:

| Level | What it proves | Our tests |
|---|---|---|
| Pure function | parsing and canonicalisation are correct and stable | golden files, property tests |
| Integration | the transaction, constraints and views behave | DuckDB in a temp dir |
| Contract | fixtures trip the assertions they should | trap/clean pairs |
| End-to-end | a full run produces the expected snapshot | replayed HTTP server |
| Live | the source still behaves | one opt-in test |

Two practices worth adopting that are less common than they should be:

- **Property-based testing for canonicalisation.** The invariants are exactly the ones
  that matter: row order does not change the fingerprint; key order does not; a one-unit
  change always does. Hypothesis generates the cases instead of me guessing them.
- **Trap/clean fixture pairs.** Every assertion needs a fixture that must fail and one
  that must pass. An assertion that never fires is worse than no assertion, because it
  creates false confidence. The v1 plan already requires this for A1–A21.

One anti-pattern to avoid: a test that asserts `snapshot_id` equality after a rebuild.
Under the adopted scheme the ids are random, so that test fails for the wrong reason. The
CI assertion must compare `(stage, observed_at, content_fingerprint)`.

---

## 9. What we deliberately do not do

Every omission below has a trigger. This is the list I want a reviewer to attack, because
each item is a place where "best practice" was consciously declined.

| Not doing | Why not, at our size | Revisit when |
|---|---|---|
| Orchestrator (Airflow/Dagster) | one pipeline, one schedule | a second source, or cross-pipeline deps |
| dbt | one fact table, no transformation graph | more than ~5 models, or analysts writing SQL |
| pandas | no need; adds a large dependency | ad-hoc analysis that outgrows SQL |
| Great Expectations / Soda | 21 assertions, two facts | assertions span tables and owners |
| Streaming / CDC | the source is a pull API | a push feed or sub-minute freshness |
| `dim_team` | no dimension attributes beyond a label | E4 proves `team_id` is unstable |
| Partitioned overwrite | 1,240 rows per snapshot | per-match event data |
| Schema registry | one producer, one consumer | a second consumer with its own contract |

The research does not say these tools are bad. It says they solve problems we do not yet
have, and each one costs a dependency, a config surface, and an upgrade path.

---

## 10. Mapping: pattern → component

| Pattern | Source of the idea | Where it lands | Status |
|---|---|---|---|
| Immutable landing zone | Databricks medallion | `raw.py`, `data/raw/` | to build |
| Run ledger | Start Data Engineering, Databricks | `ingestion_run` | to build |
| Idempotent write via unique constraint | idempotency literature | `publish.py`, DDL | to build |
| Edge-keyed dedupe | Kimball periodic snapshot | `UNIQUE(parent, content)` | decided |
| WAP inside a transaction | Dagster / dbt / lakeFS | `publish.py` | to build |
| Retry vs block classification | WAP material | A1–A21 actions | designed |
| Contract + trap fixtures | data contracts | `tests/test_assertions.py` | to build |
| Five pillars | Monte Carlo | views + assertions | designed |
| Single writer + lock | DuckDB docs | `lock.py` | to build |
| Raw-as-backup | medallion replay guarantee | runbook | to write |
| Property tests | Hypothesis | `tests/test_canonical.py` | to build |

---

## 11. Measured here vs borrowed

To keep the two honest:

**Measured in this repository**

- 24-case matrix, both schemes: A 24/24, B 21/24, B-null 20/24.
- Exact replay: ids equal under A, not under B; pin-by-observed-at works for both.
- Backfill: 5/5 downstream ids change in both schemes.
- NULL root: 2 rows for one observation.
- Storage, insert latency, parameter-binding cost, transaction behaviour (above).

**Borrowed, not verified against this data**

- That the five pillars catch most failures — plausible, untested here.
- That WAP reduces incidents — plausible, untested here.
- That cron is sufficient below the orchestration threshold — a judgement from the
  sources, not a measurement.
- That content-only dedupe is common — inferred from the literature, not from our peers.

The build plan only depends on the first list. The second informs sequencing and scope,
not correctness.

---

## 12. Sources

Primary documentation

- DuckDB — Concurrency. https://duckdb.org/docs/current/connect/concurrency.html
- DuckDB — INSERT / ON CONFLICT / RETURNING. https://duckdb.org/docs/lts/sql/statements/insert.html
- DuckDB — CHECKPOINT. https://duckdb.org/docs/lts/sql/statements/checkpoint.html
- DuckDB — Analytics-optimized concurrent transactions (WAL, checkpointing).
  https://duckdb.org/2024/10/30/analytics-optimized-concurrent-transactions.html
- Databricks — Medallion architecture. https://learn.microsoft.com/en-us/azure/databricks/lakehouse-architecture/deployment-guide/delta-lake
- Python Packaging Guide — src layout.
  https://www.pyopensci.org/python-package-guide/package-structure-code/python-package-structure.html
- uv — src vs flat layout. https://pydevtools.com/handbook/explanation/src-layout-vs-flat-layout

Patterns and practice

- Dagster — Write-Audit-Publish. https://dagster.io/blog/python-write-audit-publish
- lakeFS — Write-Audit-Publish. https://lakefs.io/blog/data-engineering-patterns-write-audit-publish
- dbt Labs — Testing is not enough (WAP).
  https://www.getdbt.com/blog/testing-is-not-enough-transforming-data-quality-with-write-audit-publish
- Kimball Group — Slowly changing dimensions.
  https://www.kimballgroup.com/2005/03/slowly-changing-dimensions-are-not-always-as-easy-as-1-2-3
- Holistics — The three types of fact tables.
  https://www.holistics.io/blog/the-three-types-of-fact-tables
- Monte Carlo — What is data observability (five pillars).
  https://montecarlo.ai/blog-what-is-data-observability
- Barr Moses — Introducing the five pillars.
  https://medium.com/data-science/introducing-the-five-pillars-of-data-observability-e73734b263d5
- Idempotency keys and exactly-once semantics.
  https://pavanrangani.com/blog/idempotency-keys-exactly-once-api-design-guide
- BackendBytes — Idempotency patterns.
  https://backendbytes.com/articles/idempotency-patterns-distributed-systems
- Late-arriving data guide.
  https://thecloudsupportengineer.com/better-late-than-never-a-guide-to-handling-late-arriving-data
- Backfilling with idempotent pipelines. https://www.ml4devs.com/what-is/backfilling-data
- Soda — Guide to data contracts. https://soda.io/blog/guide-to-data-contracts
- Collate — Data contracts. https://www.getcollate.io/learning-center/data-contracts
- DuckDB in production: limitations. https://hikmahtechnologies.com/blog/is-duckdb-safe-for-production
- Orchestration tool comparison.
  https://guptadeepak.com/tools/top-6-workflow-orchestration-tools-2026
- Hypothesis — property-based testing.
  https://oneuptime.com/blog/post/2026-01-30-how-to-build-property-based-testing-with-hypothesis/view
