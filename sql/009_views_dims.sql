-- P2 consumer cutover: expose the canonical identity in the latest views.
--
-- Additive only. No existing column is removed or renamed; every new column is
-- appended. Existing rows keep their values, so readers see the same numbers
-- plus one canonical id and one canonical name per team row. History,
-- freshness, clock, delta, and adjustments views are untouched.

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
    f.* EXCLUDE (snapshot_id),
    d.canonical_name AS canonical_team_name
FROM latest AS h
JOIN fact_team_snapshot AS f USING (snapshot_id)
LEFT JOIN dim_team AS d ON d.dataderby_team_id = f.dataderby_team_id
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
    f.* EXCLUDE (snapshot_id),
    d.canonical_name AS canonical_team_name
FROM latest AS h
JOIN fact_standings_snapshot AS f USING (snapshot_id)
LEFT JOIN dim_team AS d ON d.dataderby_team_id = f.dataderby_team_id
WHERE h.snapshot_rank = 1
ORDER BY
    h.whoscored_tournament_id,
    h.whoscored_season_id,
    h.whoscored_stage_id,
    f.whoscored_team_id;


CREATE OR REPLACE VIEW v_latest_team_with_standings AS
SELECT
    t.*,
    s.* EXCLUDE (snapshot_id, whoscored_team_id, whoscored_team_name, dataderby_team_id)
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
    d.canonical_name AS canonical_team_name,
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
LEFT JOIN dim_team AS d ON d.dataderby_team_id = f.dataderby_team_id
ORDER BY
    s.whoscored_tournament_id,
    s.whoscored_season_id,
    s.whoscored_stage_id,
    f.whoscored_team_id,
    s.observed_at;
