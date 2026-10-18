"""Can Patchright's stealth Chromium load the blocked stage page, and does the
fingerprint JS issue the cookies that unlock the statistics feed?"""

from __future__ import annotations

import json
import time

from curl_cffi import requests
from patchright.sync_api import sync_playwright

PAGE = (
    "https://www.whoscored.com/regions/206/tournaments/4/seasons/11213"
    "/stages/25662/teamstatistics/spain-laliga-2026-2027"
)
FEED = "https://www.whoscored.com/statisticsfeed/1/getteamstatistics"


def main() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = ctx.new_page()
        page.goto(PAGE, wait_until="domcontentloaded", timeout=45000)
        time.sleep(6)
        title = page.title()
        print("title:", title)
        print("url  :", page.url)
        blocked = "Attention Required" in title or "Sorry, you have been blocked" in page.content()
        print("blocked:", blocked)
        if blocked:
            browser.close()
            return

        # Did the summary grid render? That would prove the feed call passed.
        for sel in ["#statistics-team-table-summary", "#top-team-stats-summary-grid"]:
            n = page.locator(sel).count()
            print(f"locator {sel}: {n}")
        rows = page.locator("table tr").count()
        print("table rows:", rows)

        cookies = ctx.cookies()
        jar = {c["name"]: c["value"] for c in cookies}
        print("cookies:", sorted(jar))

        # Reuse the browser cookies in curl_cffi against the feed.
        s = requests.Session(impersonate="chrome")
        s.headers.update(
            {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "en-US,en;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": PAGE,
            }
        )
        for c in cookies:
            try:
                s.cookies.set(c["name"], c["value"], domain=c.get("domain") or ".whoscored.com", path=c.get("path") or "/")
            except Exception:  # noqa: BLE001
                pass
        r = s.get(
            FEED,
            params={
                "stageId": 25662,
                "category": "summaryteam",
                "subcategory": "all",
                "statsAccumulationType": "0",
                "field": "Overall",
            },
            timeout=25,
        )
        b = r.content.lstrip(b"\xef\xbb\xbf").lstrip()
        print("feed via browser cookies:", r.status_code, len(r.content), "JSON" if b[:1] in (b"{", b"[") else "GATE")
        if b[:1] in (b"{", b"["):
            d = json.loads(r.text.lstrip("\ufeff"))
            print("teams", len(d["teamTableStats"]), "statColumns", d["statColumns"])
        browser.close()


if __name__ == "__main__":
    main()