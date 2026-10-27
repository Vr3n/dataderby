-- P1 team identity. One canonical row per club, plus one mapping row per
-- source. The facts keep their whoscored_* columns; consumers join the
-- canonical id once P2 wires it. Backfill inserts source = 'whoscored' rows
-- for every distinct whoscored_team_id in fact_team_snapshot.

CREATE TABLE IF NOT EXISTS dim_team (
    dataderby_team_id VARCHAR PRIMARY KEY,
    canonical_name    VARCHAR NOT NULL,
    first_seen_at     TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at        TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE IF NOT EXISTS team_source_key (
    dataderby_team_id VARCHAR NOT NULL REFERENCES dim_team(dataderby_team_id),
    source            VARCHAR NOT NULL,
    source_team_id    VARCHAR NOT NULL,
    PRIMARY KEY (source, source_team_id),
    UNIQUE (dataderby_team_id, source)
);
