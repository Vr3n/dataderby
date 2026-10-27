# How this repository is structured

**Status:** current
**Audience:** a data engineer joining the project, or the author learning the
conventions behind it.
**Scope:** the folder layout, why it looks this way, how it maps to cloud
(Databricks/Azure) projects, and where new files go.

## 1. What this project is, and what it is not

It is a **single-node Python pipeline**: a browser capture, nine JSON feeds, a
parser, SQL assertions, and a DuckDB database. It runs on one machine and it is
deployed nowhere.

It is **not** a Databricks or Azure project. That matters for structure: copying a
cloud repository wholesale would add folders (`infra/`, `resources/`, notebooks)
that currently hold nothing. Instead, the layout follows the same **principles**
and leaves the cloud-specific folders for the moment they have content.

The principles are:

1. Production code lives under `src/` and is importable as a package.
2. Tests live outside the package and mirror its modules.
3. SQL that defines the contract is versioned like code.
4. Data is never committed; only the code that produces it.
5. Configuration is data, not code, and is validated at load time.
6. Documentation has a home per kind: decisions, reports, research, decks.

## 2. Four conventions worth learning

### 2.1 The Python `src/` layout

The Python Packaging Authority recommends putting the importable package under
`src/` rather than at the repository root. The reason is concrete: with a flat
layout, `import dataderby` can silently pick up the working copy instead of the
installed package, so a missing file only fails after packaging. The `src/`
layout forces an install (or an editable install) and makes that class of bug
impossible. ([PyPA: src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/))

Our version:

```
src/dataderby/          the package
tests/                  pytest, outside the package
pyproject.toml          packaging, dependencies, tool config
uv.lock                 the resolved environment
```

### 2.2 The Databricks bundle layout

A Databricks Declarative Automation Bundle (formerly Asset Bundle) is a
repository that contains code **and** the definitions of the jobs and pipelines
that run it. A default Python bundle looks like this:

```
my_project/
├── databricks.yml          # bundle name, targets, variables
├── resources/              # job and pipeline definitions (YAML)
│   └── sample_job.job.yml
├── src/                    # the code the job runs
│   └── sample_notebook.ipynb
├── tests/                  # unit tests
└── README.md
```

The important idea is not the file names. It is that **infrastructure and code
are versioned together**, and a deploy is a single unit. ([Databricks: what are
bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/), [job
tutorial](https://docs.databricks.com/aws/en/dev-tools/bundles/jobs-tutorial))

Our equivalent:

| Bundle concept | Here |
|---|---|
| `src/` | `src/dataderby/` |
| `resources/` (job definitions) | `config/stages.toml` + `config/dagster.yaml` |
| `databricks.yml` (targets, deploy) | not needed yet; `pyproject.toml` + `.github/workflows/ci.yml` cover build and test |
| `tests/` | `tests/` |

When this project moves to Databricks, `databricks.yml` and `resources/` are
added; the package under `src/` does not move.

### 2.3 The medallion layers

Azure Databricks describes three quality layers: **bronze** (raw ingestion),
**silver** (cleaned and validated), and **gold** (business-level, aggregated).
Bronze keeps the source exactly as received and is the layer that enables
reprocessing. Silver enforces schema and quality. Gold models the business.
([Azure Databricks: medallion architecture](https://learn.microsoft.com/en-us/azure/databricks/lakehouse/medallion))

Our mapping:

| Layer | Here | Notes |
|---|---|---|
| Bronze | `data/raw/<tournament>/<season>/<stage>/<timestamp>/` | page, standings, nine feeds, SHA-256 sidecars. Git-ignored. |
| Silver | the in-memory `Candidate` + standings, checked by A1–A22 | **Not persisted.** See below. |
| Gold | DuckDB `fact_team_snapshot`, `fact_standings_snapshot`, and the `v_latest_*` / history views | What a consumer reads. |

Why silver is not a folder: the dataset is 20–36 teams per snapshot, the
transformations are pure functions over a few hundred kilobytes, and every
published snapshot can be rebuilt from bronze. Persisting a silver copy would
double the storage and add a second thing to keep consistent. In a cloud project
with many sources and teams, a persisted silver layer earns its keep; here it is
a deliberate omission.

### 2.4 The dbt layering (staging → intermediate → marts)

dbt's project guide recommends three model layers: **staging** (one model per
source, renaming and casting only), **intermediate** (purpose-built steps), and
**marts** (business entities). ([dbt: how we structure our dbt
projects](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview))

We do not use dbt, but the same separation exists in code:

| dbt layer | Here |
|---|---|
| Staging | `parse.py`, `parse_standings.py` — source shape to typed rows |
| Intermediate | `canonical.py`, `contract.py` — ownership, naming, fingerprint |
| Marts | `publish.py`, `sql/001_schema.sql`, `sql/003_views.sql` — facts and consumer views |
| Tests | `sql/002_assertions.sql`, `tests/` |

This is why the parser does not write to the database and the publisher does not
know how JSON looks. Each layer can be tested alone.

## 3. The tree, annotated

```
dataderby/
├── AGENTS.md                 rules for humans and agents working here
├── README.md                 what the project is, how to run it
├── pyproject.toml            package, dependencies, tool config
├── uv.lock                   resolved environment (commit this)
├── main.py                   legacy fixture CLI (see "deliberate leftovers")
│
├── src/dataderby/            production package
│   ├── config.py             TOML → validated StageSpec/Settings
│   ├── contract.py           the 60 + 30 measure contract
│   ├── page.py               browser capture: token, table, standings
│   ├── fetch.py              nine feeds, URL contract, retries
│   ├── raw.py                atomic raw bundle, SHA-256, no overwrite
│   ├── landing.py            one sweep → raw files + run/raw ledger
│   ├── parse.py              feeds → Candidate (60 measures)
│   ├── parse_standings.py    page → StandingsCandidate (30 measures)
│   ├── canonical.py          sort, encode, fingerprint
│   ├── validate.py           A1–A22, actions, PublishBlocked
│   ├── publish.py            one transaction, no_change, reconcile
│   ├── db.py                 connect, migrate, transaction
│   ├── lock.py               exclusive pipeline lock
│   ├── observe.py            append-only JSONL events
│   ├── schedule.py           staleness check, heartbeat ping, scheduled-run wrapper logic
│   ├── cli.py                run, probe, replay, verify, freshness, stages
│   ├── __main__.py           python -m dataderby
│   └── fixtures/             the separate fixture-calendar pipeline
│
├── sql/                      the database contract, versioned
│   ├── 001_schema.sql        tables, constraints, keys
│   ├── 002_assertions.sql    A1–A21, comment-delimited
│   ├── 003_views.sql         consumer views
│   ├── 004_points_adjustments.sql  the points-deduction view
│   └── 005_assertions_a22.sql      A22, appended because 002 is immutable
│
├── config/                   runtime configuration, not code
│   ├── stages.toml           the stage registry
│   └── dagster.yaml          Dagster instance config (fixtures only)
│
├── scripts/                  operator tools, not imported by the package
│   ├── audit_all_stages.py   the all-league sweep
│   ├── capture_live_stage.py one-stage fixture capture
│   └── dagster.ps1           the fixture pipeline UI
│
├── tests/                    pytest; mirrors the package
├── plans/                    design and build plans (living documents)
├── experiments/              measurement scripts and results (id scheme)
├── docs/                     see docs/README.md
│   ├── adr/                  decisions, one file each
│   ├── reports/              phase and change reports
│   ├── slides/               deck rules + HTML decks
│   ├── research/             source notes and measurements
│   ├── design/               architecture and this guide
│   └── reference/            archived decks, reports, source PDFs/pptx
│
├── data/                     git-ignored: raw, databases, logs
└── .github/workflows/ci.yml  the four gates on Ubuntu and Windows
```

## 4. Where new things go

| You are adding… | Put it in | Rule |
|---|---|---|
| A pipeline module | `src/dataderby/` | Importable, typed, docstring, no CLI code |
| A test | `tests/test_<module>.py` | Same name as the module it tests |
| A schema change | `sql/00N_*.sql` | One file, one change; never edit an applied file |
| A new stage or path | `config/stages.toml` | Source-prefixed ids; `expected_teams` from the page |
| An operator tool | `scripts/` | Not imported by the package; document it in `scripts/README.md` |
| A decision | `docs/adr/NNNN-*.md` | Context, decision, rejected alternatives |
| A phase/change report | `docs/reports/` | Follow `docs/reports/TEMPLATE.md` |
| A deck | `docs/slides/` | Follow `docs/slides/RULES.md` |
| Source research | `docs/research/` | Cite the URL and the date measured |
| A plan | `plans/` | Living document, not a report |
| Raw data | `data/` | Never commit; the path is git-ignored |
| A notebook | nowhere, for production | Prototype in `experiments/`, then move the logic to `src/` |

## 5. Deliberate leftovers

- **`main.py`** is a convenience wrapper for the fixture CLI. The production CLI
  is the `dataderby` console script. When the fixture pipeline is retired,
  `main.py` goes with it.
- **`sql/` at the root** rather than inside the package: the files are the
  database contract, and keeping them next to `config/` makes them visible. If
  the package is ever shipped as a wheel, these move to package data and
  `db.py` switches to `importlib.resources`.
- **No `infra/`**: there is no cloud resource to describe. Adding Terraform or
  Bicep now would be an empty folder with a README.
- **No `notebooks/`**: production logic belongs in importable modules. Notebooks
  are for exploration and do not survive review well.

## 6. If this moves to Databricks/Azure

The logic does not need a rewrite; the adapters do.

| Today | On Databricks/Azure |
|---|---|
| `data/raw/` on local disk | ADLS Gen2 `bronze/` container |
| DuckDB file | Delta tables in Unity Catalog, `gold` schema |
| `connect()` / `migrate()` | SQL warehouses or a job cluster; migrations still versioned |
| `fetch.py` over `curl_cffi` | the same browser/session logic in a job task, or an ingestion service |
| `publish.py` inserts | `MERGE`/append into Delta, same transaction semantics |
| `config/stages.toml` | bundle variables + `resources/` job definitions |
| GitHub Actions | the same gates, plus `databricks bundle validate/deploy` |
| `scripts/audit_all_stages.py` | a job or a notebook in `src/`, still not production code |

Add `infra/` (Bicep or Terraform) and `resources/` (job YAML) at that point, not
before. Keep `contract.py`, `canonical.py`, and the assertion SQL: they are the
parts that encode the domain, and they are portable.

## 7. A reading path

1. This file.
2. `README.md` — what runs today.
3. `AGENTS.md` — the rules.
4. `src/dataderby/config.py` → `contract.py` — what a stage and a measure are.
5. `page.py` → `fetch.py` → `raw.py` — how bytes arrive.
6. `parse.py` → `parse_standings.py` → `canonical.py` — how bytes become a candidate.
7. `validate.py` → `publish.py` — how a candidate becomes history.
8. `sql/001` → `002` → `003` — the contract in DDL.
9. `tests/` — the executable specification.
10. `docs/reports/p0…p8` — what was built and what deviated.
11. `docs/adr/` — the decisions that are expensive to reverse.

## 8. Sources

- PyPA, [src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/).
- Databricks, [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/)
  and [Develop a job with bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/jobs-tutorial).
- Azure Databricks, [What is the medallion lakehouse architecture?](https://learn.microsoft.com/en-us/azure/databricks/lakehouse/medallion).
- dbt Labs, [How we structure our dbt projects](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview).
- This repository: `docs/adr/0005-duckdb-as-store.md`,
  `docs/adr/0004-raw-is-system-of-record.md`, `docs/reports/p3-schema.md`.
