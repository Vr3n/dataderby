"""Check whether the site's IndiaStandardTime export is trustworthy.

Compares it row-by-row against the UTC export for the competitions that publish both.
"""

from __future__ import annotations

import csv
import io
import urllib.request
from datetime import datetime, timedelta

BASE = "https://fixturedownload.com/download/{slug}-{tz}.csv"
SLUGS = ["la-liga-2026", "serie-a-2026", "champions-league-2026", "epl-2026"]


def load(slug: str, tz: str) -> dict[str, datetime]:
    request = urllib.request.Request(
        BASE.format(slug=slug, tz=tz),
        headers={"User-Agent": "dataderby/0.1 (+fixture research)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        text = response.read().decode("utf-8-sig")
    rows = {}
    for row in csv.DictReader(io.StringIO(text)):
        rows[row["Match Number"]] = datetime.strptime(row["Date"], "%d/%m/%Y %H:%M")
    return rows


def main() -> None:
    for slug in SLUGS:
        utc = load(slug, "UTC")
        ist = load(slug, "IndiaStandardTime")
        deltas = sorted({ist[key] - utc[key] for key in utc if key in ist})
        print(f"{slug:<22} rows={len(utc):<4} distinct deltas={deltas}")


if __name__ == "__main__":
    main()
