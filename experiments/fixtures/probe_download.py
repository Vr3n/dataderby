"""Probe fixturedownload.com CSV exports for all v1 competitions.

Run: uv run --no-project python experiments/fixtures/probe_download.py
"""

from __future__ import annotations

import csv
import io
import time
import urllib.request
from dataclasses import dataclass

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

BASE = "https://fixturedownload.com/download/{slug}-IndiaStandardTime.csv"


@dataclass(frozen=True)
class Summary:
    slug: str
    status: int
    headers: tuple[str, ...]
    rows: int
    rounds: int
    played: int
    scheduled: int
    match_numbers: int


def fetch(slug: str) -> tuple[int, bytes]:
    request = urllib.request.Request(
        BASE.format(slug=slug),
        headers={"User-Agent": "dataderby/0.1 (+fixture research)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, response.read()


def summarise(slug: str, body: bytes) -> Summary:
    text = body.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    headers = tuple(reader.fieldnames or ())
    played = sum(1 for row in rows if row.get("Result", "").strip() not in ("", "-"))
    numbers = {row.get("Match Number") for row in rows}
    rounds = {row.get("Round Number") for row in rows}
    return Summary(
        slug=slug,
        status=200,
        headers=headers,
        rows=len(rows),
        rounds=len(rounds),
        played=played,
        scheduled=len(rows) - played,
        match_numbers=len(numbers),
    )


def main() -> None:
    for slug in SLUGS:
        try:
            status, body = fetch(slug)
            summary = summarise(slug, body)
            print(
                f"{summary.slug:<26} status={status} rows={summary.rows:<4} "
                f"rounds={summary.rounds:<3} played={summary.played:<4} "
                f"scheduled={summary.scheduled:<4} unique_match_no={summary.match_numbers}"
            )
            print(f"  headers: {summary.headers}")
        except Exception as exc:  # noqa: BLE001 - probe
            print(f"{slug:<26} FAILED: {type(exc).__name__}: {exc}")
        time.sleep(1.0)


if __name__ == "__main__":
    main()
