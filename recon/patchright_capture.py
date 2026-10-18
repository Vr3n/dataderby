"""Drive the site's own UI to fetch all nine (section, view) responses and save
the full-precision JSON. View clicks are scoped to the active section's panel."""

from __future__ import annotations

import json
import pathlib
import time

from patchright.sync_api import sync_playwright

PAGE = (
    "https://www.whoscored.com/regions/206/tournaments/4/seasons/11213"
    "/stages/25662/teamstatistics/spain-laliga-2026-2027"
)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
SECTIONS = ["summary", "defensive", "offensive"]
VIEWS = ["Overall", "Home", "Away"]
OUT = pathlib.Path("recon/caps")


def parse_qs(url: str) -> dict:
    return dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&") if "=" in p)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="en-US")
        got: list[dict] = []

        def on_response(r) -> None:  # noqa: ANN001
            if "statisticsfeed" not in r.url:
                return
            body = r.body().lstrip(b"\xef\xbb\xbf").lstrip()
            kind = "JSON" if body[:1] in (b"{", b"[") else "gate"
            q = parse_qs(r.url)
            got.append({"sub": q.get("subcategory"), "field": q.get("field"), "kind": kind, "body": body.decode("utf-8", "replace")})

        ctx.on("response", on_response)
        page = ctx.new_page()
        page.goto(PAGE, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(5000)
        print("blocked:", "Attention Required" in page.title())

        for section in SECTIONS:
            if section != "summary":
                tab = page.locator(f"a[href='#stage-team-stats-{section}']")
                if tab.count():
                    tab.first.evaluate("el => el.click()")
                    page.wait_for_timeout(2500)  # let the section panel render
            panel = f"#stage-team-stats-{section}"
            for view in VIEWS:
                opt = page.locator(f"{panel} dl#field a[data-value='{view}']")
                if opt.count():
                    opt.first.evaluate("el => el.click()")
                    page.wait_for_timeout(1800)

        # summarize captured uniqueness across (subcategory, field)
        print(f"\ncaptured {len(got)} feed responses")
        seen: dict[tuple, str] = {}
        for g in got:
            seen[(g["sub"], g["field"])] = g["kind"]
        for k in sorted(seen, key=str):
            print(f"  sub={k[0]:10} field={k[1]:8} -> {seen[k]}")

        # save bodies per (subcategory, field); keep the latest JSON
        latest: dict[tuple, str] = {}
        for g in got:
            if g["kind"] == "JSON":
                latest[(g["sub"], g["field"])] = g["body"]
        for (sub, field), body in latest.items():
            fname = f"{sub}__{field}.json"
            (OUT / fname).write_text(body)
        print("\nsaved", len(latest), "json files under", OUT)
        time.sleep(0.5)
        browser.close()


if __name__ == "__main__":
    main()