-- P10 points adjustments. A deduction lowers the reported overall total below
-- 3*won + drawn, so it cannot be derived from the split tables. The view keeps
-- the reported value and shows the arithmetic gap instead of rewriting either
-- side. Only the overall total is checked: a deduction applies to the overall
-- table, not to the home and away splits.

CREATE OR REPLACE VIEW v_points_adjustments AS
SELECT
    s.snapshot_id,
    s.observed_at,
    s.accepted_at,
    s.whoscored_tournament_id,
    s.whoscored_season_id,
    s.whoscored_stage_id,
    s.season_key,
    s.run_id,
    f.whoscored_team_id,
    f.whoscored_team_name,
    f.won_overall,
    f.drawn_overall,
    f.points_overall AS points_reported,
    3 * f.won_overall + f.drawn_overall AS points_expected,
    f.points_overall - (3 * f.won_overall + f.drawn_overall) AS points_adjustment
FROM competition_snapshot AS s
JOIN fact_standings_snapshot AS f USING (snapshot_id)
WHERE f.points_overall IS NOT NULL
  AND f.won_overall IS NOT NULL
  AND f.drawn_overall IS NOT NULL
  AND f.points_overall < 3 * f.won_overall + f.drawn_overall
ORDER BY
    s.whoscored_tournament_id,
    s.whoscored_season_id,
    s.whoscored_stage_id,
    s.observed_at,
    f.whoscored_team_id;
