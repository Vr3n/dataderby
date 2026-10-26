-- P7 consumer views. The latest views choose one snapshot per stage before
-- joining facts, so a team missing from the newest snapshot cannot leak in
-- from an older one. History views never use accepted_at as the ordering clock.
-- Timestamps are TIMESTAMP WITH TIME ZONE: one instant, stored in UTC. The
-- session still defaults to UTC, but the type carries the guarantee. Local
-- renderings are presentation only; v_snapshot_clock at the end shows both.

CREATE OR REPLACE VIEW v_latest_team_state AS
WITH latest AS (
    SELECT
        *,
        row_number() OVER (
            PARTITION BY
                whoscored_tournament_id,
                whoscored_season_id,
                whoscored_stage_id
            ORDER BY observed_at DESC, accepted_at DESC, snapshot_id DESC
        ) AS snapshot_rank
    FROM competition_snapshot
)
SELECT
    h.* EXCLUDE (snapshot_rank),
    f.* EXCLUDE (snapshot_id)
FROM latest AS h
JOIN fact_team_snapshot AS f USING (snapshot_id)
WHERE h.snapshot_rank = 1
ORDER BY
    h.whoscored_tournament_id,
    h.whoscored_season_id,
    h.whoscored_stage_id,
    f.whoscored_team_id;


CREATE OR REPLACE VIEW v_latest_standings AS
WITH latest AS (
    SELECT
        *,
        row_number() OVER (
            PARTITION BY
                whoscored_tournament_id,
                whoscored_season_id,
                whoscored_stage_id
            ORDER BY observed_at DESC, accepted_at DESC, snapshot_id DESC
        ) AS snapshot_rank
    FROM competition_snapshot
)
SELECT
    h.* EXCLUDE (snapshot_rank),
    f.* EXCLUDE (snapshot_id)
FROM latest AS h
JOIN fact_standings_snapshot AS f USING (snapshot_id)
WHERE h.snapshot_rank = 1
ORDER BY
    h.whoscored_tournament_id,
    h.whoscored_season_id,
    h.whoscored_stage_id,
    f.whoscored_team_id;


CREATE OR REPLACE VIEW v_latest_team_with_standings AS
SELECT
    t.*,
    s.* EXCLUDE (snapshot_id, whoscored_team_id, whoscored_team_name)
FROM v_latest_team_state AS t
LEFT JOIN fact_standings_snapshot AS s
    ON s.snapshot_id = t.snapshot_id
   AND s.whoscored_team_id = t.whoscored_team_id
ORDER BY
    t.whoscored_tournament_id,
    t.whoscored_season_id,
    t.whoscored_stage_id,
    t.whoscored_team_id;


CREATE OR REPLACE VIEW v_standings_history AS
SELECT
    s.snapshot_id,
    s.observed_at,
    s.accepted_at,
    s.whoscored_tournament_id,
    s.whoscored_season_id,
    s.whoscored_stage_id,
    f.whoscored_team_id,
    f.whoscored_team_name,
    f.rank_overall,
    f.points_overall,
    f.form_overall,
    f.rank_home,
    f.points_home,
    f.form_home,
    f.rank_away,
    f.points_away,
    f.form_away
FROM competition_snapshot AS s
JOIN fact_standings_snapshot AS f USING (snapshot_id)
ORDER BY
    s.whoscored_tournament_id,
    s.whoscored_season_id,
    s.whoscored_stage_id,
    f.whoscored_team_id,
    s.observed_at;


CREATE OR REPLACE VIEW v_snapshot_delta AS
WITH accepted AS (
    SELECT
        *,
        lag(snapshot_id) OVER stage_window AS previous_snapshot_id
    FROM competition_snapshot
    WINDOW stage_window AS (
        PARTITION BY
            whoscored_tournament_id,
            whoscored_season_id,
            whoscored_stage_id
        ORDER BY observed_at, snapshot_id
    )
),
ordered AS (
    SELECT
        a.snapshot_id,
        a.previous_snapshot_id,
        a.observed_at,
        a.accepted_at,
        a.whoscored_tournament_id,
        a.whoscored_season_id,
        a.whoscored_stage_id,
        f.whoscored_team_id,
        f.whoscored_team_name,
        f.apps_overall,
        f.summary_overall_goal,
        f.summary_overall_yellow_card,
        f.summary_overall_red_card,
        lag(a.snapshot_id) OVER team_window AS previous_team_snapshot_id,
        lag(f.apps_overall) OVER team_window AS previous_apps,
        lag(f.summary_overall_goal) OVER team_window AS previous_goal,
        lag(f.summary_overall_yellow_card) OVER team_window AS previous_yellow_card,
        lag(f.summary_overall_red_card) OVER team_window AS previous_red_card,
        lag(a.observed_at) OVER team_window AS previous_observed_at
    FROM accepted AS a
    JOIN fact_team_snapshot AS f USING (snapshot_id)
    WINDOW team_window AS (
        PARTITION BY
            a.whoscored_tournament_id,
            a.whoscored_season_id,
            a.whoscored_stage_id,
            f.whoscored_team_id
        ORDER BY a.observed_at, a.snapshot_id
    )
)
SELECT
    snapshot_id,
    previous_snapshot_id,
    observed_at,
    previous_observed_at,
    accepted_at,
    whoscored_tournament_id,
    whoscored_season_id,
    whoscored_stage_id,
    whoscored_team_id,
    whoscored_team_name,
    apps_overall,
    summary_overall_goal,
    summary_overall_yellow_card,
    summary_overall_red_card,
    previous_apps,
    previous_goal,
    previous_yellow_card,
    previous_red_card,
    apps_overall - previous_apps AS d_apps,
    summary_overall_goal - previous_goal AS d_goal,
    summary_overall_yellow_card - previous_yellow_card AS d_yellow_card,
    summary_overall_red_card - previous_red_card AS d_red_card,
    (apps_overall - previous_apps) < 0 AS is_correction
FROM ordered
WHERE previous_team_snapshot_id IS NOT NULL
  AND previous_team_snapshot_id = previous_snapshot_id
ORDER BY
    whoscored_tournament_id,
    whoscored_season_id,
    whoscored_stage_id,
    whoscored_team_id,
    observed_at;


CREATE OR REPLACE VIEW v_pipeline_freshness AS
WITH stages AS (
    SELECT
        whoscored_tournament_id,
        whoscored_season_id,
        whoscored_stage_id
    FROM pipeline_checkpoint
    UNION
    SELECT
        whoscored_tournament_id,
        whoscored_season_id,
        whoscored_stage_id
    FROM competition_snapshot
    UNION
    SELECT
        whoscored_tournament_id,
        whoscored_season_id,
        whoscored_stage_id
    FROM ingestion_run
),
accepted AS (
    SELECT
        whoscored_tournament_id,
        whoscored_season_id,
        whoscored_stage_id,
        count(*) AS accepted_snapshots
    FROM competition_snapshot
    GROUP BY
        whoscored_tournament_id,
        whoscored_season_id,
        whoscored_stage_id
)
SELECT
    s.whoscored_tournament_id,
    s.whoscored_season_id,
    s.whoscored_stage_id,
    c.last_probe_at,
    c.last_success_at,
    CASE
        WHEN c.last_success_at IS NULL THEN NULL
        ELSE greatest(
            0,
            date_diff(
                'second',
                c.last_success_at,
                current_timestamp
            )
        )
    END AS age_seconds,
    c.last_outcome,
    coalesce(c.attempt_count, 0) AS attempt_count,
    coalesce(a.accepted_snapshots, 0) AS accepted_snapshots,
    c.last_committed_fingerprint
FROM stages AS s
LEFT JOIN pipeline_checkpoint AS c USING (
    whoscored_tournament_id,
    whoscored_season_id,
    whoscored_stage_id
)
LEFT JOIN accepted AS a USING (
    whoscored_tournament_id,
    whoscored_season_id,
    whoscored_stage_id
)
ORDER BY
    s.whoscored_tournament_id,
    s.whoscored_season_id,
    s.whoscored_stage_id;

-- Presentation only: one row per snapshot, the instant rendered in UTC and in
-- the operator's local zone. Storage stays TIMESTAMPTZ; this view is a lens,
-- not a second copy. A different zone is a one-line change here, or an
-- expression in the consumer's query (observed_at AT TIME ZONE 'Europe/London').
CREATE OR REPLACE VIEW v_snapshot_clock AS
SELECT
    snapshot_id,
    whoscored_tournament_id,
    whoscored_season_id,
    whoscored_stage_id,
    observed_at                             AS observed_at_utc,
    observed_at AT TIME ZONE 'Asia/Kolkata' AS observed_at_ist,
    accepted_at                             AS accepted_at_utc,
    accepted_at AT TIME ZONE 'Asia/Kolkata' AS accepted_at_ist
FROM competition_snapshot
ORDER BY observed_at DESC, accepted_at DESC, snapshot_id DESC;
