"""Which whoscored URLs actually serve the tournaments/seasons selects?"""

from __future__ import annotations

import re

from src.dataderby.client import session

BASE = "https://www.whoscored.com"
CANDIDATES = [
    "/regions/206",
    "/regions/206/",
    "/regions/206/spain-laliga",
    "/regions/206/tournaments",
    "/regions/206/tournaments/4/spain-laliga",
    "/regions/206/tournaments/4/seasons/11213/spain-laliga",
    "/regions/206/tournaments/4/seasons/11213/stages/25662/teamstatistics/spain-laliga-2026-2027",
]


def main() -> None:
    s = session()
    for path in CANDIDATES:
        try:
            resp = s.get(f"{BASE}{path}", timeout=30)
        except Exception as exc:  # noqa: BLE001 - probe
            print(f"{path:90} ERROR {exc!r}")
            continue
        body = resp.text.lstrip("\ufeff")
        print(
            f"{path:90} {resp.status_code} {len(body):>7}B "
            f"tourn={body.count('id="tournaments"'):>2} "
            f"seas={body.count('id="seasons"'):>2} "
            f"stageId={len(re.findall(r'stageId:', body)):>2} "
            f"blocked={'Attention Required' in body or 'Sorry, you have been blocked' in body}"
        )


if __name__ == "__main__":
    main()
