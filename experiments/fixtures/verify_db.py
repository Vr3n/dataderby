"""Spot-check the stored fixture calendar.

Run: uv run python experiments/fixtures/verify_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))

from dataderby.fixtures.store import connect  # noqa: E402

CHECKS = (
    ("fixtures", "SELECT count(*) FROM fixtures"),
    ("competitions", "SELECT count(*) FROM competitions"),
    ("ist_offset_violations", "SELECT count(*) FROM fixtures WHERE kickoff_ist NOT LIKE '%+05:30'"),
    (
        "played_without_score",
        "SELECT count(*) FROM fixtures WHERE status = 'played' "
        "AND (home_score IS NULL OR away_score IS NULL)",
    ),
    (
        "scheduled_with_score",
        "SELECT count(*) FROM fixtures WHERE status = 'scheduled' "
        "AND (home_score IS NOT NULL OR away_score IS NOT NULL)",
    ),
    (
        "duplicate_match_numbers",
        "SELECT count(*) FROM (SELECT competition_key, season, match_number FROM fixtures "
        "GROUP BY 1, 2, 3 HAVING count(*) > 1)",
    ),
)


def main() -> None:
    connection = connect(Path("data/fixtures.sqlite3"))
    try:
        for label, sql in CHECKS:
            print(f"{label:<26} {connection.execute(sql).fetchone()[0]}")
        print("\nunicode sample")
        for row in connection.execute(
            "SELECT home_team, venue, kickoff_ist FROM fixtures "
            "WHERE home_team LIKE '%Fenerbah%' OR home_team LIKE '%Bayern%' "
            "ORDER BY home_team LIMIT 4"
        ):
            print(f"  {row['home_team']!r:<28} {row['venue']!r:<40} {row['kickoff_ist']}")
    finally:
        connection.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
