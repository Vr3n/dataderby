"""What exactly is the gate, and which knob gets past it?"""

from __future__ import annotations

import time

from curl_cffi import requests

BASE = "https://www.whoscored.com"
FEED = f"{BASE}/statisticsfeed/1/getteamstatistics"
STAGE_PAGE = (
    f"{BASE}/regions/206/tournaments/4/seasons/11213/stages/25662"
    "/teamstatistics/spain-laliga-2026-2027"
)
PARAMS = {
    "stageId": 25662,
    "category": "summaryteam",
    "subcategory": "all",
    "statsAccumulationType": "0",
    "field": "Overall",
    "sortBy": "Rating",
    "sortAscending": "false",
    "isCurrent": "true",
}


def show(label: str, r: object) -> None:
    body = r.content.lstrip(b"\xef\xbb\xbf").lstrip()
    kind = "JSON" if body[:1] in (b"{", b"[") else "GATE"
    print(f"\n--- {label}: HTTP {r.status_code} {len(r.content)}B {kind}")
    if kind == "GATE":
        print(f"    headers: {dict(list(r.headers.items())[:12])}")
        print(f"    body   : {body[:600]!r}")


def attempt(label: str, impersonate: str, headers: dict | None, url: str = FEED) -> None:
    s = requests.Session(impersonate=impersonate)
    if headers:
        s.headers.update(headers)
    try:
        r = s.get(url, params=PARAMS, timeout=20)
    except Exception as exc:  # noqa: BLE001 - probe
        print(f"\n--- {label}: ERROR {exc!r}")
        return
    show(label, r)


if __name__ == "__main__":
    base_headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": STAGE_PAGE,
    }
    rich_headers = {
        **base_headers,
        "Accept-Language": "en-US,en;q=0.9",
        "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    attempt("chrome + referer", "chrome", base_headers)
    time.sleep(10)
    attempt("chrome131 + rich headers", "chrome131", rich_headers)
    time.sleep(10)
    attempt("safari18_0 + rich headers", "safari18_0", rich_headers)
    print("\nsleeping 60s...")
    time.sleep(60)
    attempt("chrome + referer (after 60s idle)", "chrome", base_headers)
