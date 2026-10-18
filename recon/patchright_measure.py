"""Measure intermittency: per fresh launch, does the doc pass CF AND does the
bootstrap summary feed return real JSON vs the soft gate?"""

from __future__ import annotations

import time

from patchright.sync_api import sync_playwright

PAGE = (
    "https://www.whoscored.com/regions/206/tournaments/4/seasons/11213"
    "/stages/25662/teamstatistics/spain-laliga-2026-2027"
)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"


def main() -> None:
    with sync_playwright() as pw:
        for attempt in range(5):
            browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            ctx = browser.new_context(user_agent=UA, locale="en-US")
            feed: list[str] = []

            def on_resp(r) -> None:  # noqa: ANN001
                if "statisticsfeed" in r.url:
                    b = r.body().lstrip(b"\xef\xbb\xbf").lstrip()
                    feed.append("JSON" if b[:1] in (b"{", b"[") else "gate")

            ctx.on("response", on_resp)
            page = ctx.new_page()
            page.goto(PAGE, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(6000)
            doc_blocked = "Attention Required" in page.title()
            rows = page.locator("#statistics-team-table-summary table tr").count()
            print(f"attempt {attempt}: doc_blocked={doc_blocked} grid_rows={rows} feed=[{','.join(feed)}]")
            browser.close()
            time.sleep(1)


if __name__ == "__main__":
    main()