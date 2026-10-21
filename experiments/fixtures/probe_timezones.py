"""Compare the UTC and IndiaStandardTime exports for every competition.

If a competition has no IST export we fall back to UTC and convert locally, so the
probe records which path applies where.
"""

from __future__ import annotations

import csv
import io
import time
import urllib.error
import urllib.request

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

BASE = "https://fixturedownload.com/download/{slug}-{tz}.csv"


def probe(slug: str, tz: str) -> tuple[int, int, str]:
    request = urllib.request.Request(
        BASE.format(slug=slug, tz=tz),
        headers={"User-Agent": "dataderby/0.1 (+fixture research)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, 0, ""
    text = body.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    first = rows[0]["Date"] if rows else ""
    return 200, len(rows), first


def main() -> None:
    for slug in SLUGS:
        utc_status, utc_rows, utc_first = probe(slug, "UTC")
        ist_status, ist_rows, ist_first = probe(slug, "IndiaStandardTime")
        print(
            f"{slug:<26} UTC={utc_status}/{utc_rows:<4} {utc_first:<20} "
            f"IST={ist_status}/{ist_rows:<4} {ist_first}"
        )
        time.sleep(1.0)


if __name__ == "__main__":
    main()
