# P5 - Parse and canonicalise

**Status:** complete
**Date:** 2026-10-21
**Plan:** `plans/v1-build-plan.md` §8

## Goal

Turn the nine accepted feed payloads and the three standings views into one
20-team, 60-measure candidate, one 30-measure standings companion, and a
deterministic SHA-256 fingerprint.

The live fixture parser and its tests were left untouched; the new WhoScored
tests live in `tests/test_whoscored_parse.py` so the existing
`tests/test_parse.py` contract continues to run.

## What was built

| Module | Responsibility |
|---|---|
| `src/dataderby/parse.py` | Parse one feed body, join nine captures, enforce the team cohort and shared-measure ownership, and produce `Candidate`. |
| `src/dataderby/parse_standings.py` | Turn the captured page into one `StandingsTeamRow` per team with all 30 standings measures; provide the feed/standings team-set check. |
| `src/dataderby/canonical.py` | Sort rows and keys, encode compact UTF-8 JSON, and compute the SHA-256 fingerprint. |

### Feed parsing

`parse_capture(section, view, body)` is pure. It calls the existing
`parse_envelope` gate/schema check, then maps the source columns to warehouse
columns:

- section-owned measures become `<section>_<view>_<measure>`;
- `apps`, `rating`, and `shots_per_game` become shared `<measure>_<view>`
  columns;
- `ranking` stays under its section and view;
- a missing source field is `None`, never `0`;
- `name` must equal `teamName` when both are present;
- a non-finite numeric value is rejected.

`build_candidate(captures, spec)` requires exactly the nine section/view
captures, rejects duplicate or missing combinations, requires identical team-id
sets across all nine, and checks the count against `spec.expected_teams`.
Metadata (`tournamentId`, `isOpta`, team name) must be consistent.

The Summary row owns `apps`, `rating`, and `shotsPerGame`. Every other section
that supplies the same shared column is compared with Summary; a disagreement
raises `OwnershipMismatch` (A6). The resulting `TeamRow.measures` always has the
full 60-column contract, with `None` for missing values.

### Standings parsing

`parse_views(page, spec=None)` returns:

- an empty `StandingsCandidate` when the stage is declared without a league
  table; any table that leaked onto the page is ignored;
- an `IncompleteCohort` when a table is declared but no table was captured;
- one row per team with all 30 `STANDINGS_MEASURES`, sorted by
  `whoscored_team_id`.

It rejects a team that appears in only one or two splits and a team name that
changes between splits. `check_team_sets(candidate, standings)` enforces A18 when
both sides are present; the no-table case is intentionally not passed to it.

### Canonical bytes

`canonical_bytes(candidate, standings, version=1)` emits this shape:

```json
{
  "canonical_version": 1,
  "is_opta": true,
  "whoscored_tournament_id": 2,
  "teams": [
    {
      "whoscored_team_id": 100,
      "measures": {"apps_overall": 7, "...": null},
      "standings": {"rank_overall": 1, "...": null}
    }
  ]
}
```

Properties:

- teams are sorted by `whoscored_team_id`;
- object keys are sorted by `json.dumps(sort_keys=True)`;
- separators are compact; UTF-8 without a BOM;
- finite floats use Python's shortest `repr`; `None` is `null`;
- names, `paging`, presentation order, and `seasonId` are excluded;
- a populated standings side must have exactly the feed's team set;
- `fingerprint()` is the SHA-256 hex digest of the canonical bytes.

For a no-table stage, every team's `standings` value is `{}`; this keeps the
fingerprint shape stable without inventing rows.

## Goldens and tests

`tests/golden/expected.json` pins the canonical fingerprint of a synthetic
20-team, 60-measure, 30-standings fixture:

```text
sha256 = b4c2a0da02981e54f8abc09e165ae35e3cac7c4e6205f79f5cbcf8824aed0c2d
```

The fixture is synthetic because no source capture is committed. It exercises
the same 20 x 60 contract and the full 30-column standings companion; the note
in the JSON records that it is not source data.

`tests/test_whoscored_parse.py` covers:

- a complete synthetic 20-team candidate with all 60 measures;
- missing measure -> `None`;
- changed `statColumns` -> `SchemaDrift`;
- 19 teams -> `IncompleteCohort`;
- team-id set mismatch -> `IncompleteCohort`;
- shared `shotsPerGame` disagreement -> `OwnershipMismatch`;
- `name`/`teamName` disagreement -> `SourceParseError`;
- source ids and measure mapping.

`tests/test_standings.py` adds:

- 30-measure standings rows, sorted by team id;
- no-table stage -> zero rows even when a table is present;
- declared table missing -> `IncompleteCohort`;
- a team missing from one split and a changed team name;
- equal, differing, and empty team-set checks.

`tests/test_canonical.py` covers:

- payload shape, 60/30 measure counts, and name exclusion;
- row order, key order, measure changes, rank/form changes;
- `None`/float encoding;
- missing measures and standings/feed set mismatch;
- Hypothesis properties for float stability, row permutations, key
  permutations, and integer rank determinism;
- the committed golden fingerprint.

## Verification

Run on 2026-10-21:

```text
uv run ruff format --check
68 files already formatted

uv run ruff check
All checks passed!

uv run mypy main.py
Success: no issues found in 1 source file

uv run pytest
116 passed in 16.50s
```

The three new source modules also pass a direct
`uv run mypy src/dataderby/parse.py src/dataderby/parse_standings.py
src/dataderby/canonical.py` check.

## Open items

- The golden fixture is synthetic; the first real sweep must be compared with
  the parser's assumptions, especially `teamName`/`name`, `isOpta`, and the
  `ranking` shape.
- A15's name divergence is currently a parser error; the caller's assertion
  mapping is P6.
- A19/A20/A21 arithmetic and rank/form checks on standings are P6 validation,
  not P5 parsing.
- The no-table path is represented only by an optional `spec` argument; P6 must
  pass the configured stage and skip `check_team_sets` for those stages.
- Canonical version 1 is pinned only by the synthetic fingerprint; a real
  capture may expose a source representation that requires a deliberate version
  bump.
- The real 2026/27 captures are not committed. Raw payloads remain local and
  ignored.
- There is no CI; all gates are local.
