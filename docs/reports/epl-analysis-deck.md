# EPL analysis deck (the analyst's cut)

**Status:** complete
**Date:** 2026-10-27
**Deck:** `docs/slides/epl-analysis-deck.html`
**Queries:** `scripts/analyze_epl.py`

## Goal

Prove the warehouse answers real analyst questions in single queries, in a
deck a non-engineer can follow. Nine questions across three acts (the league,
the game, the tool), each answered from the live file, with the schema verdict
and an honest friction log at the end.

## What changed

| File | Change | Why |
|---|---|---|
| `scripts/analyze_epl.py` | Nine read-only analyst queries with `--tournament` | One runnable source for every number in the deck |
| `docs/slides/epl-analysis-deck.html` | 14-slide dark editorial deck, Athletic/Tifo styling, SVG charts, GSAP motion | Data storytelling the schema deck does not attempt |
| `scripts/README.md` | Script row | Repo rule: every script is listed |
| `docs/reports/epl-analysis-deck.md` | This report | AGENTS.md: one report per non-phase change |
| `docs/reports/README.md` | Index row | Keep the index complete |

No DDL, pipeline, or test changed. The deck reads the warehouse; it does not
touch it.

## Design decisions

- Dark chalkboard theme instead of the paper editorial one: Tifo's
  board-and-chalk idiom fits tactics-adjacent numbers (margins, gaps,
  over/underperformance), and the red/amber accents carry the only two
  colours a claim needs.
- Hand-built SVG charts with server-side geometry: every coordinate was
  generated from query output, so the pictures cannot drift from the numbers.
- Motion draws in reading order (bars grow, lines draw, dots pop, counts
  count) with the same reduced-motion and no-CDN fallbacks as the other decks.
- The close names the report, the queries file, and the one file a skeptic
  opens first (`sql/001_schema.sql`).

### Rejected alternatives

- **Chart library or canvas.** Extra dependency and CDN failure mode for
  static data; SVG plus GSAP already in the repo's deck vocabulary.
- **Hiding the friction.** The deck's most load-bearing slide is the
  friction log (narrow history view, per-team vs per-match units, playoff
  trap). A verdict without it reads like marketing.
- **In-progress season as evidence.** 2026/27 (8 games) appears with
  explicit weather-not-climate caveats, never in a trend claim.

## Test matrix

| Test | Pins |
|---|---|
| `scripts/analyze_epl.py --tournament 2` exits 0 | every deck number reproduces from the live file |
| Deck structure check | 14 slides, 14 notes, balanced divs |
| `node --check` on the inline script | script parses |
| Cross-checks | Q1 margins sum to table totals; Q4 2023/24 spike matches the 1,246-goal season; deduction rows match `v_points_adjustments` |

What this deliberately does not test: visual rendering at reference size
(manual step before presenting); statistical significance of the 8-game
2026/27 rows (labelled as noise).

## Evidence

```text
$ uv run python scripts/analyze_epl.py --tournament 2
EXIT:0   # Q1-Q9 tables, values match the deck
$ uv run ruff format --check
129 files already formatted
$ uv run ruff check
All checks passed!
$ uv run mypy main.py
Success: no issues found in 1 source file
```

Deck verification: 14 `<section class="slide">`, 14 `data-note`, balanced
divs, inline script passes `node --check`.

## Deviations and open items

- The deck's cross-league chart excludes the UCL bar from its ranking claim
  (36-team format, small sample) while still showing the value.
- Q7 uses the latest 3 seasons present rather than hard-coding years, so it
  stays correct as history grows.
- Player-level questions, xG, knockouts, and pre-2009 seasons are listed as
  triggers, not promises.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Numbers drift from warehouse | single script generates both; rerun before presenting |
| 2026/27 rows read as conclusions | every slide carrying them says 8 games |
| Theme drift from repo decks | tokens, chrome, and motion copied from the existing shell |

## Reviewer checklist

- [ ] Spot-check two chart values against `analyze_epl.py` output.
- [ ] Every slide has a presenter note; no page references.
- [ ] Deck links to this report; report links to the deck.
- [ ] Index updated.

## References

- Deck: `docs/slides/epl-analysis-deck.html`
- Rules: `docs/slides/RULES.md`
- Queries: `scripts/analyze_epl.py`
- Warehouse: `data/dataderby.duckdb` (read-only)
- Companion history: `docs/reports/all-leagues-history.md`
