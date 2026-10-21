"""Print the fixture database inventory.

Run: uv run python experiments/fixtures/inventory.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path("data/fixtures.sqlite3")


def main() -> None:
    connection = sqlite3.connect(DB)
    try:
        print("objects")
        for kind, name in connection.execute(
            "SELECT type, name FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ):
            print(f"  {kind:<6} {name}")

        print("\nfixtures by competition")
        for row in connection.execute(
            """
            SELECT c.competition_key, c.fixture_count, c.played_count,
                   count(f.fixture_key) AS stored
            FROM competitions AS c
            LEFT JOIN fixtures AS f ON f.competition_key = c.competition_key
            GROUP BY c.competition_key, c.fixture_count, c.played_count
            ORDER BY c.competition_key
            """
        ):
            print(f"  {row[0]:<18} source={row[1]:<4} stored={row[3]:<4} played={row[2]}")

        print("\nupcoming fixtures (all competitions)")
        print(" ", connection.execute("SELECT count(*) FROM v_upcoming_fixtures").fetchone()[0])
    finally:
        connection.close()


if __name__ == "__main__":
    main()
