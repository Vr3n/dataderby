# dataderby — v1 implementation plan

**Status:** proposal for approval · **Date:** 19 October 2026
**Scope:** one source (WhoScored team season statistics), one competition season, every
observed state retained.
**Owner:** Viren · **Reviewers:** —

---

## 0. How to read this

This plan is written to be executed without further design work. It separates three
kinds of statement, and never mixes them:

- **MEASURED** — read out of the nine real payloads captured at tag `recon-evidence`
  (`f5c1e35`, `recon/caps/`). Reproducible with a command in §2.3.
- **OBSERVED** — stated by a person or a document, not verified by us.
- **INFERRED / UNKNOWN** — a guess or a gap. Every unknown has an experiment that
  closes it (§14) and nothing in the pipeline depends on an unclosed one.

Where the project's own documents disagree, §3 resolves the disagreement and says
which document loses. A plan that averages contradictions is not a plan.

**The one sentence version.** Nine HTTP responses are one observation; one observation
is one immutable row-set; a re-run that sees the same bytes writes nothing, and a re-run
that sees different bytes writes a new row-set next to the old one — never over it.

---

## 1. What we are building, and what we are not

### 1.1 The thing being observed

The source publishes **cumulative season-to-date team statistics**, not match events.
One team, one competition stage, one instant. The value of the dataset is the ability to
ask *what the table said on a given day* and *what moved between two days*.

### 1.2 v1 delivers

1. A **raw archive**: every byte the source ever returned, addressable by run — the
   stage page, the three standings views and the nine feed payloads.
2. An **immutable snapshot fact**: one row per team per accepted observation, 60
   measures, never updated.
3. A **standings fact at the same grain**: one row per `(snapshot_id, team_id)`, three
   splits, captured from the page in the same transaction.
4. A **publish contract**: 21 executable assertions that can refuse a cohort.
5. **Views**: latest team state, latest team with standings, standings history, change
   since the previous accepted state, pipeline freshness.
6. A **measurement harness** that answers the six remaining source questions, so the
   next optimisation is evidence-driven rather than hopeful.

### 1.3 v1 explicitly does not deliver

| Not in v1 | Why | Trigger that would justify it |
|---|---|---|
| xG panel (`xg-teamstats`) | Adds 3 captures and 5 unresolved reconciliation questions; not needed to prove the loop | The loop is green and xG is requested by a consumer (M7) |
| `dim_team` / SCD2 | No rename, promotion or cross-tournament merge has been observed; Option A carries identity as plain columns so the dimension is later a *view change* | First real rename, promotion, or a second source claiming the same team |
| Match-level facts | The source is cumulative; match rows cannot be recovered by subtraction when rates are involved (§8.3) | A match-level source exists |
| Multi-source crosswalk | One source; a mapping table with one side empty is dead weight | Second source added |
| dlt / Dagster / dbt / API / dashboard | All are schedulers or presentation over a pipeline that does not exist yet | Volume or team size demands it (explicit non-goal for v1) |
| The probe skip rule | **UNKNOWN #2** is unmeasured, and it is the only thing standing between "cheap" and "silently stale" | Experiment E2 passes (§14) |

---

## 2. Evidence base

### 2.1 What is measured

| Claim | Value | How |
|---|---|---|
| Captures | 9 (3 sections × 3 views) | `recon/caps/` at `f5c1e35` |
| Teams per capture | 20, identical set in all 9 | run 2.3 |
| Envelope shape | flat `{teamTableStats:[20 rows], paging, statColumns}` | 2.3 |
| `statColumns` per view | Summary 8, Defensive 6, Offensive 5 | 2.3 |
| Distinct measure columns | **60** | §5.2 arithmetic |
| Row-level fields kept | `rating` (3 cols), `ranking` (9 cols) | §5.2 |
| Additive measures (`home+away=overall`) | `apps`, `goal`, `yellowCard`, `redCard` — 0 mismatches | 2.3 |
| Non-additive measures | every `*PerGame`, `possession`, `passSuccess`, `aerialWonPerGame` — 20/20 mismatch | 2.3 |
| `apps` identical across the three sections | yes, 3/3 views | 2.3 |
| `rating` identical across sections | yes, per view | 2.3 |
| `shotsPerGame` identical between Summary and Offensive | yes | 2.3 |
| `ranking` | distinct per (section, view); dense 1..20 in every capture | 2.3 |
| Nulls | none, anywhere, except `seasonName` (always null) | 2.3 |
| `seasonId` in payload | always `0` — unusable | 2.3 |
| `tournamentId` in payload | always `4` | 2.3 |
| `isOpta` | `true` on every row | 2.3 |
| Precision | the feed carries full double precision (`21.428571428571427`); rendering is a separate artefact | 2.3 |
| Season identity | only from the page URL `/seasons/11213/stages/25662/` | `whoscored-api.md` L345 |
| Probe candidate | `summaryteam/all` — one request, byte-identical to the Summary/Overall leg | 2.3 + prior recon |
| Standings shape | 10 columns per split (`P W D L GF GA GD Pts Form`), 20 rows per split | EPL 25544, `standings-25544.json` |
| Standings key | `tr[data-team-id]`; same numeric ids as the feed (Man City 167, Brighton 211) | same |
| Standings splits | `Overall`, `Home`, `Away` are client-side re-renders; no network request | same |
| Standings consistency | `W+D+L=P`, `Pts=3W+D`, `GD=GF−GA`, ranks `1..N`, `home+away=overall` | 20/20 teams, 0 mismatches |
| `Form` | rolling last six `w/d/l`; `len == min(P, 6)` | same |
| Standings on knockout | no table (`has_league_table = false`) | stage 24797 |
| Source timestamp | none: no `ETag`, no page time; `Last-Modified` is response time | `whoscored-cadence.md` |

### 2.2 What is assumed, and why it is safe to assume

| Assumption | Basis | Blast radius if wrong |
|---|---|---|
| `team_id` is stable within one stage | The feed keys rows by it and it does not change across 9 captures | A rename splits history; detected by A6/A7, repaired by a manual alias map |
| The 9 responses describe one coherent state | The sweep is ~10 s and the source is a read-only table | A5/A6 retry; the span is recorded and bounded (A14) |
| A missing key means "not published", never zero | **MEASURED** nulls are absent only because every field was present; the parser writes NULL, never 0 | A consumer summing NULLs gets NULL, which is the honest answer |

### 2.3 Reproduce the measurements

```powershell
# nine captures out of the evidence tag
$d = "$env:TEMP\opencode\caps"; New-Item -ItemType Directory -Force $d | Out-Null
foreach ($f in 'all__Overall','all__Home','all__Away',
               'defensive__Overall','defensive__Home','defensive__Away',
               'offensive__Overall','offensive__Home','offensive__Away') {
  git show "f5c1e35:recon/caps/$f.json" | Set-Content -NoNewline -Encoding utf8 "$d\$f.json"
}
uv run --no-project python "$env:TEMP\opencode\measure_caps.py"
```

The script is retained as `tests/tools/measure_caps.py` in M1. Any number in this plan
that a reader cannot reproduce from that script is a defect in the plan.

---

## 3. Document conflicts, resolved

The nine documents do not agree. These are the resolutions; the losing document is named
so nobody re-litigates it in review.

| # | Conflict | Resolution | Losing document |
|---|---|---|---|
| R1 | `statsAccumulationType=0` is "Total" (`whoscored-api.md`) vs "per game" (scrape deck) | Never depend on it. Send `0`, record it on every capture, never interpret it. The response mixes totals (`goal`) and rates (`shotsPerGame`) in *the same row*, so no single parameter can describe it. | both are wrong to assert a meaning |
| R2 | "12 requests return the five tables" vs 4 categories × 3 views | The unit of a capture is one `(category, subcategory, venue)` request returning 20 rows. v1 issues 9 of them; the 4th category (xG) is deferred. "Five panels / 100 rows" describes the **rendered page**, not the feed. | scrape deck §"12 requests" |
| R3 | DuckDB "parses FOREIGN KEY but does not enforce it" (both decks) | **MEASURED wrong for this version**: FK *is* enforced on insert. The real gaps are no `ON DELETE CASCADE` and no self-referencing FK inserts. v1 keeps the fact→header FK **and** an anti-join assertion (A16), and declares `parent_snapshot_id` as a plain column. | `option-c-model-slides.html` P05/P18 |
| R4 | "Take Option C" vs "ship Option A" | v1 is Option A. Option C's own deck already accepts the fallback ("Ship the snapshot fact alone in v1"). Identity lives as plain columns on the fact. | `architecture-decisions.md` §4 recommendation |
| R5 | `snapshot_id` is a ULID vs a derived content hash | **ULID + `UNIQUE (parent, content)`**, on measured evidence. Idempotency is the transaction; a derived id reproduces only on an identical replay and does not survive a backfill. Reports pin `(stage, observed_at)`, not the id (§4.4, `experiments/id-scheme/`). | earlier schema draft; superseded again by the experiment |
| R6 | `observed_at` on the header is "when the probe saw the state" vs the sidebar/dt in the fact | It is **our** observation clock, not the source's — the source publishes no timestamp. Define it as the minimum `captured_at` of the page and the 9 feed captures, record the span, and reject spans > 180 s (A14). | field guide §5.2's implicit "source time" |
| R7 | `isOpta` used as evidence of a licensing violation | It is **provenance**, not a verdict. It belongs in the record and in the licence decision (§15), not in a failure path. | nothing to overrule; recorded |
| R8 | `pandera` / `dlt` / `Dagster` proposed as dependencies | None enter v1. Validation is Pydantic for the envelope plus SQL assertions for tables. There is no DataFrame in this pipeline. | `architecture-decisions.md` §10 |
| R9 | `ttournamentName` / `teamName` as identity | Neither. Identity is `(tournament_id, whoscored_stage_id, team_id)`; names are labels and never joined on. | several sketches |
| R10 | "Measure the skip rule later" vs "v1 must be cheap" | v1 is cheap by *dedupe on publish*, which is provably safe, not by *skipping fetches*, which is unproven. §4.5 names the difference explicitly. | `dataderby — Pipeline Architecture.pptx` slide 6 |

---

## 4. Decisions

Each decision records what it rules out. A decision that rules nothing out is a
preference, not a decision.

### 4.1 Grain and identity

- **`competition_snapshot`** — one row per accepted observation of one
  `(tournament_id, whoscored_season_id, whoscored_stage_id)`.
- **`fact_team_snapshot`** — one row per `(snapshot_id, team_id)`.
- **`fact_standings_snapshot`** — one row per `(snapshot_id, team_id)`, three splits
  in the same row. Same snapshot, same grain, separate fact: the 60 measures come
  from JSON, the table comes from page HTML, and a knockout stage has no table.
- Identity is the **source's own ids**. `season_key` is our label and never appears in a
  key, a join condition, or a dedupe rule.
- `team_name` is stored as observed. It is a label. Nothing joins on it — the
  standings join uses `tr[data-team-id]`, which is the feed's `teamId`.

*Ruled out:* keying on `season_key` (a typo would silently relabel a whole cohort);
keying on `tournamentName` (a cosmetic change would split a season).

### 4.2 Two clocks, and why they are both ours

The source has no clock. So:

| Clock | Meaning | Set from |
|---|---|---|
| `observed_at` | when we began reading this state | `min(captured_at)` over the page capture and the 9 feed captures |
| `accepted_at` | when the cohort became queryable | commit time |

`observed_at` is an **interval**, not an instant. The header stores
`capture_span_seconds = max(captured_at) − min(captured_at)` so a reader can see how
wide that interval was. The span now covers the page load, the three standings
toggles and the nine feed calls. A span over 180 s is retried (A14): a sweep that
slow is no longer a plausible single state.

*Ruled out:* pretending the source has an event time; using `accepted_at` to order
history (a backfill would reorder the past).

### 4.3 The rejected join, and the one we write instead

The single most common bug in this family of models is a latest-state query that takes
the max time per **fact** row:

```sql
-- WRONG: a team missing from the newest snapshot quietly reports its old row
select * from fact f
where f.observed_at = (select max(observed_at) from fact where team_id = f.team_id);
```

The correct shape picks the **snapshot** first, then joins:

```sql
select f.*
from fact_team_snapshot f
join (
    select snapshot_id
    from competition_snapshot
    where tournament_id = $1 and whoscored_stage_id = $2
    order by observed_at desc, snapshot_id desc
    limit 1
) s using (snapshot_id);
```

This is `v_latest_team_state` (§8.1) and it is covered by a test that deletes one team
from the newest snapshot and asserts the team does **not** reappear.

### 4.4 Snapshot identity: generated ULID, deduped on the edge

```
snapshot_id = ULID()                       # 26 chars, Crockford base32, ms-sortable
parent      = last accepted snapshot_id for this stage, or "genesis"
UNIQUE (parent_snapshot_id, content_fingerprint)
UNIQUE (tournament_id, whoscored_season_id, whoscored_stage_id, observed_at)
```

**This reverses the earlier decision (R5), on evidence.** The comparison lives in
`experiments/id-scheme/`: 24 cases, 3 implementations, 500 publishes, a real process
kill, a contending writer, and a rebuild with one backfilled observation. Raw results
are `results/summary.md`, `results/final.json`, `results/backfill.json`; the narrative
deck is `docs/id-scheme-report.html`.

What the experiment established:

1. **Idempotency is the transaction.** Both schemes pass all eight retry/crash cases.
   Header, fact rows and checkpoint commit together; a retry sees all of them or none.
2. **A derived id reproduces only on an *identical* replay.** Insert one missed
   observation in the middle and 5 of 5 downstream ids change, because every child
   hashes its parent's id. The case the derived id was meant to protect — a corrected
   history — is the case where it fails.
3. **Pinning by `(stage, observed_at)` is stable in both schemes**: 20/20 rows after an
   exact rebuild and 20/20 after a backfill. Pinning by `snapshot_id` returns 0 rows in
   both schemes after a backfill.
4. **A NULL root silently duplicates.** The same ULID + `UNIQUE(parent, content)` with a
   NULL parent for the first observation produced **2 rows** for one observation. The
   sentinel is mandatory, not stylistic.
5. The ULID costs little and the cost is measured: **+6.2% storage** at 300 snapshots,
   and a slower median insert in five of six runs (2–35%, a spread wider than the gap
   itself), with **−11 bytes per id**. Timing is not the deciding factor.

| Scenario | ULID + unique edge | derived id |
|---|---|---|
| First observation | insert (`parent = genesis`) | insert (`parent = genesis`) |
| Same content, previous run succeeded | `no_change` | `no_change` |
| Crash **before** COMMIT | rolled back; retry inserts once | same |
| Crash **after** COMMIT | checkpoint advanced atomically; retry `no_change` | same |
| Revert A → B → A | recorded (content ≠ last committed) | recorded (`parent` differs) |
| Checkpoint lost or restored stale | deduped by the unique edge | deduped by the primary key |
| Exact rebuild from raw | new ids; the id is not an address | identical ids |
| Backfill one observation | new ids after the insertion point | **new ids after the insertion point** |
| Report pinned to `(stage, observed_at)` | resolves | resolves |

**Limits, all load-bearing:**

1. `snapshot_id` is **not** reproducible. A rebuild is content-equivalent, not
   id-equivalent. Nothing outside the warehouse may store it.
2. The report address is `(tournament_id, whoscored_season_id, whoscored_stage_id,
   observed_at)`. `observed_at` must therefore be unique per stage; it is the minimum
   `captured_at` across the nine raw files, so it is reproducible from the archive.
3. `accepted_at` records when the cohort became queryable, is **not** reproducible, and
   never chooses latest or orders history; never pin a report to it.
4. The **single-writer lock is still required**: one checkpoint, one writer.
5. `content_fingerprint` is **not** UNIQUE on its own. The same content at a different
   parent is a new row, and collapsing it would erase a revert.

### 4.5 Two different "nothing changed" — only one of them is safe

This distinction is the heart of the plan and is missing from every document so far.

| | **Fetch gate** (probe) | **Publish gate** (content) |
|---|---|---|
| Question | can I skip 8 of 9 requests? | is this state already published? |
| Input | `summaryteam/all` only | all 9 payloads |
| Safe? | **No** — UNKNOWN #2 | **Yes, unconditionally** |
| v1 behaviour | recorded, never acted on (`PROBE_SKIP=0`) | always acted on |
| What enables it | Experiment E2 passes | nothing |

v1 therefore has a cheap path that is *safe*: the second run of an unchanged table still
costs 9 requests, but costs **zero writes**, and the freshness view can prove it.

The probe is still useful as a **positive trigger**: a change in `summaryteam/all` proves
something changed, so a probe-only schedule can *schedule* a full sweep. It can never
prove the absence of change. That is a one-way valve, and the plan uses it that way.

### 4.6 One writer

DuckDB is a single-process database. **MEASURED** (stack deck, to be re-verified in M4):
a second writer fails with `Could not set lock on file`.

- Many fetchers are fine; one loader.
- v1 runs one process: `dataderby run` acquires `data/state/pipeline.lock` (PID +
  timestamp + host) before touching the DB and releases it after COMMIT.
- A stale lock (PID dead **and** older than 15 min) is broken with a WARN log line.

### 4.7 Raw is the system of record

The database can be rebuilt. The source cannot:

- The site is not replayable: matchday values change in place, and yesterday's table is
  gone.
- Every payload is written **before** parsing, with `O_CREAT|O_EXCL` semantics (write to
  `.tmp`, `fsync`, then rename only if the destination does not exist).
- A sidecar `.meta.json` records URL, status, response headers (`content-type`), byte
  count, SHA-256, capture time, client version, impersonation profile.
- `data/raw` is local-only and never redistributed (§15).

### 4.8 One fact table per source

The fact is **WhoScored-shaped**. It is not a normalised cross-source model. If a second
source arrives, it gets its own fact table joined on `(team_key, snapshot_key)` — the
shape is already in the header. What v1 must do is not *preclude* that: hence the
source ids and the source page URL on the header.

### 4.9 Fail loud, fail legible

Every failure maps to exactly one of three actions, declared in SQL (`sql/002_assertions.sql`):

- **BLOCK** — refuse the cohort, keep raw, exit non-zero, do not advance the checkpoint.
- **RETRY** — the signature of a mid-publish source; try again after a bounded backoff,
  then BLOCK.
- **WARN** — record and continue; a human looks at it.

"Ambiguous" is not an action.

---

## 5. Source contract

### 5.1 The request

```
GET https://www.whoscored.com/statisticsfeed/1/getteamstatistics
    ?stageId=25662
    &category=summaryteam          # summaryteam | defensive | offensive | xg-teamstats
    &subcategory=all               # all | home | away
```

Nine v1 combinations: `category ∈ {summaryteam, defensive, offensive}` ×
`subcategory ∈ {all, home, away}`.

Response: `Content-Type: text/html` with a UTF-8 BOM, body is JSON. Gate trips return
HTTP 200 with ~770 bytes of HTML. Detection is by **structure**, never by size:

1. strip BOM, decode UTF-8, `json.loads`;
2. require top-level keys `teamTableStats`, `paging`, `statColumns`;
3. require `statColumns` to equal the expected list for that `(category, subcategory)`;
4. only then treat it as data.

A `403` is retried with backoff. A second consecutive gate response stops the run.

### 5.2 The 60 columns, derived

Per view the source returns 19 `statColumns` instances; row-level `rating` and `ranking`
sit outside `statColumns`.

| Component | Instances | Stored as | Rule |
|---|---|---|---|
| Summary `statColumns` (8) | 9 | 6 owned + `apps` + `shotsPerGame` | `apps`/`shotsPerGame` deduped |
| Defensive `statColumns` (6) | 9 | 5 owned + `apps` | `apps` deduped |
| Offensive `statColumns` (5) | 9 | 3 owned + `apps` + `shotsPerGame` | both deduped |
| `rating` (row field) | 9 | 3 | section-invariant, view-specific |
| `ranking` (row field) | 9 | 9 | distinct per (section, view) |

Arithmetic: `57` statColumn instances `− 9 (apps) − 6 (shotsPerGame) + 3 (apps) + 3
(shotsPerGame) + 3 (rating) + 9 (ranking) = 60`.

**Ownership** — the section that supplies a shared metric, and the assertion that the
others agree:

| Metric | Owner | Agreement rule |
|---|---|---|
| `apps` | Summary | A6: identical in Defensive and Offensive |
| `shotsPerGame` | Summary | A6: identical in Offensive |
| `rating` | Summary | A6: identical in Defensive and Offensive |
| `ranking` | each (section, view) | A7: dense 1..N |

There is exactly one owner per column. Nothing is "taken from whichever section arrived
first" — that is how two sources of the same number quietly diverge.

### 5.3 Types

| Source type | Stored as | Reason |
|---|---|---|
| `teamId`, `apps`, `ranking`, ids | `INTEGER` | integral; validated on parse |
| `goal`, `yellowCard`, `redCard` | `DOUBLE` | **MEASURED**: arrives as `31.0`, not `31` |
| every rate, ratio, rating | `DOUBLE` | full precision preserved; never rounded |
| `teamName`, `tournamentName`, urls | `VARCHAR` | labels |

### 5.4 Fields deliberately discarded

`name` (an alias of `teamName`; if they ever diverge, A15 flags it), `teamRegionName`,
`regionCode`, `tournamentRegion*`, `paging` (constant zeros), `seasonId` (always 0),
`seasonName` (always null). They are still in the raw file, so nothing is lost.

### 5.5 The standings contract

The league table is page HTML, not a feed. It is captured in the same snapshot as a
companion fact, one row per `(snapshot_id, team_id)`, with three splits in that row.

| Field | Type | Rule |
|---|---|---|
| `team_id` | `INTEGER` | `tr[data-team-id]`; must equal the feed's `team_id` |
| `team_name` | `VARCHAR` | `a.team-link`; label only |
| `rank_{split}` | `INTEGER` | `<span>` in the first cell; `1..N` permutation per split |
| `{played,won,drawn,lost}_{split}` | `INTEGER` | `W+D+L=P` |
| `{goals_for,goals_against,goal_difference}_{split}` | `INTEGER` | `GD=GF−GA` |
| `points_{split}` | `INTEGER` | `3W+D` |
| `form_{split}` | `VARCHAR` | rolling last six `w/d/l`; `len == min(P, 6)`, or NULL only when `P = 0` |

`split` is `overall`, `home`, `away`. A stage with `has_league_table = false` publishes
zero standings rows; that is not a null measure. The fingerprint covers all three
splits, so a rank change alone is a new snapshot.

---

## 6. The publish contract

`sql/002_assertions.sql` is created with A1–A21. Each returns offending rows; empty means
pass. Actions are part of the contract.

| # | Assertion | Action on failure |
|---|---|---|
| A1 | Candidate has exactly `expected_teams` rows (20) | BLOCK (`whoscored_not_ready` if fewer) |
| A2 | `team_id` unique within the candidate | BLOCK |
| A3 | Exactly 9 feed captures for this run, covering every `(section, view)` once; one page capture and three standings views (A17) | BLOCK |
| A4 | Team-id set identical across all 9 feed captures | RETRY once, then BLOCK |
| A5 | `home + away = overall` for `apps`, `goal`, `yellowCard`, `redCard` | RETRY (mid-publish signature), then BLOCK |
| A6 | `apps`, `rating`, `shotsPerGame` agree across the sections that publish them | RETRY, then BLOCK |
| A7 | Every `ranking` in `1..N` (per section/view) | BLOCK; **uniqueness** only WARN |
| A8 | `rating ∈ [0,10]`, `possession`/`passSuccess` `∈ [0,1]`, counts `≥ 0`, all doubles finite | BLOCK |
| A9 | No NULL in `snapshot_id`, `team_id`, `team_name` | BLOCK |
| A10 | `apps` non-decreasing vs the last accepted snapshot of the same stage | BLOCK + require `--allow-apps-decrease` |
| A11 | Every capture URL contains `stageId=<run stage>` | BLOCK |
| A12 | `whoscored_page_url` contains `/seasons/<sid>/stages/<stid>/` | BLOCK |
| A13 | Payload `tournamentId` equals the configured id, and `isOpta` is constant within the run | BLOCK |
| A14 | `capture_span_seconds ≤ 180` | RETRY |
| A15 | `statColumns` exactly equals the expected set for that `(section, view)`; `name` vs `teamName` never diverges | BLOCK (`schema_drift`) |
| A16 | Fact→header anti-join is empty | BLOCK |
| A17 | Page capture always exists; the three standings views exist iff `has_league_table` | RETRY once (`whoscored_not_ready`) |
| A18 | Standings `team_id` set equals the feed `team_id` set | RETRY once, then BLOCK |
| A19 | Standings rows obey `W+D+L=P`, `Pts=3W+D`, `GD=GF-GA`, `len(form)=min(P,6)` (NULL only when `P=0`), form chars `w/d/l` | BLOCK |
| A20 | `home + away = overall` for `P/W/D/L/GF/GA/Pts` | RETRY (mid-publish), then BLOCK |
| A21 | Rank is a permutation `1..N` in every split | BLOCK |

Why A5 is not a `CHECK`: a mid-publish source legitimately produces `overall ≠ home +
away` for a few seconds. A `CHECK` would reject that state permanently; a RETRY fetches
the same state again and accepts it once the source settles. A `CHECK` on a *range*
(`rating ≤ 10`) is different: that can never be transiently true, so it stays a
constraint.

A10's escape hatch exists because a provider *can* revoke a match. The override is
explicit, logged, and records who asked.

---

## 7. The run, step by step

```
 1  acquire data/state/pipeline.lock                       (else exit 5)
 2  load config/stages.toml; open ingestion_run(running)
 3  load the stage page (`/show/...`) in the browser
       -> raw page HTML + `Model-last-Mode` token + `#stages` labels
       -> read Overall/Home/Away standings, one raw JSON each
       observed_at = min(captured_at) over the page and the standings
 4  GET summaryteam/all with the token  -> raw + raw_capture
       whoscored_feed_fingerprint = sha256(payload)
       if PROBE_SKIP and fp == checkpoint.last_seen_fingerprint:
           outcome=no_change; last_probe_at=now; exit 0        <-- disabled in v1
 5  GET the other 8, sequential, >=1.2 s apart, 3 tries, backoff 2/4/8 s + jitter
       a second consecutive gate page -> outcome=fetch_failed; exit 2
 6  write each raw atomically (O_EXCL) + .meta.json sidecar + raw_capture row
 7  parse all 9 -> 20 x 60 candidate rows; parse the 3 standings views
       A3, A4, A13, A15, A8 (row-level shape first)
       A17, A18, A19, A21 (standings shape)
 8  content_fingerprint = canonicalise(candidate + standings)
 9  if content_fingerprint == checkpoint.last_committed_fingerprint:
           outcome=no_change; last_probe_at=now; exit 0
10  BEGIN
11      stage candidate; A1, A2, A5, A6, A7, A9, A10, A16, A20
12      INSERT header ON CONFLICT (parent_snapshot_id, content_fingerprint) DO NOTHING
        if inserted: INSERT 20 fact rows + the standings rows
        UPDATE checkpoint (last_committed_fingerprint, last_success_at, last_outcome)
13  COMMIT; outcome=accepted; exit 0
```

**Recovery after a crash.** `run` verifies its own last step: at start, any `ingestion_run`
still marked `running` with a committed snapshot is reconciled to `accepted`. A run that
crashed before COMMIT has no snapshot and is marked `abandoned`; the retry reuses the
same parent and the same content, so the unique edge — not the id — prevents a duplicate.

**Canonicalisation** (must be byte-stable across machines and Python patch versions):

- rows sorted by `team_id`;
- keys sorted;
- include `team_id`, all 60 measures, the three standings views (rows sorted by
  `team_id`, splits in `overall, home, away` order), and the payload constants that
  carry meaning (`tournamentId`, `isOpta`);
- exclude `paging`, `name`, and presentation order;
- floats via `repr()` (shortest round-trip), ints as ints, `None` as `null`;
- join with `\n`, no trailing newline, UTF-8.

A change to this function changes every future id, so it is versioned:
`canonical_version` is stored on the header.

---

## 8. What the data can answer

### 8.1 `v_latest_team_state`

Current 20 rows. Snapshot chosen first, then joined (§4.3). Includes `observed_at`,
`accepted_at`, `snapshot_id`. A report pins `(stage, observed_at)`; `snapshot_id` is
internal lineage and may change on a rebuild.

`v_latest_standings` is the standings-only companion: the same snapshot selection,
joined to `fact_standings_snapshot` on `snapshot_id`, returning one row per team and
the 30 standings measures. It is useful when the consumer does not need the 60 team
measures.

The standings companion is `v_latest_team_with_standings`: the same 20 rows, joined to
`fact_standings_snapshot` on `(snapshot_id, team_id)`. It adds 30 columns (10 per split).
A knockout stage has zero standings rows; the join produces NULLs, not missing teams.

`v_standings_history` is the journey view: one row per `(stage, team, observed_at)` with
rank, points and form per split, ordered by `observed_at`. It is not a delta; it is the
series a chart or a "position over time" query reads.

### 8.2 `v_snapshot_delta`

For each team, the difference between consecutive **accepted** snapshots of the same
stage, over the **full** history — not over "the latest two rows per team", which is the
other classic bug:

```sql
with ordered as (
    select s.snapshot_id, s.observed_at, f.team_id,
           f.overall_apps, f.home_apps, f.away_apps,
           f.summary_overall_goal, f.summary_home_goal, f.summary_away_goal,
           lag(f.overall_apps) over w as prev_apps,
           lag(f.summary_overall_goal) over w as prev_goal
    from fact_team_snapshot f
    join competition_snapshot s using (snapshot_id)
    window w as (partition by s.tournament_id, s.whoscored_season_id,
                              s.whoscored_stage_id, f.team_id
                 order by s.observed_at, s.snapshot_id)
)
select *, overall_apps - prev_apps as d_apps,
          summary_overall_goal - prev_goal as d_goal,
          (overall_apps - prev_apps) < 0 as is_correction
from ordered where prev_apps is not null;
```

**Delta is defined only for the four additive measures** (`apps`, `goal`,
`yellowCard`, `redCard`). For `rating`, every `*PerGame`, `possession` and `passSuccess`
the arithmetic is meaningless: they are already normalised, so their difference is not a
count of anything.

### 8.3 The limit that must be written on the tin

From this feed you **cannot** recover per-match totals for a rate metric. Given
`shotsPerGame` and `apps` you can form `shots ≈ shotsPerGame × apps`, but:

- the source rounds nothing, so the product is exact only for the *cumulative* value;
- differencing two cumulative products double-counts the rounding of `apps`;
- the venue split (`home`/`away`) has a *different* denominator per team.

So v1 answers "how did the season-to-date table move", not "what happened in match N".
That is a true statement about the source and belongs in the README, not in a footnote.

### 8.4 `v_pipeline_freshness`

One row per stage: `last_probe_at`, `last_success_at`, `age_seconds`,
`last_outcome`, `attempt_count`, `accepted_snapshots`, `last_committed_fingerprint`.
This is the only view an operator needs, and monitoring reads it instead of the logs.

---

## 9. The six tables

```
ingestion_run ──< raw_capture
      │
      └──< competition_snapshot ──< fact_team_snapshot
                    │
                    ├──< fact_standings_snapshot
                    └── pipeline_checkpoint   (keyed by stage, not by snapshot)
```

`schema` (verbatim DDL) is created in `sql/001_schema.sql` in M1. The DDL must satisfy:

| Object | Requirement |
|---|---|
| `ingestion_run` | one row per attempt; `outcome` describes the **run**, never the data |
| `raw_capture` | `UNIQUE (run_id, section, view)`; `attempt`, `bytes`, `content_type`, `is_gate` |
| `competition_snapshot` | accepted rows only; `parent_snapshot_id`, `capture_span_seconds`, `canonical_version`, `is_opta`, `whoscored_page_url` |
| `fact_team_snapshot` | 60 measures; `CHECK (x >= 0)` on every stored count; FK to the header |
| `fact_standings_snapshot` | 30 measures (10 per split); FK to the header; zero rows when `has_league_table = false` |
| `pipeline_checkpoint` | keyed by `(tournament_id, whoscored_season_id, whoscored_stage_id)`; `last_accepted_snapshot_id`, `last_committed_fingerprint`, `abandoned_runs` |

---

## 10. Failure matrix

| What happens | Detection | Behaviour | Data after |
|---|---|---|---|
| Gate page (200, HTML) | structure check | retry with backoff; 2 in a row → stop | no rows, raw kept |
| 403 | status | retry with backoff; escalate to cookie refresh | no rows |
| BOM/`text/html` JSON | parser | accepted normally | normal |
| One section returns 19 teams | A1/A4 | retry, then BLOCK | old snapshot still latest |
| Overall published, splits not yet | A5 | RETRY (2×), then BLOCK | old snapshot still latest |
| Provider adds a column | A15 | BLOCK `schema_drift` | raw kept; parser must be updated |
| Provider removes a column | A15 | BLOCK `schema_drift` | raw kept |
| League stage has no standings table | A17 | RETRY once, then BLOCK | old snapshot still latest |
| Standings ids disagree with the feed | A18 | RETRY once, then BLOCK | old snapshot still latest |
| Standings internal arithmetic breaks | A19/A21 | BLOCK | raw page kept; parser repair |
| Home + away ≠ overall in the table | A20 | RETRY, then BLOCK | old snapshot still latest |
| Value missing | parser | `NULL`, never `0` | honest unknown |
| Same table, details changed | content fp | new snapshot | both states kept |
| Revert (A→B→A) | unique edge `(parent, content)` | new snapshot, `is_correction` on the delta | all three kept |
| Two runs overlap | lock | second exits 5 | none |
| Crash mid-publish | transaction | nothing committed | old state |
| Crash after commit, before run update | startup reconcile | run marked accepted | state intact |
| Disk full | `OSError` | run fails; no DB write | old state |
| Wrong stage in config | A11/A12 | BLOCK | none |
| Season mislabelled | A10 + A12 | BLOCK | none |
| Apps decrease (revoked match) | A10 | BLOCK unless `--allow-apps-decrease` | explicit |

---

## 11. Tests

Offline by default: every test runs against the nine captured payloads. One opt-in live
test.

### 11.1 The five must-haves (from the stack deck, kept)

1. **Publish twice = once.** Run the same observation twice; assert one snapshot.
2. **Crash before COMMIT = nothing.** Inject a raise after staging; assert zero snapshots
   and an `abandoned` run.
3. **Revert is recorded.** A → B → A; assert three snapshots and `is_correction` false,
   false, then the delta back.
4. **NULL is not zero.** Remove `goal` from one row; assert `NULL`, and that aggregating
   it yields `NULL`, not `0`.
5. **Parser golden files.** All nine feeds and the three standings views parse to a frozen row-set (checksummed).

### 11.2 Additional

- **Latest-state leak:** delete a team from the newest snapshot; the team must not
  reappear from an older one.
- **Delta partition:** three snapshots with one team absent in the middle; the delta must
  be computed over the full history and mark the gap, not silently join across it.
- **Id stability:** `canonicalise` is stable under row reordering, dict ordering, and a
  Python patch upgrade (golden hash).
- **Assertion traps:** each of A1–A21 has a poisoned fixture that must fail, and a clean
  fixture that must pass. (A4, A5, A6, A7, A15 get two traps each.)
- **FK + anti-join:** inserting a fact row without its header fails; the anti-join query
  returns empty on clean data.
- **DB shape:** schema applies twice (idempotent), FK enforced, CHECKs enforced.
- **Gate detection:** 200/HTML, 403, truncated JSON, BOM+JSON, empty body.
- **Live (opt-in, `-m live`):** one probe + one full sweep, asserting the page, 3 standings views, 9 captures, 20
  teams, and that the probe payload is byte-identical to the Summary/Overall leg.

### 11.3 Quality gates

`AGENTS.md` requires `ruff format`, `ruff check`, `mypy main.py`, `pytest`. There is no
`main.py` today. **Decision:** create `main.py` as a six-line entrypoint delegating to
`dataderby.cli.main`, so the existing gate is satisfied literally and no rule is amended
for convenience.

Dependencies to add (needs sign-off, per `AGENTS.md`):

| Package | Why | Alternative rejected because |
|---|---|---|
| `duckdb` | the store | SQLite cannot do `QUALIFY`/`ASOF`/`DOUBLE` semantics we rely on |
| `pydantic` | config + envelope models | hand-rolled validation drifts |
| `pytest` | tests | stdlib `unittest` has no fixtures/markers |
| `hypothesis` (dev-only) | property tests for canonicalisation | table-driven cases are weaker for row/key order properties |
| `ruff` | format + lint | gate already names it |
| `mypy` | gate already names it | — |

No `pandas`, no `pandera`, no `requests`, no `dlt`, no `dbt`, no orchestrator.
`curl-cffi` and `patchright` are already present.

---

## 12. Layout

```
main.py                      # entrypoint (AGENTS.md gate)
pyproject.toml
config/stages.toml           # the stage registry (new, §13)
sql/
  001_schema.sql
  002_assertions.sql
  003_views.sql
src/dataderby/
  cli.py                     # run | probe | replay | verify | freshness
  config.py                  # StageSpec, Settings (pydantic)
  contract.py                # sections, views, expected statColumns, ownership
  fetch.py                   # curl_cffi session, retries, gate detection
  cookie.py                  # patchright cookie refresh (only after a hard block)
  raw.py                     # atomic write + sidecar + path builder
  parse.py                   # pure: bytes -> CandidateRows
  canonical.py               # pure: candidate -> fingerprint
  publish.py                 # transaction: stage -> assert -> insert -> checkpoint
  validate.py                # A1..A21 execution + action dispatch
  lock.py
  observe.py                 # structured JSON logging
tests/
  golden/                    # the 9 payloads + expected checksum
  fixtures/                  # poisoned cohorts
  tools/measure_caps.py
data/                        # git-ignored: raw/ dataderby.duckdb logs/ state/
```

`data/` must be added to `.gitignore` before the first run (raw payloads are not
redistributable — §15).

---

## 13. The missing registry

Both the scrape deck and the stack deck name the same gap: *"What is missing is the
tournament and stage list, so a season can be named rather than hardcoded."* v1 closes it
with a file, not a scraping feature:

```toml
# config/stages.toml
[[stage]]
tournament_id    = 4
whoscored_season_id = 11213
whoscored_stage_id  = 25662
season_key       = "2026-2027"
competition      = "LaLiga"
expected_teams   = 20
whoscored_page_url  = "https://www.whoscored.com/seasons/11213/stages/25662/..."
has_league_table = true
```

Rationale: discovery of new stage ids is a **human, monthly** task with a URL in it. A
scraper that guesses ids is a scraper that silently ingests the wrong competition. v2 may
add `dataderby stages discover <url>` when the manual step is actually painful.

---

## 14. Unknowns and the experiments that close them

Nothing here blocks M1–M4. Each is scheduled, each has a pass condition.

| # | Unknown | Experiment | Pass condition | Blocks |
|---|---|---|---|---|
| E1 | Is `summaryteam/all` a sufficient probe? | Compare 100 consecutive probe/sweep pairs | probe change ⇒ sweep change, 100/100 | probe-only scheduling |
| E2 | Does an unchanged table imply unchanged details? | Freeze a fingerprint, watch a live matchday, diff all 9 | no detail moves while the table is identical, over ≥2 matchdays | **the skip rule — the only gate on §4.5** |
| E3 | Are values corrected retroactively? | Re-fetch 24 h after acceptance, compare | classify: none / additive late / rewrite | correction policy (§10, A10 override) |
| E4 | Is `team_id` stable across seasons? | Two seasons of the same competition | same ids for the same clubs | crosswalk design, identity |
| E5 | Publication latency after a final whistle? | Probe every 5 min across a match window | a distribution, not a number | schedule cadence, grace period |
| E6 | Does the gate become cookie-bound? | Run probe-only for 7 days, log every gate trip | < 1% gate rate, no cookie needed | cookie refresh, request pacing |

E5 is executable now: `experiments/whoscored/cadence_probe.ps1` logs one JSON line per
interval, and `docs/whoscored-cadence.md` records the header evidence, the method and
the provisional schedule. Next window: EPL, 2026-10-24 22:00 IST to 2026-10-25 04:00
IST. Until it reports, the schedule is a 06:00 IST daily heartbeat plus
`last kickoff + 2 h` and `+6 h` sweeps.

**E2 is the release gate for the optimisation, not for v1.** If E2 fails, the pipeline
still works; it just keeps paying nine requests.

Anything still open at the end of v1 is listed in `docs/open-questions.md` with the
experiment id, so the next person does not start from zero.

---

## 15. Licence gate

`isOpta = true` on every row. That is **provenance**: the data is Opta-sourced and
WhoScored is presenting it under some arrangement. It is not proof of a violation, and
it is not proof of permission.

**Decision (2026-10-20): accepted by the project owner.** The decision and its scope are
recorded in `docs/whoscored-decisions.md`. The operational posture is unchanged:

- local and private;
- raw payloads never committed;
- no public redistribution of the raw feed;
- no bulk historical scrape beyond the configured seasons.

The M6 licence checkbox is satisfied. The remaining M6 work is the record link and the
backup/replay drill, not a legal decision. `isOpta` stays a recorded field and is never
a failure path (R7).

---

## 16. Milestones

Each milestone has an exit criterion that a reviewer can check without reading the code.

### M0 — Decisions and hygiene (½ day)
- [ ] ADR-0001 history model (Option A, ULID + unique edge)
- [ ] ADR-0002 precision (store full precision, round at presentation)
- [ ] ADR-0003 two clocks (observation vs acceptance)
- [ ] ADR-0004 raw is the system of record
- [ ] ADR-0005 DuckDB as the store (with the measured FK/limit notes)
- [ ] `data/` ignored; dependency sign-off recorded

**Exit:** ADRs merged; `uv sync` clean; `uv run ruff check` runs on an empty tree.

### M1 — Schema and contract (1 day)
- [ ] create `001_schema.sql` per §9
- [ ] create `002_assertions.sql` A1–A21 with actions
- [ ] `003_views.sql` (§8)
- [ ] test: schema applies twice; FK enforced; every CHECK enforced
- [ ] test: every assertion has a trap fixture and a clean fixture

**Exit:** `pytest tests/test_schema.py tests/test_assertions.py` green. All 21 traps fail
on the poisoned fixture and pass on the clean one.

### M2 — Fetch and raw landing (1 day)
- [ ] `page.py`: load the stage page, mint the token, read `#stages`
- [ ] `standings.py`: read Overall/Home/Away from `tr[data-team-id]`
- [ ] `fetch.py`: 3 tries, backoff, gate detection by structure, 1.2 s pacing
- [ ] `raw.py`: atomic `O_EXCL` write, sidecar, path layout
- [ ] `raw_capture` + `ingestion_run` rows (page, standings, 9 feeds)
- [ ] tests: gate page, 403, truncated body, BOM, duplicate run id

**Exit:** a sweep against a local replayed server writes the page, 3 standings views and
9 feed files; a second identical sweep writes the same set again and zero DB duplicates.

### M3 — Parse and canonicalise (1 day)
- [ ] `contract.py`: expected `statColumns` per (section, view), ownership table
- [ ] `parse.py`: 9 payloads → 20 × 60; NULL for absent; hard fail on drift
- [ ] `parse_standings.py`: 3 views → rows keyed by `team_id`
- [ ] `canonical.py`: stable fingerprint over stats + standings + `canonical_version`
- [ ] golden checksum test
- [ ] tests: row reorder changes nothing; a dropped key yields NULL; an extra key blocks

**Exit:** golden checksum matches; §5.2 arithmetic reproduced by a test that counts
columns rather than trusting the document.

### M4 — Publish and views (1–2 days)
- [ ] transaction: stage → assert → insert header + 20 facts + standings → checkpoint → COMMIT
- [ ] ULID `snapshot_id` + `ON CONFLICT (parent, content) DO NOTHING` + genesis sentinel
- [ ] startup reconcile for abandoned/accepted runs
- [ ] views + the latest-state leak test + the delta partition test
- [ ] `dataderby verify-replay`: rebuild from raw → identical `(stage, observed_at, content_fingerprint)`; ids may differ

**Exit:** the five must-haves (§11.1) green; replay reproduces the committed content
exactly, with ids excluded from the diff.

### M5 — Measurement harness (1 day)
- [ ] E1, E3, E5 runnable as `dataderby measure <experiment>`
- [ ] E2 has a documented protocol and a report template
- [ ] `docs/open-questions.md` seeded

**Exit:** E1 and E3 produce a written result from live data; E2 has a scheduled window.

### M6 — Ops and the v1 gate (1 day)
- [ ] lock, structured logs, `v_pipeline_freshness`, exit codes
- [ ] backup of `data/raw` (second disk or object store) **and a restore drill**
- [ ] scheduler entry (daily probe + post-match window)
- [x] licence decision recorded, 2026-10-20 (`docs/whoscored-decisions.md`, §15)
- [ ] README: what the data can and cannot answer (§8.3)

**Exit — the v1 gate:**
1. two consecutive scheduled runs happen with no manual intervention;
2. the second run reports `no_change` **and writes nothing**;
3. a deliberately poisoned cohort (19 teams) is refused and the previous snapshot stays
   latest;
4. `v_pipeline_freshness` shows both runs;
5. a raw file is restored from backup and replays to the same snapshot id;
6. all AGENTS.md gates pass.

---

## 17. Status of the eight model failure modes

From `option-c-model-slides.html` P18. Five survive without Option C; three are
Option-C-only and die with the deferred dimension.

| # | Failure | Status in v1 |
|---|---|---|
| 1 | NULL `valid_to` join | **gone** — no validity intervals |
| 2 | Overlapping / gapped intervals | **gone** — append-only, no intervals |
| 3 | Two current rows per team | **gone** — no `is_current`; latest is a snapshot selection |
| 4 | `is_current` vs `valid_to` divergence | **gone** — one representation |
| 5 | Which clock bounds validity | **fixed** - one clock, `observed_at` on the header and used for ordering; `accepted_at` only records acceptance, documented in ADR-0003 and A14 |
| 6 | Unenforced referential integrity | **fixed differently than the deck says** — FK *is* enforced; we keep it, keep A16, and declare `parent_snapshot_id` as a plain column because self-referencing FKs do not work |
| 7 | Spurious versions from cosmetic drift | **fixed** — names are never identity; `team_id` is; `name`/`teamName` divergence is a drift signal (A15) |
| 8 | Restatement rewrites the past | **fixed** - reports pin `(stage, observed_at)`; `observed_at` orders history; `accepted_at` only records acceptance; raw is immutable. Measured: that address survives a rebuild *and* a backfill (20/20 rows); a pinned `snapshot_id` survives neither after a backfill |

Separately, the five model bugs that survive without Option C:

| Bug | Fix | Covered by |
|---|---|---|
| `latest_*` takes the max time per fact row | select the snapshot first, then join | §4.3, test 11.2 |
| Delta computed over "latest two" instead of full history | `lag()` over the whole partition | §8.2, test 11.2 |
| `observed_at` missing from the header | on the header, with `capture_span_seconds` | §4.2, A14 |
| Header mixes candidates and accepted rows | accepted only; candidates live in `ingestion_run` + `raw_capture` | §9 |
| `tournamentName` used as identity | `tournament_id` only; name is a label | A13 |

---

## 18. Risks

| Risk | Likelihood | Impact | Mitigation | Detection |
|---|---|---|---|---|
| Gate tightens (cookie-bound / JS) | medium | high | `patchright` fallback already installed; E6 measures | gate rate in `v_pipeline_freshness` |
| Source changes shape mid-season | medium | medium | A15 blocks; raw keeps the evidence | `schema_drift` exit code |
| Silent mid-publish cohort | medium | high | A4–A6 + retry | `is_correction` / validation failures |
| Licence decision is "no" | unknown | total | gate at M6, before any new load | §15 |
| Chained id makes an out-of-order backfill impossible | low | medium | history is acceptance-ordered by design; `verify-replay` proves it | M4 |
| Raw archive lost | low | total | backup + restore drill | M6 gate 5 |
| DuckDB lock contention | low | low | single-writer lock | exit code 5 |
| A10 blocks on a legitimate revocation | low | medium | explicit, logged override | run log |

---

## 19. What would make me abandon this plan

Stated up front, because a plan without a falsifier is a belief:

- **E2 shows the table is unchanged while details move.** Then the probe is useless and
  the schedule must be full sweeps — the design survives, but the cost model in the
  decks does not.
- **The source has no stable team id across seasons** (E4). Then identity must be built
  from a name-based crosswalk sooner than planned, and Option C stops being optional.
- **The licence is withdrawn or the redistribution terms change.** Then v1 becomes an
  offline exercise over the captured evidence and the plan's M5/M6 change shape entirely.
- **The source stops publishing season-to-date tables** in favour of per-match data.
  Then the whole snapshot premise is wrong and this plan should be discarded, not
  patched.

---

## 20. Decisions I need from you

1. **Approve the runtime dependencies** (`duckdb`, `pydantic`) and the **dev-only**
   `hypothesis`; `pytest`, `ruff` and `mypy` are already part of the gates.
2. **Approve Option A for v1** with a **ULID** `snapshot_id` and
   `UNIQUE (parent_snapshot_id, content_fingerprint)` (R5, revised on evidence in
   `experiments/id-scheme/`). Reports pin `(stage, observed_at)`.
3. **Confirm the stage registry is a file** (`config/stages.toml`), not a scrape.
4. **Note:** the licence gate is closed (2026-10-20). A new live sweep may run under the
   recorded local/private/non-redistributed posture; no further legal decision is pending.

Until (1) and (2) are answered, work stops at M0/M1, which need neither.
