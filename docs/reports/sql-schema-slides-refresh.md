# SQL schema slides refresh (tables slide, highlighting, counts)

**Status:** complete
**Date:** 2026-10-27
**Deck:** `docs/slides/sql-schema-slides.html`
**Companion:** `docs/reports/sql-schema-deck.md`

## Goal

Slide 05 ("Seven tables") confused readers: the "Why it exists" column was vague, it never said which columns each table stores, and it never showed what a snapshot contains. This change rewrites that slide, adds lightweight SQL syntax highlighting, improves the ER-adjacent visuals, and fixes stale view/assertion counts — without changing the deck's argument, theme, or motion.

## What changed

| File | Change | Why |
|---|---|---|
| `docs/slides/sql-schema-slides.html` | Rewrote slide 05 as grain + key + principal columns with chips, plus a 1+20+20 snapshot strip; rewrote headline and explainer | "Why it exists" did not say what is stored; a snapshot is 41 rows, not one row |
| `docs/slides/sql-schema-slides.html` | Added `.kw/.ty/.str/.num/.cm/.cols/.snap-ex` CSS and highlighted header, fact, and latest-view code | Plain mono SQL is hard to scan; keywords, types, and comments now carry colour |
| `docs/slides/sql-schema-slides.html` | Cover 7 views/22 assertions to 8 views/23 definitions; glossary, transaction, no-procedure, and views footnotes to match | File has 8 views (`003_views.sql` + `004`) and 23 definitions (A1-A21 + A7U + A22) |
| `docs/slides/sql-schema-slides.html` (pass 2) | Rewrote slide 02, glossary rows, slide 06 note, header kv, fact kv, shape table, keys, NULL block, append-only cards, conflict, transaction, assertion cards (WARN 1 to 2), views table | Slides named mechanisms without showing values; now each names the actor, the repo location, and a live example (EPL hash, Brighton, team 13) |
| `docs/reports/sql-schema-slides-refresh.md` | This report, updated for pass 2 | AGENTS.md requires one report per non-phase change |
| `docs/reports/README.md` | Index row for this refresh | Keep the index complete |

## Design decisions

- Kept one slide for the seven tables (no split): the strip plus chips fits 1600x900 without scrolling. A split would break the "seven jobs" claim.
- Chips show representative columns, not all 63/33: full lists live in `sql/001_schema.sql` and the header/facts slides.
- Highlighting is span-based, no JS highlighter: the deck must work offline with the GSAP CDN blocked.
- Counts fixed to file truth: 8 views, 23 assertion definitions, 28 slides/notes preserved.

### Rejected alternatives

- **Split slide 05 in two.** Clearer per table, but loses the at-a-glance seven-way comparison.
- **Full column lists on slide 05.** Accurate, unreadable at deck size; the header/facts slides already carry DDL.
- **JS highlighter (highlight.js).** Extra dependency and CDN failure mode for three code slides.

## Test matrix

| Test | Pins |
|---|---|
| Manual: 28 `<section class="slide">`, 28 `data-note`, balanced divs | structure intact |
| `node --check` on extracted inline script | script still parses |
| Visual: cover, slide 05, a code slide rendered at 1600x900 | no clipping by footer/stage |

What this deliberately does not assert: DuckDB behaviour, assertion logic, and counts beyond slide text (covered by `pytest` and P3/P6/P7 reports).

## Evidence

```text
$ uv run ruff format --check
106 files already formatted
$ uv run ruff check
All checks passed!
$ uv run pytest -q -p no:cacheprovider
233 passed in 261.51s (0:04:21)
$ uv run python check_deck.py
slides: 28
notes: 28
inline scripts: 1
section close: 28
div open/close: 342 342
```

`node --check` on the extracted inline script passed. Test count in the deck corrected 216 to 233 to match the suite.

## Deviations and open items

- Did not re-render every slide as an image; checked cover, slide 05, and one code slide at reference size.
- Did not touch `docs/reports/sql-schema-deck.md`; this file links to it instead of editing it.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Slide 05 overflows at 1600x900 on small fonts | Chips wrap; table uses compact sizing; verified no footer overlap |
| Highlight spans break copy-paste of SQL | Spans carry no text change; underlying SQL identical |

## Reviewer checklist

- [ ] Slide 05 grain + columns match `sql/001_schema.sql`.
- [ ] 8 views / 23 definitions match `sql/003_views.sql`, `004_points_adjustments.sql`, `002_assertions.sql`, `005_assertions_a22.sql`.
- [ ] No existing test deleted; no Python changed.
- [ ] Index and deck/report links updated.

## References

- Deck: `docs/slides/sql-schema-slides.html`
- Report: `docs/reports/sql-schema-deck.md`
- Rules: `docs/slides/RULES.md`
- SQL: `sql/001_schema.sql`, `sql/002_assertions.sql`, `sql/003_views.sql`, `sql/004_points_adjustments.sql`, `sql/005_assertions_a22.sql`
