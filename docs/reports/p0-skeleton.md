# P0 - Skeleton and gates

**Status:** complete
**Date:** 2026-10-21
**Plan:** `plans/v1-build-plan.md` §3

## Goal

A repository where the four quality gates run and pass before any WhoScored
ingestion logic exists.

## What changed

- Added the planned runtime dependencies:
  - `duckdb` 1.5.6
  - `pydantic` 2.14.1
- Added the planned dev-only dependency:
  - `hypothesis` 6.170.5
- `pytest`, `ruff`, and `mypy` were already present and remain in the dev group.
- `pyproject.toml` already carried the required tool configuration from the
  fixture slice:
  - Ruff line length 100, Python 3.12.
  - Mypy strict, `mypy_path = "src"`, `explicit_package_bases = true`.
  - Pytest `testpaths = ["tests"]` and the `live` marker.
- The project is already an installable `src/` package (`package = true`).
- `.gitignore` already excludes `data/`, DuckDB files, SQLite files, and tool
  caches. Raw research captures under `experiments/` are also excluded; the
  scripts and derived results remain committable.
- `main.py` and `src/dataderby/__init__.py` already exist.

## Deviation from the plan

The plan's P0 sketch imports `dataderby.cli` from `main.py`. That module is a
P8 deliverable. Creating it now would either be a dead import or a wrapper with
no behaviour. `main.py` therefore continues to delegate to the fixture CLI
until P8 creates the unified `dataderby.cli`; the `mypy main.py` gate passes
today and will be re-pointed in P8.

No `data/` directory is required for the gates. The local `data/` directory is
git-ignored.

## Verification

Run on 2026-10-21:

```text
uv run ruff format --check
31 files already formatted

uv run ruff check
All checks passed!

uv run mypy main.py
Success: no issues found in 1 source file

uv run pytest
27 passed in 5.95s
```

The test suite includes the existing fixture pipeline tests. Hypothesis is
installed and loaded as a pytest plugin, ready for P5.

## Exit

All four `AGENTS.md` gates are green, and the new dependencies resolve through
`uv.lock`. The fresh-clone condition is covered by the package layout and the
ignored `data/` directory; a separate clean-checkout run remains a CI task
because this repository has no CI yet.

## Next

P1: six ADRs and the validated stage registry.
