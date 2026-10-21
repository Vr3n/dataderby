# dataderby — architecture decisions

**Subject:** a historical analytical dataset built from a scraped source that publishes *cumulative team statistics as JSON as a competition progresses*.
**Status:** options paper. Nothing here is locked. Four decisions need a call; everything else follows from them.
**Reading time:** ~25 minutes, or skim §4–§7 (one decision each) and read §9.

---

## 0. What this document is

You asked for every option, with the why / how / what and the technical detail, plus a recommendation. This is that.

It is written against two inputs:

1. `docs/football_competition_data_engineering_field_guide.docx` — the design guide already in the repo.
2. The established literature the guide is unknowingly re-deriving: Kimball dimensional modelling, SCD Type 2, bi-temporal modelling, Functional Data Engineering (Beauchemin), dbt/SQLMesh snapshots, dlt, Dagster, data contracts, Monte Carlo's observability pillars, event-time/watermark theory, and Simon Willison's git-scraping.

§2 is the important part: it shows that the guide's instincts are correct but that it is missing four named patterns, two of which change the design. §3 lists what is settled and not worth re-litigating. §4–§7 are the four decisions. §8 covers the cross-cutting concerns that every option has to answer anyway. §9 is the recommendation assembled into one picture.

Where I state a fact about a tool I name it; where I'm giving an opinion I say "I would".

---

## 1. The problem, stated precisely

One sentence, because everything else is a consequence of it:

> At each accepted observation point, the source reports a table of teams and a set of **cumulative** statistics for those teams. We want to retain every reported state so the same team can be compared with itself and with others across time.

Three properties of this that drive the design:

**The values are cumulative, not per-event.** A team's goals-for is a season-to-date total. The difference between two snapshots bounds combined activity, but it cannot be attributed to a match unless exactly one match sits between them. This is the guide's §1.5 and it is the single most important correctness constraint in the project.

**The cadence is event-driven and irregular.** Snapshots are triggered by fixtures finishing, and the source publishes late and sometimes in batches. Kimball's *periodic snapshot* assumes a fixed period and uniform density; ours has neither. That mismatch is why the guide hedges its own terminology, and it is why the history model is a genuine decision rather than a lookup.

**The source is thin and hostile.** No update timestamp, no ETag, no revision id, an anti-bot gate, and possible silent corrections. We cannot ask the source to tell us what changed.

---

## 2. The field guide vs. the literature

### 2.1 The guide independently re-derived these patterns

| Field guide | Established name | Verdict |
|---|---|---|
| "Declare the grain first: one row = team × snapshot" | Kimball **grain declaration** | Correct, and correctly given first place |
| "Event-driven historical state snapshot, borrowing from periodic snapshots" | Kimball **periodic vs accumulating snapshot facts** | Right instinct, wrong neighbour — see §2.2 |
| "Append a new version, never overwrite in place" | **SCD Type 2** | Same pattern. The guide never uses the term |
| "Five timestamps, don't collapse into one date" | **Bi-temporal**: valid time vs transaction time | The rigorous form of the same idea |
| raw → staging → model → views | **Medallion** (bronze/silver/gold) / dbt staging→marts | Identical |
| "Replayable = reprocess a stored capture, not re-request the site" | **Functional Data Engineering** (Beauchemin) | Identical |
| "last_seen vs last_committed fingerprint" | Checkpoint / high-water mark | Identical |
| "Fingerprint = canonicalised digest, exclude volatile fields" | Change detection; SQLMesh **model fingerprint** | Correct but incomplete — see §8.3 |
| "Validation is a contract, not a feeling" | Sanderson **data contracts**; Moses **5 pillars** (freshness, volume, schema, distribution, lineage) | The guide reinvents the pillars without the vocabulary |
| "DuckDB first, Parquet when useful, FastAPI later" | Tigani **"Big Data is Dead"**; Dagster **software-defined assets** | Well-supported |
| "Change to the table does not prove change to the details" | Akidau **event time vs processing time, watermarks** | Same problem, formal machinery |

### 2.2 The four real gaps

**(a) It is SCD Type 2, and that is a solved problem.**
The guide builds versioning by hand. `dbt snapshot` emits `dbt_valid_from` / `dbt_valid_to` / `dbt_scd_id` from two built-in strategies. SQLMesh has an `SCD_TYPE_2` model kind with `valid_from` / `valid_to`. Either gives you point-in-time queries for free. This does not mean we must adopt them — it means we should *choose* rather than *invent*.

**(b) It merges two things that should be split.**
The guide puts a team's *identity* (name) and its *measures* (points, xG) on the same versioned row. In dimensional modelling those are different things with different rates of change: team names, league membership and promotion/relegation are the actual **slowly changing dimension**; season-to-date metrics are the **fact**. Splitting them makes both cheaper and cleaner.

**(c) It fingerprints source content only.**
SQLMesh's insight is that a model's fingerprint includes **its own logic and its upstream dependencies**, because changing the parser must also force a recompute. We need two fingerprints, not one — one to decide "is this a new observation?", one to decide "do derived tables need rebuilding?". The guide has `schema_version` in its raw manifest but never wires it to anything.

**(d) It never asks build-vs-buy.**
`dlt` already does schema inference and evolution, incremental loading with persisted state, nested-JSON normalisation, and loads to DuckDB. That is most of the guide's §3.6 and §5.2. The guide hand-rolls it without noting the alternative exists.

### 2.3 Where the guide is better than most published advice

Keep these verbatim; they are the parts I would defend in review:

- The **asymmetry**: a changed table may imply ready details, but an unchanged table does **not** prove unchanged details. Most "hash the page" advice gets this wrong.
- **Atomic publication of a complete cohort** — 18 of 20 teams must never present as "latest".
- **Run outcome ≠ data outcome** — "checked, nothing new" is a success, not a failure.
- **Refusing to manufacture match-level attribution from cumulative deltas.**

---

## 3. Invariants

These are supported by both inputs and I do not propose to debate them.

1. **Raw evidence is immutable and append-only.** Never the only copy of anything, never overwritten.
2. **Derived layers are rebuildable from raw** with recorded logic + schema versions.
3. **Publication is atomic per observation.** A snapshot is validated complete, then becomes visible as one unit.
4. **The checkpoint advances only after acceptance.** `last_seen` and `last_committed` are distinct.
5. **A team is identified by a stable source id**, never by a display name.
6. **Missing is not zero.** Null means "not provided"; zero means "provided and zero".
7. **A season is identified by (tournament, season), not by year.** (This was ADR-0003 before the ADRs were removed; it remains correct.)
8. **Deltas are derived, flagged as approximate, and never computed for ordinal or ratio metrics.**
9. **Every accepted observation records when it was observed, in UTC.**

---

## 4. Decision 1 — How to model the history

### 4.0 Why this matters

This decides what a query has to look like forever, and it decides what happens when the provider corrects an old number. It also decides whether "compare all twenty teams at matchday 10" is one join or a correlated subquery.

There are really three axes here, and conflating them is what makes this feel hard:

- **Axis 1 — the history mechanism:** how versions are produced (immutable rows, mutable row + validity period, or the database doing it).
- **Axis 2 — the shape:** wide (one column per metric) vs long (one row per metric).
- **Axis 3 — what gets versioned:** measures only, or measures *and* team attributes.

I'll take them in order.

---

### 4.1 Axis 1, Option A — Immutable snapshot fact

**What.** One row per team per accepted observation. Nothing is ever updated. The observation itself is a header row carrying `snapshot_id`, tournament, season, and the timestamps.

**How, technically.** A `snapshot` header table plus a `fact_team_snapshot` table at grain `(snapshot_id, team_id)`. All teams in one capture cycle share one `snapshot_id`, making the comparison cohort explicit and making incompleteness detectable (20 expected teams, 18 rows → reject).

```sql
-- DuckDB
CREATE TABLE competition_snapshot (
    snapshot_id        VARCHAR PRIMARY KEY,
    tournament_id      INTEGER NOT NULL,
    season_key         VARCHAR NOT NULL,       -- '2026-2027'
    stage_id           INTEGER,
    observed_at        TIMESTAMPTZ NOT NULL,
    source_fingerprint VARCHAR NOT NULL,
    accepted_at        TIMESTAMPTZ NOT NULL,
    status             VARCHAR NOT NULL        -- candidate | accepted | rejected
);

CREATE TABLE fact_team_snapshot (
    snapshot_id  VARCHAR NOT NULL,
    team_id      INTEGER NOT NULL,
    ranking      INTEGER,
    rating       DECIMAL(4,2),
    points       INTEGER,
    goals_for    INTEGER,
    goals_against INTEGER,
    -- ... one column per metric, prefixed by section_view
    PRIMARY KEY (snapshot_id, team_id)
);
```

Queries it makes easy:

```sql
-- latest accepted state per tournament/season
CREATE OR REPLACE VIEW latest_team_state AS
SELECT f.*, s.tournament_id, s.season_key, s.observed_at
FROM fact_team_snapshot f
JOIN competition_snapshot s USING (snapshot_id)
WHERE s.status = 'accepted'
QUALIFY row_number() OVER (
    PARTITION BY s.tournament_id, s.season_key, f.team_id
    ORDER BY s.observed_at DESC
) = 1;
```

**How it handles the hard cases.**
- *Provider corrects an old value:* a new snapshot appears with different numbers. The old row is untouched, so the correction is visible as a change between two observations. This is exactly the desired behaviour.
- *Retry / duplicate:* de-duplicate on a logical key (see §8.6); a retry that re-observes identical canonical content produces no new accepted snapshot.
- *Backfill:* re-run the parse for an old capture; you get a new candidate which, if identical, is rejected as a duplicate.

**Pros.**
- Perfect audit trail; nothing is ever destroyed.
- The observation cohort is explicit — incompleteness is a *validation* failure rather than a silent gap.
- Insert-only, so concurrency is trivial and retries are naturally safe.
- Maps directly onto the guide's argument and onto Medallion's bronze→silver.

**Cons.**
- Storage grows with teams × observations. (For us: 20 teams × maybe 40–60 observations a season × a few dozen metrics — kilobytes. Irrelevant.)
- "Current value of X" needs a window function or a view, not a plain read.
- SCD-style "which version was valid on date D" needs care: validity is *observed time*, not "the value was true until then".
- Versioning team *attributes* on these rows duplicates the name on every row.

---

### 4.2 Axis 1, Option B — SCD Type 2

**What.** One row per team, mutated in place: the old version gets `valid_to` set, a new row is inserted with `valid_from` and `is_current = true`. This is Kimball's Type 2, and it is what `dbt snapshot` and SQLMesh produce.

**How, technically.** Two columns of validity plus a change-detection strategy.

```sql
CREATE TABLE dim_team_scd2 (
    team_sk      UBIGINT PRIMARY KEY,   -- surrogate key
    team_id      INTEGER NOT NULL,      -- natural key from source
    team_name    VARCHAR NOT NULL,
    league       VARCHAR,
    valid_from   TIMESTAMPTZ NOT NULL,
    valid_to     TIMESTAMPTZ,           -- NULL = current
    is_current   BOOLEAN NOT NULL,
    dbt_scd_id   VARCHAR                -- stable id for this version
);
```

Two change-detection strategies, straight from dbt:
- **timestamp** — the source supplies an `updated_at` you trust. *We have no such column.*
- **check** — compare a nominated set of columns. This is the one available to us.

The upsert in modern DuckDB (v1.0+, `MERGE` supported):

```sql
MERGE INTO dim_team_scd2 AS t
USING staged AS s ON t.team_id = s.team_id AND t.is_current
WHEN MATCHED AND s.checksum <> t.checksum THEN
    UPDATE SET valid_to = now(), is_current = false
WHEN NOT MATCHED THEN
    INSERT (team_id, team_name, league, valid_from, valid_to, is_current)
    VALUES (s.team_id, s.team_name, s.league, now(), NULL, true);
```
(with a second insert for the new version — the standard MERGE-then-INSERT dance.)

**Pros.**
- Turnkey in dbt and SQLMesh; no bespoke logic.
- Compact: one row per *change*, not per observation. Best when the thing changing is naturally single-valued (a name, a status, a membership).
- Point-in-time joins are idiomatic: `WHERE d.valid_from <= t.observed_at AND (d.valid_to > t.observed_at OR d.valid_to IS NULL)`.
- The right answer for genuinely slowly-changing attributes.

**Cons.**
- **It loses the observation cohort.** "All twenty teams as reported at matchday 10" is not a thing you can read off a Type 2 table unless every team happened to change at that instant.
- Mutating rows means the table has a lifecycle; retries and backfills need care, and the history of the *table* (as opposed to the business history) is opaque.
- Bad fit for our measures: cumulative stats change every matchday for nearly every team, so every team becomes a new version every observation — you get the storage cost of the snapshot model *and* mutation, i.e. the worst of both.
- Validity periods are ambiguous when the source publishes late.

**Verdict on measures: wrong tool.** **Verdict on team attributes: right tool.**

---

### 4.3 Axis 1, Option C — Both (snapshot fact for measures + SCD2 for the team dimension)

**What.** Split the two rates of change. Measures live in an immutable snapshot fact. Team attributes live in a small Type 2 dimension. A `team_sk` (surrogate) links them at the observation's point in time.

**How, technically.** Same fact table as 4.1. A tiny dimension whose rows number in the tens.

```
competition_snapshot (header)       fact_team_snapshot (measures)        dim_team_scd2 (attributes)
  snapshot_id  ───────────────────┐   snapshot_id                        team_sk
  tournament_id                   └── team_sk  ────────────────────────  team_id
  season_key                          team_id                            team_name
  observed_at                         ranking, rating, points, ...       league
  source_fingerprint                                                     valid_from / valid_to
  accepted_at
```

**Pros.**
- Each thing is versioned at its own natural rate. Names cost ~20 rows a season; measures cost 20 × observations.
- Point-in-time team names for free: join with the validity window.
- The fact stays append-only (safe retries) while the dimension absorbs the one place mutation is idiomatic.
- Literally what dimensional modelling prescribes.

**Cons.**
- One more table and one more concept in the first version.
- The surrogate-key join adds a step to every query. (Mitigable with a view.)

**When it pays for itself:** as soon as a team is renamed, promoted, relegated, or appears in two tournaments. That is: immediately after the first full season.

---

### 4.4 Axis 1, Option D — Let the database keep history (system-versioned temporal tables)

**What.** Declare the table as system-versioned and the engine maintains a shadow history table, with temporal query syntax.

**How, technically.** SQL:2011. SQL Server 2016+, MariaDB 10.3+:

```sql
CREATE TABLE team_stats (
    tournament_id INT, team_id INT, points INT,
    valid_from DATETIME2 GENERATED ALWAYS AS ROW START,
    valid_to   DATETIME2 GENERATED ALWAYS AS ROW END,
    PERIOD FOR SYSTEM_TIME (valid_from, valid_to),
    CONSTRAINT pk PRIMARY KEY (tournament_id, team_id)
) WITH (SYSTEM_VERSIONING = ON (HISTORY_TABLE = dbo.team_stats_history));

SELECT * FROM team_stats FOR SYSTEM_TIME AS OF '2026-10-09T22:03:00Z';
```

**Pros.**
- Zero application code for history. Point-in-time queries are one clause.
- This is the **transaction time** half of bi-temporal modelling done for you, and it is compliance-grade.

**Cons.**
- **DuckDB does not implement it.** Adopting it means adopting a server database, which contradicts the local-first decision we already have consensus on.
- It versions *transaction* time, not *valid* time — and our valid time (when the source's numbers were true) is exactly the thing we care about. SQL Server's own docs warn that "if you load data with a significant delay, transaction time might not be acceptable" — which is precisely our situation.
- History is managed by the engine, so it is less explicit and less portable.

**Verdict: mention it, don't use it.** It is the right pattern for the wrong engine. But it names the concept we should *borrow* — see §8.4.

---

### 4.5 Axis 2 — Wide, long, or hybrid

This is orthogonal to Axis 1 and worth deciding once.

**Wide.** One column per metric (`offensive_rating`, `defensive_home_rating`, …).
- *Pros:* direct, fast, one row per team — the source is already wide. Easy to eyeball.
- *Cons:* schema churn on every new metric; category/view information is baked into column *names*; "top N categories" queries become `UNPIVOT` gymnastics.

**Long (EAV-style with explicit dimensions).** One row per (team, snapshot, section, view, metric).
- *Pros:* schema-stable; new metrics are rows, not migrations; category-generic queries are trivial.
- *Cons:* the number of rows explodes; every query needs a pivot; types get muddied (one `value` column holding ints, decimals and ranks); harder to reason about at the grain level, which Kimball explicitly warns against.

**Hybrid (recommended).** Keep the *fact* wide for the metrics we actually model — points, goals, xG, the ratings — because those are stable and few. Put the long tail (situational and positional categories, of which there may be hundreds) in a **child table** keyed by `(snapshot_id, section, view, category, direction)`.
- *Pros:* stable core, flexible periphery, no giant `UNPIVOT`.
- *Cons:* two tables to validate; cross-section consistency checks span both.

Kimball's "keep to the grain" applies: the child table is a **different grain** and should be declared as such, not smuggled into the fact row.

---

### 4.6 Axis 3 — Comparison

| | Snapshot fact | SCD2 on measures | Snapshot fact + SCD2 dim | System-versioned |
|---|---|---|---|---|
| Audit trail | Perfect | Good | Perfect | Perfect (engine-held) |
| Observation cohort explicit | **Yes** | No | **Yes** | No |
| Handles provider corrections | Yes, visibly | Yes | Yes | Yes |
| Retry-safe by construction | **Yes** (insert-only) | Needs care | Fact yes, dim needs care | Engine-dependent |
| Storage | Fine at our scale | Worst case for us | Best | Fine |
| Point-in-time attr query | Awkward | **Idiomatic** | **Idiomatic** | **One clause** |
| Works in DuckDB | **Yes** | Yes | **Yes** | **No** |
| Matches the field guide | **Yes** | No | Mostly | No |
| Matches Kimball | Yes (state snapshot) | **Yes** (dimension) | **Yes** | n/a |

### 4.7 Recommendation — Decision 1

**Take Option C.** Immutable snapshot fact for measures; a small SCD Type 2 dimension for team attributes; wide fact with a long child table for the situational/positional tail.

Why: it is the only option where each thing is versioned at its own rate, it keeps the guide's two strongest ideas (explicit observation cohort, atomic publication), it stays append-only where mutation would hurt, and it runs on DuckDB today. Option A alone is the correct *minimum* if you want the smallest first version — I'd accept A for v1 and add the dimension at the first rename or promotion. Adopting dbt/SQLMesh later gives us the dimension for free without changing the fact.

**Minimum viable version of this decision:** Option A (snapshot fact, wide), with the `dim_team_scd2` table sketched but not populated.

---

## 5. Decision 2 — Where the ingest layer's boundary sits

### 5.0 Why this matters

Ingestion is where all the irreducibly-bespoke work lives (the anti-bot gate) *and* most of the boilerplate work lives (schema evolution, incremental state, normalisation). Putting the boundary in the wrong place means either hand-maintaining boilerplate forever, or fighting a library to do something only this source needs.

### 5.1 Option A — Hand-roll everything

**What.** Our own `client.py` (requests) + our own loader (DuckDB inserts).

**How.** `curl_cffi` with Chrome TLS impersonation → parse → validate with pydantic/pandera → `INSERT` into DuckDB. State in our own `pipeline_checkpoint` table.

**Pros.**
- Total control over the gate, cookies, backoff and bespoke quirks.
- One dependency fewer; nothing to learn.
- Exactly what the previous attempt started (`client.py` + `scraper.py`, now deleted).

**Cons.**
- We re-implement schema evolution, incremental state, nested-JSON normalisation, and load bookkeeping. That is real, ongoing maintenance.
- Schema drift handling is the part people get wrong, and it is the part a library has already solved.

**Use when:** the source shape is stable and the team is one person who enjoys owning it.

---

### 5.2 Option B — Hand-rolled client + a loading library

**What.** We own extraction; a library owns loading. The natural pick is `dlt`.

**How.** The client yields dicts. `dlt` infers the schema, evolves it as fields appear, normalises nested structures into relational tables, persists incremental state in the destination, and writes to DuckDB.

```python
import dlt
from dataderby.client import fetch_team_stats


@dlt.resource(name="team_stats", write_disposition="merge", primary_key=["snapshot_id", "team_id"])
def team_stats(fingerprint_state=dlt.sources.incremental("observed_at")):
    payload = fetch_team_stats(...)  # our code: gate, cookies, retry
    yield from normalise(payload)  # our code: field mapping, null policy


pipeline = dlt.pipeline("dataderby", destination="duckdb", dataset_name="staging")
pipeline.run(team_stats)
```

What dlt brings, concretely:
- **Schema inference and evolution** — a renamed or added field becomes a schema migration, and `_dlt_version` records the history.
- **Incremental state** — cursor-based, persisted next to the data, so a failed run resumes correctly.
- **Write dispositions** — `append` / `replace` / `merge`, which is exactly the "append vs overwrite-partition" choice from FDE, expressed as configuration.
- **Normalisation** — nested JSON unpacked with keys, which is the staging layer.
- **Load bookkeeping** — `_dlt_loads`, `_dlt_version` for free.
- **Destination portability** — DuckDB locally, MotherDuck/Postgres later, by changing a string.

**Pros.**
- Keeps the bespoke part bespoke and the generic part generic.
- Schema drift stops being an incident and becomes a recorded event.
- Much less code to own; the state machine is tested by someone else.

**Cons.**
- An external dependency, which AGENTS.md says to ask about first.
- Its table naming (`_dlt_*`, normalised child tables) and its schema conventions become part of our warehouse whether we like them or not.
- It has no notion of "did the *source state* change" — that is our fingerprint, and it stays ours.
- Another mental model on top of DuckDB.

**Use when:** the payload is nested, the schema churns, or more sources are coming.

---

### 5.3 Option C — dlt end to end (including extraction)

**What.** Model the source as a `dlt` REST API source with pagination, auth and incremental config.

**How.** `dlt.sources.rest_api` with a `client` config, or a `dlt` verified source.

**Pros.** Least code overall. If the source were a well-behaved REST API this would be the obvious answer.

**Cons.**
- The source is hostile, not well-behaved. The gate is a TLS-fingerprint + cookie problem, not a pagination problem. `dlt`'s HTTP client is not `curl_cffi` with Chrome impersonation, and bolting TLS impersonation in means fighting the abstraction — which removes the reason to use it.
- We would still write the gate logic and hand it to dlt as a custom source, at which point this collapses into Option B with extra indirection.

**Verdict: not for this source.** Revisit if a second, well-behaved source appears.

---

### 5.4 Option D — A scraping framework (Scrapy and friends)

**What.** Scrapy with item pipelines and feed exports.

**Pros.** Mature, handles concurrency, retries, throttling, and item validation well; feed exports give immutable raw files almost for free.

**Cons.** It is a framework for crawling many pages of HTML; we have a handful of JSON endpoints behind a TLS gate. It is a large abstraction for a small problem, and it fights asyncio-based `curl_cffi` less gracefully than it fights its own twisted engine. The re-architecture cost outweighs the benefit at this size.

**Verdict: no.** Worth remembering if the scope grows to thousands of pages.

---

### 5.5 Recommendation — Decision 2

**Take Option B, staged.** Hand-roll the client (unavoidable — the gate is bespoke) and start by writing rows with plain DuckDB SQL through pydantic-validated models. Add `dlt` the moment either (a) the payload's shape churns more than once, or (b) a second source appears. Option A is a fine starting point and dlt is a drop-in *later*, because the boundary — client yields dicts — is the same either way.

I would not take A permanently, and I would not take C at all for this source.

---

## 6. Decision 3 — Where the raw evidence lives

### 6.0 Why this matters

This is the layer that makes the system auditable and the parser fixable. Its only job is: given a bug in the field mapping, reproduce the accepted output without touching the source again. The guide's §3.5 and §4.2 nail the requirement; this decides the mechanism.

Relevant scale, so nobody architects for the wrong problem: one capture is one JSON response of a few KB. A full snapshot is ~9 requests (3 sections × 3 views). A season at ~40–60 observation windows is a few **megabytes**. This is small.

### 6.1 Option A — Local immutable files + a manifest

**What.** Every response is written once to a unique path and never rewritten. A sidecar manifest makes it self-describing.

**How.** The guide's own convention, plus the manifest:

```
data/raw/tournament=4/season=2026-2027/
  observed_at=2026-10-09T22-03-02Z_run=run_0187/
    snapshot.json                  # our normalised record
    manifest.json
    team_statistics__overall.json
    team_statistics__home.json
    ...
```

```json
{
  "capture_id": "cap_0187_team_stats_overall",
  "run_id": "run_0187",
  "snapshot_id": "snap_2026-10-09_4_25662",
  "tournament_id": 4,
  "season_key": "2026-2027",
  "whoscored_stage_id": 25662,
  "section": "team_statistics",
  "view": "overall",
  "whoscored_url": "https://www.whoscored.com/statisticsfeed/1/getteamstatistics?...",
  "captured_at": "2026-10-09T22:03:02Z",
  "http_status": 200,
  "payload_sha256": "…",
  "schema_version": "whoscored-shape-v1",
  "parser_version": "0.1.0"
}
```

Uniqueness comes from the path including `run_id` and the capture time; the same request made twice produces two files, which is correct — two raw attempts are two facts. The *accepted* snapshot is de-duplicated at the model layer, not here.

**Pros.**
- Dead simple, greppable, diffable, works offline, zero infrastructure.
- Naturally replayable — the whole point.
- Path partitioning by tournament/season makes retention policies trivial.

**Cons.**
- No content-addressing: identical payloads are stored twice.
- Disk is local, so "durability" is "whatever you back up".
- Nothing stops a careless `open(path, "w")` from clobbering a capture. Mitigate with write-once logic and a filename that includes the run id.

---

### 6.2 Option B — Git scraping

**What.** A scheduled job scrapes, writes into a git repo, and commits. Simon Willison's pattern. Git becomes the immutable append-only store.

**How.** A GitHub Actions workflow on a cron, running the client, writing the payload, `git commit && git push`. The commit history *is* the change log.

**Why it's compelling here.** Our stated product goal — "know when a value changed and what it changed from" — is literally what `git log -p` gives you, for free, with content-addressing, immutability, deduplication and diffability built in. It also solves the storage and backup problem in one move.

**And the caveat, which is on-point.** Willison hit **exactly our problem**: Cloudflare blocking the GitHub Actions IP range when scraping `doge.gov`, and worked around it with a Tailscale exit node. He also notes GitHub Actions proved unreliable for *precise* scheduling, and moved a crawler to Cloudflare Workers cron instead. Both apply to us: we have a Cloudflare gate, and our scheduling is fixture-driven, not "every N minutes".

**Pros.**
- Immutable, content-addressed, deduplicated, diffable, backed up, portable — all from `git`.
- Human-readable change history with zero extra tooling.
- Free scheduling on Actions; free provenance (which commit, which run).

**Cons.**
- Repo bloat over time (mitigable; at megabytes a season, not for years).
- Git is not a data store: no SQL, no schema, awkward for the derived layers.
- Ties scheduling to a hosted runner whose IPs the source may block, and whose cron is imprecise.
- Committing derived data to git is a well-known anti-pattern; must be raw-only.

**Use when:** the raw layer is small (ours is), change-visibility is the product (it is), and the scheduler can reach the source (ours may not).

---

### 6.3 Option C — Both

Files are the source of truth; git is a mirror of the raw layer only. You get local-first operation and the free diff history, at the cost of two paths to keep straight.

**Cons:** two places storing the same bytes; a mirror can silently lag; more moving parts than a first version needs.

---

### 6.4 Option D — Object storage (S3/R2/GCS)

The production answer: path conventions, lifecycle rules, versioning, cheap. **Cons:** it solves a problem we do not have (durability at scale) at the cost of credentials, a network dependency in the hot loop, and a local-vs-remote split during development. The *path convention* in 6.1 is worth stealing; the infrastructure is not, yet.

### 6.5 Option E — Store payloads in a database column

**Verdict: don't.** It couples raw evidence to the warehouse's lifecycle, makes a parser bug a database migration, and means a rebuild can destroy the evidence. Worth naming only because it is the tempting shortcut.

### 6.6 Recommendation — Decision 3

**Take Option A.** Local immutable files with a manifest, path-partitioned by tournament/season and made unique by `run_id` + capture timestamp, hash-recorded with sha256.

Add **Option C** (a git mirror of `data/raw/`) only if you want the free diff history *and* you accept that scheduling must then live somewhere that can reach the source — which, given the Cloudflare gate, is not the GitHub Actions runner we'd otherwise use. My honest read: the diff-history benefit is real but smaller than it looks, because we are building the "what changed" query into the model layer anyway (§8.3), and a local-first project should not take a hosted-runner dependency for it.

---

## 7. Decision 4 — Orchestration and transformation

### 7.0 Why this matters

Two separate questions that people bundle: **when does work run** (orchestration) and **how are tables produced** (transformation). They have different right answers at different scales.

The specific pressure here is the guide's §4.3: fixture-derived check windows. Matches finish close together; the source publishes late and in batches. Naive "scrape every matchday midnight" either duplicates work or misses updates.

### 7.1 Option A — Plain Python + OS scheduler + DuckDB SQL

**What.** A `python -m dataderby.run` entrypoint; Task Scheduler (Windows) or cron invokes it; transformations are `.sql` files run by DuckDB.

**How.** The scheduler wakes on a cadence; the program asks "does a fixture window close now? has the source state changed?" and either does nothing (a successful no-op, per §6.2 of the guide) or runs the capture→validate→publish sequence:

```python
def run_once(now: datetime) -> RunOutcome:
    for window in due_windows(now):
        probe = fetch_league_table(window)  # cheap
        fp = fingerprint(probe)
        if fp == checkpoint.last_committed(window.scope):
            return RunOutcome.skipped_no_change(window)
        captures = [capture(s) for s in SECTIONS]  # expensive
        candidate = parse(captures)
        validate_or_reject(candidate)  # atomic
        publish(candidate)  # header + rows, one txn
        checkpoint.commit(window.scope, fp)  # only now
    return RunOutcome.accepted(...)
```

**Pros.**
- Zero new dependencies; nothing to learn; the whole control flow is readable in one file.
- The fixture-window logic lives in *our* domain vocabulary, not an orchestrator's.
- Easy to test — `run_once` is a pure-ish function of `now`.

**Cons.**
- Retries, run history, observability and backfills are ours to build.
- No lineage graph or asset-level UI; "what is stale?" is a query you write.
- Crash-and-resume needs our own ledger (which we need anyway, for the checkpoint).

**Use when:** one source, one consumer, and a small team. **That is us.**

---

### 7.2 Option B — Dagster

**What.** Asset-based orchestration. Each table and file is an **asset**; the code that produces it is declared; partitions, schedules/sensors, retries, backfills and lineage come from the framework.

**How.** `@asset` functions with `PartitionsDefinition`; a `sensor` reacts to fixture windows; a backfill is one UI action across a partition range. Crucially, Dagster models **partitions** as first-class, which is exactly the FDE "one task → one partition → overwrite the whole partition" idempotency model.

**Pros.**
- Partitions + backfills + retries + run history + lineage, all built in and all things we would otherwise hand-roll.
- Data-as-code: pushing a change to the parse logic feels like pushing code, which is the guide's "replayable" requirement made operational.
- Python-first, so our bespoke gate fits without fighting the framework.
- Makes "which asset is stale, and why" a first-class question.

**Cons.**
- A real framework to learn and run (a daemon, a UI, a `definitions.py`).
- Overkill for one source; the guide's own advice is to keep domain rules in testable Python/SQL *anyway*, so the framework mostly adds the scheduling shell.
- Adds an abstraction between us and a problem that is currently 40 lines of Python.

**Use when:** a second source, a second consumer, or a backfill that is dangerous to do by hand.

---

### 7.3 Option C — dbt (transformation only)

**What.** SQL models with `ref()`, tests, docs, and `dbt snapshot` for SCD Type 2. Not an orchestrator, but often paired with one.

**Pros.** The de-facto standard for SQL transformation; snapshots give Decision 1's dimension for free; tests and docs are part of the model definitions; a huge body of practice to copy.

**Cons.** Another runtime and a `profiles.yml`; the dbt-duckdb adapter is good but not the first-class path; it brings Jinja-templated SQL as a new dialect; and it does not solve scheduling.

---

### 7.4 Option D — SQLMesh

**What.** A transformation framework that is explicitly *not* dbt, built around a plan/apply model with **fingerprints** and **virtual environments**.

**How.** Every model gets a fingerprint over its logic *and its upstream dependencies*. If the fingerprint exists in an environment, the physical table is reused rather than rebuilt. Changes are classified "breaking" or "non-breaking" and backfilled accordingly. It has an `SCD_TYPE_2` model kind with `valid_from`/`valid_to`, and it detects schema changes at plan time.

**Pros.**
- The plan/apply/backfill model is the most direct expression of "safe to re-run" I have found in a tool.
- Its fingerprint concept is *exactly* the guide's change-detection idea, extended correctly to include logic — fixing gap (c) from §2.2.
- Physical tables are versioned, so you never read a half-rebuilt table.

**Cons.**
- Younger ecosystem than dbt; fewer people to ask.
- A plan/apply mental model to adopt wholesale; it wants to own the model layer.
- Another dependency, for a project whose transformation needs are currently a handful of views.

---

### 7.5 Option E — Airflow / Prefect

Task-centric orchestrators. Airflow is the incumbent, heavy, and its partitions are stringly-typed per-DAG; Prefect is lighter and Pythonic but also task-centric. Both model *tasks*, not *data*, so the FDE partition idempotency has to be built by hand. Worth naming to dismiss: for a single-source local pipeline they are more framework than problem.

---

### 7.6 Comparison

| | Plain Python + DuckDB | Dagster | dbt | SQLMesh | Airflow/Prefect |
|---|---|---|---|---|---|
| Scheduling | OS cron | Schedules + sensors | — (needs a runner) | Built-in | Schedules |
| Partitions/backfills | Hand-rolled | **First-class** | Incremental models | **Plan/apply** | Catchup |
| Asset lineage | — | **Yes** | Partial | Yes | Partial |
| Retries/history | Hand-rolled | **Yes** | Partial | Yes | Yes |
| SCD2 built in | No (we write it) | No | **`dbt snapshot`** | **`SCD_TYPE_2` kind** | No |
| Change fingerprints | Ours | No | No | **Yes (incl. logic)** | No |
| Idempotency model | Ours | Partition overwrite | Table rebuild | Snapshot reuse | Task retry |
| New deps | **0** | 1 framework | 1 + adapter | 1 | 1 framework |
| Fits one source | **Yes** | Overkill | Ok | Overkill | Overkill |

### 7.7 Recommendation — Decision 4

**Take Option A for the first version.** A scheduled `run_once(now)` that owns the fixture-window logic, a checkpoint table, SQL views in DuckDB for the model layer, and hand-written SCD2 in SQL if and when Decision 1's dimension is needed.

Then adopt **in this order**, triggered by a need rather than a preference:
1. **SQLMesh** or **dbt** when the model layer grows past a handful of views or when SCD2/backfills become routine — SQLMesh if you want fingerprint-driven rebuilds, dbt if you want the larger ecosystem. This is the highest-value adoption because it replaces the *most* hand-rolled code.
2. **Dagster** when there is a second source, a second consumer, or a backfill you would not dare run by hand. Its partitions map 1:1 onto our snapshots, so it is a natural fit when it is needed.

I would not adopt Dagster *and* a transformation framework simultaneously — that is two new mental models for one source.

---

## 8. Cross-cutting decisions

These fold into whichever options you pick.

### 8.1 Identity and keys

- **Team:** the source's numeric id. Never the display name (localisation, sponsorship, punctuation).
- **Competition + season:** a composite. Never the calendar year — La Liga 2026/27 spans two. Keep the source's `stage_id` as a nullable attribute, because statistics are keyed by stage but a season may have several.
- **Snapshot:** generate our own `snapshot_id`. Do **not** derive it from a date — two valid observations can occur on the same day.
- **Surrogate keys:** only for the SCD2 dimension (`team_sk`), where the natural key is not unique across versions.

### 8.2 Validation

Layered, and matched to the artefact:

| Layer | Tool | Checks |
|---|---|---|
| Raw envelope | `pydantic` | JSON parses; required fields present with expected types; the anti-bot gate is detected (a 200 carrying HTML is a *failure*, not data) |
| Typed table | `pandera` | Column types, nullability, uniqueness of `(snapshot_id, team_id)`, ranges, cross-section consistency, contested-value warnings |
| Cross-record | our own + DuckDB SQL | Expected team count for the competition; all sections cover the same team set; freshness vs the fixture window |

`pydantic` for records, `pandera` for DataFrames, Great Expectations only if this grows into a suite someone else operates. The guide's hard-failure/warning split is right; encode it as two lists, not one boolean.

### 8.3 Change detection — the two fingerprints

The guide has one; we need two.

**`source_fingerprint`** — canonicalised digest of the *observed source state*. Sorted by stable team id, key order normalised, volatile fields (request time, session cookies, HTML noise) excluded. Decides: *append a new observation, or skip.*

**`logic_fingerprint`** — a version stamp over parsing code + field mapping + schema version. Decides: *do derived tables need rebuilding?* This is gap (c). Without it, fixing a parser leaves stale derived data with no signal that it is stale.

The guarantee that makes skipping safe is asymmetric and must be **verified against the source, not assumed**:

- *table changed → details ready*: plausible, use as a positive trigger.
- *table unchanged → details unchanged*: **unproven**. Until proven, either reconcile periodically or always fetch the details. The cost of a false negative (a lost observation) is permanent; the cost of a false positive (a wasted fetch) is one request.

### 8.4 The time model

Bi-temporal, expressed as columns rather than as a database feature:

| Column | Question | Our value |
|---|---|---|
| `fixture_end_expected_at` | when did we expect readiness? | from the fixturedownload.com calendar |
| `source_published_at` | when does the provider say? | **unavailable** — leave null, don't invent |
| `observed_at` | when did we see this payload? | our probe time, UTC |
| `captured_at` | when was this exact byte-payload written? | per capture |
| `accepted_at` | when was the complete snapshot validated and published? | per snapshot |
| `valid_from` / `valid_to` | (dimension only) when was this attribute true? | SCD2 window |

The guide is right that these must not collapse into one `date`. And `source_published_at` being genuinely unavailable is itself a finding worth recording, because it means "the source was late" can only ever be inferred from `observed_at`.

### 8.5 Layering

```
data/raw/           immutable captured bytes + manifest        (append-only)
duckdb: staging     parsed, typed, normalised, rebuildable     (overwrite by run)
duckdb: model       snapshot header, fact, dim_team_scd2       (accepted only)
duckdb: marts       latest_state, history, delta, freshness    (recomputed views)
```

Raw is never the input to a *query*; marts are never the only copy of anything.

### 8.6 Idempotency

Three identities, per the guide and dlt alike:

- `run_id` — one execution attempt.
- `capture_id` — one exact byte-payload.
- `snapshot_id` — one accepted observation.

Uniqueness rule for acceptance: a candidate whose `source_fingerprint` already exists as *accepted* for the same `(tournament, season, stage)` is a duplicate and is rejected, not published. Raw may have three captures for that state; the model has one snapshot. This is the "run ≠ snapshot" separation, and it is what makes retries safe.

### 8.7 Observability, in the literature's vocabulary

Monte Carlo's five pillars map almost 1:1 onto what we already want, and using the standard names costs nothing:

- **freshness** — expected window vs `observed_at` (the guide's `source_freshness`).
- **volume** — teams captured vs teams expected (the guide's completeness check).
- **schema** — field additions/removals/type changes.
- **distribution** — plausibility (goals within bounds, ratings in range).
- **lineage** — capture → staging → snapshot, and which parser version produced it.

Track these as rows in a small `pipeline_run` / `pipeline_checkpoint` ledger rather than as log lines, so "when did this table last get a valid observation?" is a query.

---

## 9. The recommendation, assembled

If you take my recommendation on all four:

```
              ┌──────────────────────────────────────────────┐
  FIXTURES ──▶│  run_once(now)   (plain Python, OS scheduler) │
              │   1. build/close fixture windows              │
              │   2. cheap probe → source_fingerprint         │
              │   3. skip?  → record a successful no-op        │
              │   4. else fetch sections (gate-aware client)   │
              └───────────────┬──────────────────────────────┘
                              ▼
     data/raw/tournament=4/season=2026-2027/…/  ← immutable JSON + manifest
                              │  (never mutated, never the only copy)
                              ▼
           staging:  pydantic → pandera → typed rows   (rebuildable)
                              ▼
        validate complete cohort ──reject──▶ keep evidence, mark rejected
                              │ accept
                              ▼
        ┌─────────────── one transaction ───────────────┐
        │ competition_snapshot (header, cohort)         │
        │ fact_team_snapshot  (wide measures, append)   │
        │ fact_team_section   (long tail, child grain)  │
        │ dim_team_scd2       (attributes, valid_from/to)│
        └───────────────────────────────────────────────┘
                              ▼
        checkpoint.commit(snapshot_id, source_fingerprint)   ← only now
                              ▼
        marts: latest_team_state · team_snapshot_history ·
               team_snapshot_delta · snapshot_completeness ·
               source_freshness
```

One-sentence summary: **immutable raw → validated complete cohorts → append-only snapshot fact plus a Type 2 team dimension, in DuckDB, driven by a hand-written fixture-window loop, with two fingerprints and a checkpoint that advances only on acceptance.**

### 9.1 Minimum viable, then grow

| Stage | Build | Trigger to move on |
|---|---|---|
| **v1** | Client + gate; raw files + manifest; pydantic+pandera; snapshot fact (wide); `latest_team_state` view; checkpoint; `run_once` on cron | it works end-to-end twice, correctly detecting "no change" the second time |
| **v2** | `dim_team_scd2`; `team_snapshot_history`; `team_snapshot_delta` with its caveats documented; freshness/completeness views | first rename/promotion, or first correction observed |
| **v3** | `logic_fingerprint` + rebuild path; long child table for the situational/positional tail | parser changed once, or the tail grew past comfort |
| **v4** | SQLMesh or dbt over the model layer; dlt for loading | model count > ~10, or a second source |
| **v5** | Dagster | a second source *and* a dangerous backfill |

The guide's own "first trustworthy milestone" is the gate for v1, and I agree with it: *one competition scraped twice, the second run correctly deciding "no new state", a failed detail capture retried without losing the update, and every accepted snapshot complete under one `snapshot_id`.*

---

## 10. Proposed repo shape

```
dataderby/
  pyproject.toml                # uv; deps: curl-cffi, pydantic, pandera, duckdb
  AGENTS.md
  docs/
    football_competition_data_engineering_field_guide.docx
    whoscored-api.md            # the source contract the guide keeps deferring to
    architecture-decisions.md   # this document, once promoted into the repo
  src/dataderby/
    __init__.py
    source.py                   # client: gate, cookies, backoff, fingerprint
    contract.py                 # pydantic models for the raw envelope
    schema.py                   # pandera schemas for the typed tables
    ingest.py                   # capture → raw files + manifest
    parse.py                    # raw → typed records
    validate.py                 # completeness / consistency / plausibility
    publish.py                  # atomic snapshot transaction
    checkpoint.py               # last_seen vs last_committed
    windows.py                  # fixture windows
    run.py                      # run_once(now) — the entrypoint
  sql/
    001_schema.sql
    002_scd2_merge.sql
    views/latest_team_state.sql
    views/team_snapshot_history.sql
    views/team_snapshot_delta.sql
    views/snapshot_completeness.sql
  data/raw/…                    # immutable captures (git-ignored)
  tests/
```

This restores the `src/dataderby` package deleted earlier, but with the ingest/parse/validate/publish boundaries made explicit — which is the shape the guide's §5.1 ten-step run suggests, and which is the same shape every source above converges on.

---

## 11. Open questions to verify against the source

These cannot be answered from the literature; they need a probe. They gate §8.3 in particular.

1. **Is there a cheap league-table endpoint** that can act as the probe/gate the guide describes, or is the smallest request already the detail feed?
2. **Does an unchanged table imply unchanged details?** Measure it: hold the table fingerprint fixed across a fixture and see whether any detail field moves. Until measured, treat skipping as unsafe.
3. **Does the source expose any update/publish timestamp, ETag, or revision id?** If yes, the fingerprint problem gets much easier.
4. **Are values ever corrected retroactively?** Compare an accepted snapshot against a re-fetch of the same stage days later.
5. **Is `teamId` stable across seasons and competitions?**
6. **How long after a final whistle does the source publish?** This sets the grace period and the retry cadence.
7. **What does the anti-bot gate look like now** — TLS fingerprint only, or cookie/session-bound? Determines whether the client can be stateless.
8. **What is the real metric count across sections and views?** Decides wide vs long for the tail (§4.5).

---

## 12. Sources

**Canonical modelling**
- Kimball — [Declaring the Grain](https://www.kimballgroup.com/2003/03/declaring-the-grain) · [Grain](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/grain) · [Type 2: Add New Row](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-2/) · [Periodic Snapshot Fact Tables](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/periodic-snapshot-fact-table) · [Accumulating Snapshot Fact Tables](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/accumulating-snapshot-fact-table)

**Modern practice**
- Maxime Beauchemin — [Functional Data Engineering](https://maximebeauchemin.medium.com/functional-data-engineering-a-modern-paradigm-for-batch-data-processing-2327ec32c42a) · [How the Modern Data Stack Reshapes Data Engineering](https://preset.io/blog/reshaping-data-engineering)
- Databricks — [What is Medallion Architecture?](https://www.databricks.com/blog/what-is-medallion-architecture) · Microsoft Learn — [Medallion lakehouse](https://learn.microsoft.com/en-us/azure/databricks/lakehouse/medallion)
- dbt Labs — [Track data changes with dbt snapshots](https://www.getdbt.com/blog/track-data-changes-with-dbt-snapshots) · [Snapshots docs](https://docs.getdbt.com/docs/build/snapshots)
- SQLMesh — [Environments (fingerprints)](https://sqlmesh.readthedocs.io/en/stable/concepts/environments) · [Model kinds (`SCD_TYPE_2`)](https://sqlmesh.readthedocs.io/en/stable/concepts/models/model_kinds)
- dlt — [Incremental loading](https://dlthub.com/docs/general-usage/incremental-loading) · [Destination tables & lineage](https://dlthub.com/docs/general-usage/destination-tables)
- Dagster — [What is a Software-defined Asset](https://dagster.io/glossary/software-defined-assets) · [Understanding Partitions in Pipelines](https://dagster.io/blog/partitioned-data-pipelines)
- Simon Willison — [Git scraping](https://simonwillison.net/2020/Oct/9/git-scraping) · [git-scraping tag](https://simonwillison.net/tags/git-scraping)
- Jordan Tigani / MotherDuck — [Big Data is Dead](https://motherduck.com/blog/big-data-is-dead)
- Chad Sanderson — [The Shift Left Data Manifesto](https://dataproducts.substack.com/p/the-shift-left-data-manifesto)
- Barr Moses / Monte Carlo — [What is Data Observability? 5 Key Pillars](https://montecarlodata.com/blog-what-is-data-observability)

**Temporal and streaming**
- Tyler Akidau — [Streaming 101: The world beyond batch](https://www.oreilly.com/radar/the-world-beyond-batch-streaming-101)
- Microsoft Learn — [Temporal tables overview](https://learn.microsoft.com/en-us/sql/relational-databases/tables/temporal/overview) · [Temporal table usage scenarios](https://learn.microsoft.com/en-us/sql/relational-databases/tables/temporal/usage-scenarios)

**Validation**
- pandera vs Great Expectations — [endjin comparison](https://endjin.com/blog/a-look-into-pandera-and-great-expectations-for-data-validation)
