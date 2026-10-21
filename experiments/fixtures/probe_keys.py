"""Check candidate natural keys for the fixtures table across all 12 competitions.

Run: uv run --no-project python experiments/fixtures/probe_keys.py
"""

from __future__ import annotations

import csv
import io
import time
import urllib.request
from collections import Counter

SLUGS = [
    "eredivisie-2026",
    "bundesliga-2026",
    "ligue-1-2026",
    "la-liga-2026",
    "serie-a-2026",
    "champions-league-2026",
    "conference-league-2026",
    "europa-league-2026",
    "epl-2026",
    "efl-league-two-2026",
    "efl-league-one-2026",
    "championship-2026",
]

BASE = "https://fixturedownload.com/download/{slug}-UTC.csv"


def load(slug: str) -> list[dict[str, str]]:
    request = urllib.request.Request(
        BASE.format(slug=slug),
        headers={"User-Agent": "dataderby/0.1 (+fixture research)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        text = response.read().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def duplicates(rows: list[dict[str, str]], key: tuple[str, ...]) -> int:
    counts = Counter(tuple(row[field] for field in key) for row in rows)
    return sum(1 for value in counts.values() if value > 1)


def main() -> None:
    for slug in SLUGS:
        rows = load(slug)
        by_match = duplicates(rows, ("Match Number",))
        by_pair = duplicates(rows, ("Home Team", "Away Team"))
        by_round_pair = duplicates(rows, ("Round Number", "Home Team", "Away Team"))
        dates = [row["Date"] for row in rows]
        print(
            f"{slug:<26} rows={len(rows):<4} dup(match)={by_match:<3} "
            f"dup(home,away)={by_pair:<3} dup(round,home,away)={by_round_pair:<3} "
            f"distinct_dates={len(set(dates))}"
        )
        time.sleep(1.0)


if __name__ == "__main__":
    main()
