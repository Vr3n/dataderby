"""Find a real entry point that lists regions and tournaments."""

from __future__ import annotations

import re
from collections import Counter

from src.dataderby.client import session

BASE = "https://www.whoscored.com"
CANDIDATES = [
    "/",
    "/tournaments",
    "/regions",
    "/regions/206/tournaments/4",
    "/regions/206/tournaments/4/seasons/11213/spain-laliga",
]
LINK = re.compile(r'/regions/(\d+)/tournaments/(\d+)/([a-z0-9-]+)')


def main() -> None:
    s = session()
    for path in CANDIDATES:
        resp = s.get(f"{BASE}{path}", timeout=30)
        body = resp.text.lstrip("\ufeff")
        links = LINK.findall(body)
        print(
            f"{path:55} {resp.status_code} {len(body):>7}B "
            f"links={len(links):>3} regions={len(Counter(r for r, _, _ in links)):>3} "
            f"gate={body.count('oo-sports.com') or body.count('Oddschecker')}"
        )
        for rid, tid, slug in dict.fromkeys(links[:40]):
            print(f"    region {rid:>4}  tournament {tid:>4}  {slug}")


if __name__ == "__main__":
    main()
