# WhoScored team-stats decisions

**Decision date: 2026-10-20 · owner: project owner · status: accepted.**

These are the answers to the five questions in
`docs/whoscored-discovery-report.html` (slide 16). They supersede the
pre-decision wording in `plans/v1-implementation-plan.md` where the two differ.

---

## 1. Licence

**Accepted.** The `isOpta` data may be used for this project.

The `isOpta` flag stays in the record as provenance. It is not a licence
verdict and it is not a failure condition. The operational posture is unchanged:

- local and private;
- raw payloads are never committed;
- no public redistribution of the raw feed;
- no bulk historical scrape beyond the configured seasons.

If the project later publishes derived data, re-check the redistribution terms;
this decision covers the internal pipeline, not a public data product.

## 2. Home and away

**In scope.** The 60-column fact keeps all three splits. The Overall-only option
(B) is rejected. The home/away split is the analytical point of the dataset.

## 3. Standings

**In scope, at the same grain as the team stats.** Standings are not a separate
product and not a later add-on. They are the team's journey through the
competition in the current season and the context for under/overperformance.

Modelling decision:

- **Companion fact, same snapshot.** Add `fact_standings_snapshot`, one row per
  `(snapshot_id, team_id)`, published in the same transaction as
  `fact_team_snapshot`.
- **Do not widen the 60-column fact.** The 60 measures come from the JSON feed;
  standings come from the page. Keeping them as two facts at the same grain
  preserves the 60-column contract, keeps the knockout case (no table) clean, and
  still allows a one-row join on `(snapshot_id, team_id)`.
- **Join key is `tr[data-team-id]`.** It is the same numeric `teamId` the feed
  uses. Nothing joins on team name.
- **Three splits.** The page renders `Overall`, `Home` and `Away` as three
  client-side views of the same 10-column table. Capture all three.
- **`has_league_table` gates it.** League and group stages have a table; the
  measured knockout stage does not. A missing table is zero rows, not null
  measures.
- **The journey is the snapshot sequence.** No separate history table; the
  `(stage, team, observed_at)` series is the trajectory. Rank and points over
  snapshots answer "under/overperforming" at the results level. Explicit
  expected-points/xG analysis is still the xG feed, which remains out of v1.

Measured shape (EPL 2026-10-20, `experiments/whoscored/standings-25544.json`):

| Field | Rule |
|---|---|
| `rank` | `<span>` inside the first cell; permutation `1..N` |
| `team_id` | `tr[data-team-id]` |
| `team_name` | `a.team-link`, label only |
| `played, won, drawn, lost` | integers; `W+D+L=P` |
| `goals_for, goals_against` | integers |
| `goal_difference` | `GF−GA` |
| `points` | `3W+D` |
| `form` | rolling last six `w/d/l`; `len == min(P, 6)` |

Cross-split check on the capture: `home + away = overall` for
`P/W/D/L/GF/GA/Pts`, all 20 teams, no mismatches.

The fingerprint covers the 60 stats and the three standings views. A rank change
alone is a new snapshot.

## 4. Refresh cadence

**Not fixed yet.** The source has no timestamp, so the cadence is measured, not
read. Experiment E5 runs on the next matchday; the provisional schedule is a
06:00 IST daily heartbeat plus post-matchday sweeps at `last kickoff + 2 h` and
`+6 h`. Full evidence and method: `docs/whoscored-cadence.md`.

The important consequence for the build: a sweep is **page + nine feeds**, not
nine feeds. The page load supplies the token, the stage labels and the three
standings views.

## 5. Raw payloads

**Persist them.** Raw is the system of record, as the plan already says. Extend
the raw capture to include:

- the stage page HTML (`page/show`);
- the three standings views (`standings/Overall|Home|Away`);
- the nine feed payloads (`summary|defensive|offensive` × `Overall|Home|Away`).

The raw archive is the replay source. `data/` stays git-ignored.

---

## Consequences for the plan

1. The pre-decision sentence "league table: never, from this source" is wrong and
   has been removed. The page carries points, GD and form.
2. The token bootstrap was implicit. It is now explicit: page load first, then the
   nine feed calls with `Model-last-Mode`.
3. The 60-column fact is unchanged. The standings are a second fact at the same
   grain, with its own assertions.
4. The licence gate at M6 is satisfied. The remaining M6 work is the record and
   the backup/replay drill, not a legal decision.
5. E5 becomes the only open question that affects the schedule; it does not block
   P0–P6.