# 0004 - Raw is the system of record

**Status:** accepted, 2026-10-21
**Evidence:** `docs/whoscored-decisions.md` section 5

## Context

The parsed tables are a lossy projection of the source. A parser bug, a schema
drift, or a changed canonicalisation rule can be repaired only if the bytes that
produced the row still exist. The DuckDB file is a derived store and may be
rebuilt.

## Decision

- Keep every captured page, standings view, and feed payload under
  `data/raw/<tournament>/<season>/<stage>/<observed_at>/`.
- Write with exclusive create, then `os.replace`; never overwrite an existing
  capture.
- Write a sidecar `.meta.json` with URL, status, content type, SHA-256, byte
  count, and attempt.
- Keep `data/` git-ignored. Raw payloads are never committed or redistributed.
- Back up `data/raw/`, not the `.duckdb` file, as the primary recovery path.
- Replay from raw into a scratch database and compare the content map; ids may
  differ.

## Consequences

- A parser repair can be proved against the original bytes.
- A failed publish leaves the raw evidence intact.
- The database can be rebuilt without re-fetching.
- A backup drill is a required v1 gate, not an optional nicety.

## Rejected alternatives

- **Commit the raw captures to Git.** Violates the local/private,
  non-redistributed posture.
- **Back up only DuckDB.** Loses the ability to repair a parser or canonical
  version.
- **Overwrite on retry.** Destroys the evidence that a second observation
  happened.
