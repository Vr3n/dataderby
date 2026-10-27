# Open questions register

**Purpose:** one row per unanswered experiment or deferred decision, with the
owner, the status, the evidence link, and the decision it unblocks. A question
leaves this register only through a dated report, never by going quiet.

**Path note:** issue #8 asked for `docs/open-questions.md`, but the repository
rule keeps the `docs/` root to the index and the six folders, so the register
lives here in `research/`.

| Id | Question | Decides | Status (2026-10-27) | Evidence |
|---|---|---|---|---|
| E1 | Is `summaryteam/all` a sufficient probe? | whether probe-only scheduling is safe | open | `docs/research/whoscored-cadence.md` §1 |
| E2 | Does an unchanged table imply unchanged details? | the skip rule | open, needs a live matchday | `docs/research/whoscored-cadence.md` §2 |
| E3 | Are values corrected retroactively? | the correction policy and the A10 override | open | — |
| E4 | Is `team_id` stable across seasons? | crosswalk and identity design | open | — |
| E5 | Publication latency after a final whistle? | the schedule cadence and grace period | open, next matchday; provisional 36 h ceiling stands | `docs/research/whoscored-cadence.md` §3 |
| E6 | Does the gate become cookie-bound? | cookie refresh and request pacing | open | — |
| K1 | 2026/27 knockout stage ids | knockout coverage before the draw | **deferred**: stages do not exist yet; see the registry comment | `config/stages.toml`, issue #10 |

## Status note (2026-10-27)

The E5 windows named in the cadence note (2026-10-24 and 2026-10-25 IST)
passed with no recorded result. E5 moves to the next matchday; the
provisional schedule (06:00 IST daily, `+2 h`/`+6 h` post-match) stays in
force, and the 36-hour freshness ceiling stands until E5 reports p50/p95.
