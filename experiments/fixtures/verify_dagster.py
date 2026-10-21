"""Inspect the Dagster SQLite instance after a run.

Run: uv run python experiments/fixtures/verify_dagster.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

RUNS_DB = Path("data/dagster/history/history/runs.db")
SCHEDULES_DB = Path("data/dagster/history/schedules/schedules.db")


def main() -> None:
    print("runs.db        ", RUNS_DB.exists(), RUNS_DB)
    print("schedules.db   ", SCHEDULES_DB.exists(), SCHEDULES_DB)
    print("stray history/ ", Path("history").exists())

    if not RUNS_DB.exists():
        return
    connection = sqlite3.connect(RUNS_DB)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        ]
        print("tables         ", tables)
        print("run count      ", connection.execute("SELECT count(*) FROM runs").fetchone()[0])
        for row in connection.execute(
            "SELECT run_id, status, pipeline_name, start_time FROM runs "
            "ORDER BY start_time DESC LIMIT 3"
        ):
            print("  run:", row)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
