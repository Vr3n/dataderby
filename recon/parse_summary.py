"""Show the server-rendered Summary/Overall table (no API involved).

The stage page renders this grid server-side, so we can inspect real
team-stats data even while the statistics feed is behind the fingerprint gate.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from curl_cffi import requests

URL = (
    "https://www.whoscored.com/regions/206/tournaments/4/seasons/11213"
    "/stages/25662/teamstatistics/spain-laliga-2026-2027"
)
TID = re.compile(r'class="team-link"[^>]*href="/teams/(\d+)/')
RANK_NAME = re.compile(r"^(?:(\d+)\.\s*)?(.+?)$")


class _Table(HTMLParser):
    """Collect plain-text header list and row list from one <table>."""

    def __init__(self) -> None:
        super().__init__()
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        self._h = self._d = False
        self._buf: list[str] = []
        self._row: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        if tag in ("th", "td"):
            setattr(self, f"_{tag[0]}", True)
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "th":
            self.headers.append("".join(self._buf).strip())
            self._h = False
        elif tag == "td":
            self._row.append("".join(self._buf).strip())
            self._d = False
        elif tag == "tr" and self._row:
            self.rows.append(self._row)
            self._row = []

    def handle_data(self, data: str) -> None:
        if self._h or self._d:
            self._buf.append(data)


def main() -> None:
    s = requests.Session(impersonate="chrome")
    r = s.get(URL, timeout=25)
    r.raise_for_status()
    body = r.text.lstrip("\ufeff")
    print(f"page {r.status_code} {len(body)}B")

    start = body.index('id="top-team-stats-summary-grid"')
    end = body.index("</table>", start) + len("</table>")
    p = _Table()
    p.feed(body[start:end])
    print("headers:", p.headers)

    table = body[start:end]
    for tr_idx, cell_row in enumerate(p.rows):
        tid = TID.search(table) if tr_idx == 0 else None
        name = RANK_NAME.match(cell_row[0])
        print(f"{tid.group(1) if tid else '----':>4} "
              f"rank={name.group(1) or '?':>2} "
              f"{name.group(2):<14} {cell_row}")


if __name__ == "__main__":
    main()