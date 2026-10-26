# <Change title>

**Status:** in progress
**Date:** YYYY-MM-DD
**Issues:** #N
**Decision:** `docs/adr/NNNN-<slug>.md` (delete this line if there is no ADR)
**Commit:** `<sha>` (fill in when merged)

## Goal

One paragraph. What problem this solves, for whom, and what "done" means.

## What changed

| File | Change | Why |
|---|---|---|
| `path/to/file` | what changed | the reason, not a restatement of the diff |

## Design decisions

What was chosen and why. Include the constraint that forced the choice: a type,
a transaction boundary, a dependency rule, a platform branch.

### Rejected alternatives

- **Alternative.** Why it was not chosen. What would make it right later.

## Test matrix

| Test | Pins |
|---|---|
| `tests/test_x.py::test_y` | the behaviour, stated as a claim |

What the tests deliberately do **not** assert, and why that is the right level.

## Evidence

```text
$ uv run ruff format --check
...
$ uv run ruff check
...
$ uv run mypy main.py
...
$ uv run pytest -q
...
```

Include command output that a reviewer can reproduce. If a gate was not run, say
so here rather than implying it passed.

## Deviations and open items

- What did not land, and the issue that owns it.
- Any deviation from the plan, with the reason.
- Anything a reviewer might expect to be present and is not.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| what could go wrong | how the design or the runbook prevents it |

## Reviewer checklist

- [ ] The behaviour is tested at the level it lives.
- [ ] No existing test was deleted to make the suite pass.
- [ ] Configuration and paths are explicit, not assumed.
- [ ] Errors map to the documented exit codes or assertion ids.
- [ ] The index and links are updated.

## References

- Repo: `docs/reports/...`, `docs/adr/...`, `sql/...`
- External: link and the one-line reason it is relevant.
