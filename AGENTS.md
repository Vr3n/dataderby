# Project Domain

This codebase is a Data-Engineering project which will `scrape` data from different sources.\
Then ingest into a columnar database.

1. Use python requests or

# Project Setup & Management.

This is a python project which uses `uv` as it's package manager.

Always check the `pyproject.toml` for installed packages. Never use `pip` or a `requirements.txt` file.

1. Install new package with `uv add <package_name>`.
2. Run the development commands with `uv run <command>`

If you are ever confused about `uv` check it's latest documentation.

When coding python, follow `The Zen of Python` strictly.

```
Beautiful is better than ugly.
Explicit is better than implicit.
Simple is better than complex.
Complex is better than complicated.
Flat is better than nested.
Sparse is better than dense.
Readability counts.
Special cases aren't special enough to break the rules.
Although practicality beats purity.
Errors should never pass silently.
Unless explicitly silenced.
In the face of ambiguity, refuse the temptation to guess.
There should be one-- and preferably only one --obvious way to do it.
Although that way may not be obvious at first unless you're Dutch.
Now is better than never.
Although never is often better than *right* now.
If the implementation is hard to explain, it's a bad idea.
If the implementation is easy to explain, it may be a good idea.
Namespaces are one honking great idea -- let's do more of those!
```

# Coding Conventions.

- Type-hint public functions and methods, including their return types.
- Use `pathlib` for path management. Don't use `os.path`.
- Prefer f-strings over `str.format()` or `%` formatting.
- Follow EAFP: handle exceptions rather than checking conditions up front.
- Write Google-style docstrings for every public function and method.
- Validate request bodies with Pydantic models.
- Embrace idiomatic Python like comprehensions, generators, and decorators.

## Documentation

Every implementation ships its documentation in the same commit. This is not
optional and there is no "small change" exemption for code.

- **A build phase** gets `docs/reports/pN-<slug>.md`.
- **A single change that is not a phase** gets `docs/reports/<slug>.md`.
- **An architectural or hard-to-reverse decision** gets
  `docs/adr/NNNN-<slug>.md`. The ADR records the decision and the rejected
  alternatives; the report records the implementation.
- **A change that spans several artifacts** also gets a one-page
  `docs/<slug>-summary.md`.
- Update the index (`docs/reports/README.md`) and any README link in the same
  commit.

A report is written for a co-worker who was not in the room, and must contain:

1. Goal, in one paragraph.
2. What changed, as a file → change → why table.
3. Design decisions and rejected alternatives.
4. Test matrix: what each test pins, and what it deliberately does not.
5. Evidence: the exact commands and their results.
6. Deviations and open items.
7. Risks and mitigations.
8. A reviewer checklist.
9. References, including any external source.

Start from [`docs/reports/TEMPLATE.md`](docs/reports/TEMPLATE.md). A change
without a report is not done.

## Quality Gates

A task is done only when all of these pass:

- `uv run ruff format` leaves the code unchanged.
- `uv run ruff check` reports no errors.
- `uv run mypy main.py` reports no errors.
- `uv run pytest` passes, with a test added for every new endpoint.

## Constraints

- Ask before adding any external dependency.
- Preserve the signature and response shape of existing endpoints.
- Don't use blocking I/O inside `async` functions.
- Keep existing tests intact, and fix the code to make them pass.
- Declare a task done only after the gates pass and docstrings are
  updated.
- Name the source in every source-derived identifier, name, URL or raw
  payload: `whoscored_stage_id`, `whoscored_url`, `fixturedownload_slug`.
  Never add a bare `source_*` field or variable. Derived values such as
  `row_hash` and `teams_in_feed` are exempt because they do not claim a
  source.

# Ignore

Treat everything in `.gitignore` as off-limits to read or edit. On top of
that, never open:

- Secrets and `.env` files
- Large data files unrelated to the current task
- Vendored or generated code
