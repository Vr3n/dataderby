"""Answer nine analyst questions against the warehouse and print the tables.

Covers champions and margins, dominance, home advantage, scoring trends,
best attack and defence, ratings versus titles, relegation, cross-league
comparison, and performance-versus-table gaps. Read-only: opens the
configured database without writing.

    uv run python scripts/analyze_epl.py --tournament 2

Needs the live warehouse file; never runs in CI.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

_DEFAULT_DB = Path("data/dataderby.duckdb")

_Q1 = """
WITH x AS (
    SELECT s.season_key, f.whoscored_team_name, f.points_overall,
           f.rank_overall
    FROM fact_standings_snapshot f
    JOIN competition_snapshot s USING (snapshot_id)
    WHERE s.whoscored_tournament_id = ?
)
SELECT a.season_key, a.whoscored_team_name, a.points_overall,
       (SELECT max(points_overall) FROM x b
        WHERE b.season_key = a.season_key AND b.rank_overall = 2),
       a.points_overall - (SELECT max(points_overall) FROM x b
        WHERE b.season_key = a.season_key AND b.rank_overall = 2)
FROM x a WHERE a.rank_overall = 1 ORDER BY a.season_key
"""

_Q2 = """
SELECT s.season_key, f.whoscored_team_name, f.points_overall,
       f.goal_difference_overall, f.won_overall
FROM fact_standings_snapshot f JOIN competition_snapshot s USING (snapshot_id)
WHERE s.whoscored_tournament_id = ? ORDER BY f.points_overall DESC LIMIT 8
"""

_Q3 = """
SELECT s.season_key,
       ROUND(100.0*sum(f.points_home)
             /NULLIF(sum(f.points_home + f.points_away), 0), 1),
       ROUND(100.0*sum(f.won_home)
             /NULLIF(sum(f.won_home + f.won_away + f.drawn_home + f.drawn_away), 0), 1)
FROM fact_standings_snapshot f JOIN competition_snapshot s USING (snapshot_id)
WHERE s.whoscored_tournament_id = ? GROUP BY 1 ORDER BY 1
"""

_Q4 = """
SELECT s.season_key,
       ROUND(sum(f.goals_for_overall)*1.0/sum(f.played_overall), 2),
       sum(f.goals_for_overall)
FROM fact_standings_snapshot f JOIN competition_snapshot s USING (snapshot_id)
WHERE s.whoscored_tournament_id = ? GROUP BY 1 ORDER BY 1
"""

_Q5 = """
WITH a AS (
    SELECT s.season_key, f.whoscored_team_name AS attack,
           f.goals_for_overall,
           row_number() OVER (
               PARTITION BY s.season_key ORDER BY f.goals_for_overall DESC) r
    FROM fact_standings_snapshot f JOIN competition_snapshot s USING (snapshot_id)
    WHERE s.whoscored_tournament_id = ?
),
d AS (
    SELECT s.season_key, f.whoscored_team_name AS defence,
           f.goals_against_overall,
           row_number() OVER (
               PARTITION BY s.season_key ORDER BY f.goals_against_overall ASC) r
    FROM fact_standings_snapshot f JOIN competition_snapshot s USING (snapshot_id)
    WHERE s.whoscored_tournament_id = ?
)
SELECT a.season_key, a.attack, a.goals_for_overall, d.defence,
       d.goals_against_overall
FROM a JOIN d ON a.season_key = d.season_key AND a.r = 1 AND d.r = 1
ORDER BY a.season_key DESC LIMIT 8
"""

_Q6 = """
WITH r AS (
    SELECT s.season_key, tm.whoscored_team_name AS top_rated,
           tm.rating_overall,
           row_number() OVER (
               PARTITION BY s.season_key ORDER BY tm.rating_overall DESC) rn
    FROM fact_team_snapshot tm JOIN competition_snapshot s USING (snapshot_id)
    WHERE s.whoscored_tournament_id = ?
),
c AS (
    SELECT s.season_key, f.whoscored_team_name AS champ
    FROM fact_standings_snapshot f JOIN competition_snapshot s USING (snapshot_id)
    WHERE s.whoscored_tournament_id = ? AND f.rank_overall = 1
)
SELECT r.season_key, r.top_rated, ROUND(r.rating_overall, 2), c.champ,
       CASE WHEN r.top_rated = c.champ THEN 'MATCH' ELSE '' END
FROM r JOIN c USING (season_key) WHERE r.rn = 1 ORDER BY 1
"""

_Q7 = """
SELECT s.season_key, f.rank_overall, f.whoscored_team_name, f.points_overall
FROM fact_standings_snapshot f JOIN competition_snapshot s USING (snapshot_id)
WHERE s.whoscored_tournament_id = ? AND f.rank_overall >= (
    SELECT max(f2.rank_overall) - 2 FROM fact_standings_snapshot f2
    JOIN competition_snapshot s2 USING (snapshot_id)
    WHERE s2.whoscored_tournament_id = ?
)
ORDER BY s.season_key DESC, f.rank_overall LIMIT 9
"""

_Q8 = """
SELECT s.whoscored_tournament_id AS tourn, count(*) AS teams,
       ROUND(avg(f.goals_for_overall*1.0/f.played_overall), 2) AS goals_pg,
       ROUND(avg(tm.rating_overall), 2) AS avg_rating
FROM v_latest_team_with_standings tm
JOIN competition_snapshot s USING (snapshot_id)
JOIN fact_standings_snapshot f USING (snapshot_id, whoscored_team_id)
GROUP BY 1 ORDER BY 1
"""

_Q9 = """
SELECT tm.whoscored_team_name, tm.ranking_summary_overall AS perf_rank,
       f.rank_overall AS table_rank,
       tm.ranking_summary_overall - f.rank_overall AS gap
FROM v_latest_team_with_standings tm
JOIN fact_standings_snapshot f USING (snapshot_id, whoscored_team_id)
JOIN competition_snapshot s USING (snapshot_id)
WHERE s.whoscored_tournament_id = ? AND s.season_key = ?
ORDER BY abs(tm.ranking_summary_overall - f.rank_overall) DESC LIMIT 8
"""


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=_DEFAULT_DB)
    parser.add_argument("--tournament", type=int, default=2)
    return parser.parse_args(argv)


def _show(title: str, rows: list[tuple[object, ...]], limit: int = 25) -> None:
    print(f"===== {title} =====")
    for row in rows[:limit]:
        print(row)
    print()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.db.exists():
        print(f"database does not exist: {args.db}", file=sys.stderr)
        return 1
    con = duckdb.connect(str(args.db), read_only=True)
    try:
        t = args.tournament
        _show("Q1 champions + margin", con.execute(_Q1, [t]).fetchall())
        _show("Q2 most dominant (top 8 by points)", con.execute(_Q2, [t]).fetchall())
        _show("Q3 home points share by season", con.execute(_Q3, [t]).fetchall(), limit=30)
        _show("Q4 avg goals/game per season", con.execute(_Q4, [t]).fetchall(), limit=30)
        _show(
            "Q5 best attack and defence (latest 8 seasons)",
            con.execute(_Q5, [t, t]).fetchall(),
        )
        _show(
            "Q6 best avg rating vs champion",
            con.execute(_Q6, [t, t]).fetchall(),
            limit=30,
        )
        _show("Q7 relegated (latest 3 seasons present)", con.execute(_Q7, [t, t]).fetchall())
        _show("Q8 leagues compared (latest snapshots)", con.execute(_Q8).fetchall())
        latest = con.execute(
            "SELECT max(season_key) FROM competition_snapshot WHERE whoscored_tournament_id = ?",
            [t],
        ).fetchone()
        season = str(latest[0]) if latest else ""
        _show(
            f"Q9 rating vs table gaps ({season})",
            con.execute(_Q9, [t, season]).fetchall(),
        )
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
