# P2 - The contract

**Status:** complete
**Date:** 2026-10-21
**Plan:** `plans/v1-build-plan.md` §5

## Goal

One module owns the 60 fact columns, the 30 standings measures, the source's
expected `statColumns` order, and the ownership of values that repeat across
sections.

## Contract

`src/dataderby/contract.py` now declares:

- `SECTIONS` and `VIEWS`;
- `EXPECTED_STAT_COLUMNS`, keyed by `(section, view)`;
- `MEASURE_COLUMNS`, the 60 warehouse columns in schema order;
- `STANDINGS_MEASURES`, ten fields times three views;
- `OWNERSHIP` for the three shared base measures (`apps`, `shots_per_game`,
  `rating`);
- `WHOSCORED_TO_WAREHOUSE`, the source-to-warehouse base-name map;
- `measure_owner()`, which returns the owning section, `ranking`, or `shared`.

### Column naming

The measured contract corrects two names in the build plan:

- `shotsConcededPerGame` is **shots conceded**, not goals conceded. The
  warehouse name is `defensive_{view}_shots_conceded`.
- The defensive and offensive per-game fields use the source-faithful nouns
  `tackles`, `interceptions`, `fouls`, `offsides`, `shots_on_target`,
  `dribbles_won`, and `fouls_given` rather than carrying a redundant `_per_game`
  suffix. `summary_{view}_aerial_won_per_game` keeps its suffix because that is
  the measured summary contract.

The 60 columns are:

| Block | Count |
|---|---:|
| `apps_{view}` | 3 |
| `rating_{view}` | 3 |
| `shots_per_game_{view}` | 3 |
| `summary_{view}_*` | 18 |
| `defensive_{view}_*` | 15 |
| `offensive_{view}_*` | 9 |
| `ranking_{section}_{view}` | 9 |
| **Total** | **60** |

### Arithmetic

The plan's prose line `57 - 9 - 6 + 3 + 3 + 3 + 9 = 60` subtracts the duplicate
groups twice. The measured arithmetic is:

```text
57 raw statColumn entries
- 6 duplicate apps entries (2 x 3 views)
- 3 duplicate shotsPerGame entries (1 x 3 views)
= 48 unique entries
  42 section-owned + 3 apps + 3 shots_per_game
+ 3 rating + 9 ranking
= 60
```

`test_contract_arithmetic_counts_the_60_columns` derives those numbers from
`EXPECTED_STAT_COLUMNS`; it does not assert the total alone.

## Golden fixture

`tests/golden/stat_columns.json` contains only the nine measured `statColumns`
arrays. It does not contain rows, team names, or any raw payload. Raw captures
remain under the git-ignored `experiments/` and `data/` paths.

The test checks every `(section, view)` entry against the corresponding golden
capture, in order, and checks that all nine capture keys are present.

## Verification

`tests/test_contract.py` covers:

- exactly 60 unique warehouse columns;
- the nine golden captures and their order;
- exactly one owner for every measure, with the expected 18/15/9/9/9 split;
- `OWNERSHIP` contains only `apps`, `shots_per_game`, and `rating`;
- exactly 30 unique standings measures;
- the counted 57 - 6 - 3 = 48 -> 60 arithmetic;
- every source stat column has a warehouse name;
- unknown measure names are rejected.

Run on 2026-10-21:

```text
uv run ruff format --check
44 files already formatted

uv run ruff check
All checks passed!

uv run mypy main.py
Success: no issues found in 1 source file

uv run pytest
45 passed in 3.17s
```

## Open items

- The golden fixture is metadata, not a replay fixture. P5 will add the parser
  goldens and the checksum.
- The 60-column schema is not yet generated. P3 must import `MEASURE_COLUMNS` or
  prove that the SQL column list is identical to it.

## Next

P3: the six-table schema, DuckDB connection/transaction helpers, and constraint
tests.
