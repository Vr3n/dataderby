# Documentation

This folder is organised by **kind of document**, not by date. If you are new to
the project, read [`design/project-structure.md`](design/project-structure.md)
first: it explains the repository layout and how it maps to Databricks/Azure
conventions.

## Where to look

| Folder | What lives there | Start with |
|---|---|---|
| [`design/`](design/) | How the system is put together | [project-structure.md](design/project-structure.md), [architecture-decisions.md](design/architecture-decisions.md) |
| [`adr/`](adr/) | Decisions that are expensive to reverse | [0001-history-model.md](adr/0001-history-model.md) |
| [`reports/`](reports/) | Phase reports, change reports, summaries | [reports/README.md](reports/README.md) |
| [`slides/`](slides/) | HTML decks and the rules for making them | [RULES.md](slides/RULES.md) |
| [`research/`](research/) | Source notes, measurements, discovery | [whoscored-discovery-report.md](research/whoscored-discovery-report.md) |
| [`reference/`](reference/) | Archived decks, reports, and source guides | — |

## Reading paths

**A new engineer**

1. [`design/project-structure.md`](design/project-structure.md) — the map.
2. `README.md` at the repository root — what runs today.
3. [`design/architecture-decisions.md`](design/architecture-decisions.md) — the shape.
4. [`reports/p3-schema.md`](reports/p3-schema.md) → [`p4`](reports/p4-fetch-raw.md) →
   [`p5`](reports/p5-parse-canonical.md) → [`p6`](reports/p6-publish.md) →
   [`p7`](reports/p7-views.md) — the build order.
5. `tests/` — the executable specification.

**An agent joining the repo**

1. `AGENTS.md` — the rules and the gates.
2. [`reports/`](reports/) — the latest report ends with deviations and open items.
3. [`slides/RULES.md`](slides/RULES.md) before writing any deck.

**A reviewer**

1. [`reports/README.md`](reports/README.md) — what was built, phase by phase.
2. [`adr/`](adr/) — why the irreversible choices were made.
3. [`reports/all-league-capture.md`](reports/all-league-capture.md) — the latest
   live result.

## Where new documents go

| You are writing… | Put it in |
|---|---|
| A decision with alternatives | `docs/adr/NNNN-<slug>.md` |
| A build phase or a single change | `docs/reports/<slug>.md` (see the template) |
| A slide deck | `docs/slides/<topic>-slides.html` (see the rules) |
| Source research or measurements | `docs/research/<source>-<topic>.md` |
| Architecture or a guide | `docs/design/<topic>.md` |
| An archived artefact | `docs/reference/` |

Do not add files to the root of `docs/`. The root holds this index and the six
folders.

## A note on `reference/`

`reference/` contains older decks and reports that explain how the design
evolved. They are kept for context, not maintained. The current documents are in
`design/`, `reports/`, and `slides/`.
