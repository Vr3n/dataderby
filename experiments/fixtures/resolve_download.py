"""Resolve the real CSV filename for each competition from the download page.

The site redirects `/download/csv/<slug>` to a timezone-suffixed filename via a
`window.location` assignment. The suffix is not always the same shape, so resolve
it rather than guessing.
"""

from __future__ import annotations

import re
import time
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

PAGE = "https://fixturedownload.com/download/csv/{slug}"
LOCATION = re.compile(r'window\.location\s*=\s*"([^"]+)"')


def resolve(slug: str) -> str | None:
    request = urllib.request.Request(
        PAGE.format(slug=slug),
        headers={"User-Agent": "dataderby/0.1 (+fixture research)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", "replace")
    match = LOCATION.search(html)
    return match.group(1) if match else None


def main() -> None:
    for slug in SLUGS:
        try:
            target = resolve(slug)
            print(f"{slug:<26} -> {target}")
        except Exception as exc:  # noqa: BLE001 - probe
            print(f"{slug:<26} FAILED: {type(exc).__name__}: {exc}")
        time.sleep(1.0)


if __name__ == "__main__":
    main()
