-- P2 stage identity and canonical cutover. One canonical row per stage, one
-- mapping row per source, plus nullable canonical id columns on the header
-- and both fact tables. Nullable on purpose: the backfill fills old rows,
-- publish fills new rows, and assertions A23/A24 refuse rows that resolve to
-- nothing. No existing column is touched.

CREATE TABLE IF NOT EXISTS dim_stage (
    dataderby_stage_id VARCHAR PRIMARY KEY,
    tournament_name    VARCHAR NOT NULL,
    season_key         VARCHAR NOT NULL CHECK (season_key LIKE '____-____'),
    stage_code         VARCHAR NOT NULL,
    canonical_name     VARCHAR NOT NULL,
    first_seen_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at         TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE (tournament_name, season_key, stage_code)
);

CREATE TABLE IF NOT EXISTS stage_source_key (
    dataderby_stage_id   VARCHAR NOT NULL REFERENCES dim_stage(dataderby_stage_id),
    source               VARCHAR NOT NULL,
    source_tournament_id VARCHAR NOT NULL,
    source_season_id     VARCHAR NOT NULL,
    source_stage_id      VARCHAR NOT NULL,
    PRIMARY KEY (source, source_tournament_id, source_season_id, source_stage_id),
    UNIQUE (dataderby_stage_id, source)
);

ALTER TABLE competition_snapshot ADD COLUMN IF NOT EXISTS dataderby_stage_id VARCHAR;
ALTER TABLE fact_team_snapshot ADD COLUMN IF NOT EXISTS dataderby_team_id VARCHAR;
ALTER TABLE fact_standings_snapshot ADD COLUMN IF NOT EXISTS dataderby_team_id VARCHAR;
