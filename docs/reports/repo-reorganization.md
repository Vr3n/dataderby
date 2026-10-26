# Repository structure reorganisation

**Status:** complete
**Date:** 2026-10-26
**Type:** change report
**Guide:** `docs/design/project-structure.md`

## Goal

Make the repository legible to a data engineer who has never seen it.

Before this change, `docs/` held **24 files at its root**: decks, research notes,
old reports, a `.pptx`, a `.docx`, and a one-page summary. There was no index, no
statement of where new documents belong, and no written mapping to the
Databricks/Azure conventions the project claims to follow.

The code layout was already sound (`src/`, `tests/`, `sql/`, `config/`,
`scripts/`). The problem was the documentation layer and the missing rationale.

## What changed

| Before | After | Why |
|---|---|---|
| `docs/*.html` (7 decks) | `docs/slides/` | Decks are a kind of document, not root clutter |
| `docs/whoscored-*.md` (6 files) | `docs/research/` | Source notes and measurements |
| `docs/design/architecture-decisions.md` | `docs/design/` | Design material, not research |
| `docs/reports/p8-summary.md` | `docs/reports/` | A phase summary belongs with its phase |
| 9 archived decks, reports, `.pptx`, `.docx` | `docs/reference/` | Kept for context, not maintained |
| none | `docs/README.md` | The index a newcomer reads first |
| none | `docs/design/project-structure.md` | The guide and cloud mapping |
| none | `scripts/README.md` | What each operator tool does and writes |
| none | this report | The change record |

`docs/` now contains one index and six folders:

```
docs/
├── README.md
├── adr/          decisions
├── design/       architecture and the structure guide
├── reference/    archived artefacts
├── reports/      phase and change reports
├── research/     source notes and measurements
└── slides/       deck rules and HTML decks
```

## What did not change

- No Python module moved. `src/dataderby/`, `tests/`, `sql/`, `config/`, and
  `scripts/` are where they were.
- `main.py` stays as the legacy fixture entry point.
- `sql/` stays at the repository root. It is the database contract, and the
  structure guide records the trade-off (package data if the project is ever
  shipped as a wheel).
- No runtime dependency was added.

## Link updates

Twenty-three Markdown/HTML files had references rewritten:

- `docs/<file>` → `docs/<folder>/<file>`.
- `../<file>` from `docs/reports/` and `docs/adr/` → `../<folder>/<file>`.

A link checker resolved every relative Markdown and HTML link in the repository.
The only two remaining unresolved `href` values are inline `data:image/svg+xml`
URIs, which are images, not links.

## Verification

```
$ uv run python (link checker)
files changed: 23
broken links: 0 (excluding 2 data: URIs)
```

The code gates were not affected by a documentation move, but they were run
anyway before the commit: `ruff format --check`, `ruff check`, `mypy main.py`,
`pytest`.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| External bookmarks to old paths break | There are no published external links yet. The index and the guide give the new paths. |
| A relative link was missed | The link checker runs over every `.md` and `.html` file; it is re-run after any move. |
| The guide drifts from the tree | `AGENTS.md` points to it, and the layout section is short enough to keep current. |
| Someone adds a file to `docs/` root again | `docs/README.md` states the rule; `AGENTS.md` repeats it. |

## Reviewer checklist

- [ ] Every top-level `docs/` entry is the index or a folder.
- [ ] `docs/README.md` links resolve.
- [ ] `docs/design/project-structure.md` matches the tree.
- [ ] `scripts/README.md` matches the scripts.
- [ ] No code file moved; tests still pass.
- [ ] The reports index has this report.

## References

- `docs/design/project-structure.md` — the researched guide.
- `docs/README.md` — the documentation index.
- `AGENTS.md` — repository layout rules.
- Databricks bundles, Azure medallion, dbt structure, PyPA `src/` layout — cited
  in the guide.
