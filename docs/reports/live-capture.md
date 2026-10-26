# One real capture, and what it broke

**Status:** complete
**Date:** 2026-10-26
**Issue:** #5
**Commit:** this change (see `git log`)
**Follow-up:** #14 (browser feed transport)

## Goal

Replace the claim "the parser works" with evidence from real bytes.

Every parser test until now used synthetic payloads. They proved the code agreed
with the fixture, not that the fixture agreed with WhoScored. This change captures
one live stage, runs it through the real parser and the real assertions, and keeps a
redacted fixture so CI can reproduce the result.

It also did what real data usually does: it broke four assumptions.

## What changed

| File | Change | Why |
|---|---|---|
| `scripts/capture_live_stage.py` | New. One headed browser captures the page, standings, and nine feeds; writes a redacted fixture with per-file SHA-256 | the feed is bound to the browser session |
| `src/dataderby/page.py` | Token read from the inline bootstrap as well as `require` | `require` is `undefined` on the live page |
| `src/dataderby/page.py` | Standings toggle selector uses lower-case `data-source` | `view.title()` matched nothing, so every split was a copy of Overall |
| `src/dataderby/fetch.py` | URL contract: `category=summaryteam`, section in `subcategory`, split in `field`, plus the required parameters | the old URL returned the site's 404 shell |
| `src/dataderby/standings.py` | Form is lower-cased before validation | the page sends `WWWWWL`; the validator only accepted `wdl` |
| `src/dataderby/parse.py` | `name` may differ from `teamName`; `teamName` is canonical | `name` is "Man City", `teamName` is "Manchester City" |
| `tests/fixtures/whoscored/epl-2026-2027-25544/` | New. 9 feeds, 3 standings views, manifest | the real input |
| `tests/test_live_fixture.py` | New. 5 tests | checksums, redaction, cohort, publish, pinned fingerprint |
| `tests/test_page.py` | New. 3 token tests | the token path is now two-source |
| `tests/test_fetch.py` | URL contract updated | field/subcategory split |
| `tests/test_standings.py` | Uppercase form test | pins the normalisation |
| `tests/test_whoscored_parse.py` | "names must agree" replaced by "short name is accepted" | the old test asserted the wrong rule |
| `tests/fixtures/whoscored/README.md` | New | provenance and regeneration |

## Findings

### 1. The token is no longer on `require`

`require.config.params.site.gSiteHeaderValue` throws because `require` is
`undefined`. The value is still in the inline bootstrap:

```
gSiteHeaderValue: '4K1Xf6…'
```

`_token_from_html` reads it with a regex; the JS lookup remains as a fallback.

### 2. The feed is bound to the browser session

Calling `/statisticsfeed/1/getteamstatistics` over plain HTTP returns a 200 with a
776-byte HTML shell: "The page you requested does not exist". It is a 404 dressed as
200, wrapped in the fingerprint scripts:

```
oc-orchestrator-trace: {"FINGERPRINT":true,...}
```

The same endpoint returns JSON when called from the site's `/statistics` page with
`fetch(..., {credentials: 'include'})`. Browser cookies alone are not enough:
exporting the jar and the user agent to `curl_cffi` still gets the shell. The
verified session is the transport.

Consequence: `dataderby run` cannot fetch feeds yet. The CLI path is unchanged and
still uses `curl_cffi`; it will return `fetch_failed` against the live endpoint. This
is tracked as a follow-up issue, not silently ignored.

### 3. The standings toggles are lower-case

`a.option[data-source="Overall"]` matches nothing. The real values are
`overall`, `home`, `away`, `wide`. Because the code checked `if toggle.count()`,
it did not fail; it read the same table three times. The fixture exposed it in the
only way that matters: `home + away` did not equal `overall`, so A20 blocked the
publish.

After the fix, the real numbers for Manchester City are:

| Split | Played | Won | Points |
|---|---|---|---|
| Overall | 8 | 7 | 21 |
| Home | 4 | 4 | 12 |
| Away | 4 | 3 | 9 |

Home + away = overall. A20 passes.

### 4. `name` and `teamName` are different fields

The old parser raised when they disagreed. They always disagree on the live feed:

```
name:     "Man City"
teamName: "Manchester City"
```

`teamName` matches the standings table, so it is the canonical label. The short
`name` is ignored; the parse error is gone and a test now pins the behaviour.

## Design decisions

- **The fixture is a redacted extract, not a raw bundle.** Raw bundles stay in
  `data/raw` and are git-ignored. The fixture contains the feed bodies and the
  standings views, with a check that refuses tokens, cookies, and headers.
- **The capture tool is an operator script, not pipeline code.** It exists to produce
  evidence and fixtures. Wiring the browser transport into `run` is a separate
  decision with its own lifecycle concerns (browser reuse, pacing, retries).
- **The fingerprint is pinned.** A change to the fixture means the source content
  changed; updating the pin is a deliberate act, like updating a golden hash.

### Rejected alternatives

- **Commit the page HTML.** It is 500 KB, full of ads and session material, and the
  parser does not consume it.
- **Keep the synthetic fixture and skip the live run.** That is the status quo the
  issue exists to end.
- **Store the browser cookies in the fixture.** They are credentials.
- **Treat `name` as canonical.** It disagrees with the standings table and would
  break A15.

## Test matrix

| Test | Pins |
|---|---|
| `test_every_fixture_file_matches_its_manifest_checksum` | the fixture is byte-for-byte what the capture wrote |
| `test_the_fixture_contains_no_credentials_or_headers` | no token, cookie, or header leaked into the commit |
| `test_the_live_capture_forms_a_complete_twenty_team_candidate` | 20 teams, 60 measures each, real names |
| `test_the_live_capture_publishes_and_records_its_fingerprint` | A1–A21 pass; the stored fingerprint equals the computed one |
| `test_the_committed_fixture_is_pinned` | a deliberate content change is the only way the fingerprint moves |
| `test_reads_a_single_quoted_token…` / `…double_quoted…` / `…none…` | the token regex covers both quote styles and absence |
| `test_uppercase_form_is_normalised_to_lowercase` | the page's case does not reach storage |
| `test_short_name_is_accepted_when_it_differs_from_the_full_name` | `teamName` is canonical |
| `test_feed_url_contains_stage_and_category` | the URL carries `stageId`, `category`, `subcategory`, `field` |

What the tests do **not** do: hit WhoScored in CI. The live capture is an operator
step; CI consumes its output.

## Evidence

Capture:

```
$ uv run python scripts/capture_live_stage.py --stage epl-2026-2027 \
    --out tests/fixtures/whoscored/epl-2026-2027-25544
stage: epl-2026-2027 (25544)
standings: overall=20, home=20, away=20
feeds: 9 files
fixture: tests\fixtures\whoscored\epl-2026-2027-25544
teams in summary/overall: 20
```

Fixture:

```
12 files, 110 KB
summary/overall: 20 teams, 8 columns
fingerprint: ddd500267e1134f8df4506cb13d7efe8b5d02cbeaac082bd78ffdb3448cec5ea
```

Gates: `ruff format --check`, `ruff check`, and `mypy main.py` pass; the full suite
reports **201 passed**. CI runs the same gates on Ubuntu and Windows for the commit
that adds the fixture.

## Deviations and open items

- **`dataderby run` cannot fetch the live feed yet.** The browser transport is not
  wired into the pipeline; #14 tracks it. Until it lands, the CLI is honest but
  unusable against the live endpoint.
- **Replay was not run against a live raw bundle.** The fixture test publishes and
  compares the fingerprint, which is the same content guarantee, but the CLI
  `replay` path is still exercised only by synthetic bundles.
- **The fixture is source-derived data.** `docs/adr/0006-source-use.md` says raw
  payloads are never committed. This commit reads that as "raw bundles", not
  "redacted extracts", and the fixture README says so. The owner should confirm the
  reading if the repository is ever made public beyond its current audience.
- **The capture script uses fixed waits** (400 ms after a toggle, 6 s on the
  statistics page). They worked twice; they are not a synchronisation primitive. A
  future revision should wait on the table's contents changing.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Source changes again | the fixture test fails on the fingerprint; regenerate deliberately |
| Fixture contains a secret | the capture tool refuses to write forbidden markers; the test re-checks |
| Browser transport rots | one script, one place; the report records the exact session requirement |
| Someone "fixes" the pinned fingerprint to make CI pass | the pin is documented as a content change, not a flake |
| Selector silently matches nothing | the fixture's home+away=overall check catches it; a no-op toggle can no longer pass A20 |

## Reviewer checklist

- [ ] The fixture has no token, cookie, or header.
- [ ] The pinned fingerprint matches the committed files.
- [ ] `test_fetch.py` still asserts the URL contract, not an implementation detail.
- [ ] The old "names must agree" test is replaced, not deleted.
- [ ] The browser transport gap is tracked, not implied to work.

## References

- `docs/reports/p5-parse-canonical.md` — the synthetic-fixture open item this closes.
- `docs/adr/0004-raw-is-system-of-record.md` — raw bundles and replay.
- `docs/adr/0006-source-use.md` — the redaction posture.
- `scripts/capture_live_stage.py` — the capture tool.
- `tests/fixtures/whoscored/README.md` — fixture provenance.
