"""Mirror the passing probe.py launch params, then dump real stats selectors."""

from __future__ import annotations

from patchright.sync_api import sync_playwright

PAGE = (
    "https://www.whoscored.com/regions/206/tournaments/4/seasons/11213"
    "/stages/25662/teamstatistics/spain-laliga-2026-2027"
)


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
        seen: list[str] = []

        def on_resp(r) -> None:  # noqa: ANN001
            if "statisticsfeed" in r.url or "stagestatfeed" in r.url:
                seen.append(f"{r.status} {r.url[:150]}")

        ctx.on("response", on_resp)
        page = ctx.new_page()
        page.goto(PAGE, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(6000)
        print("title:", page.title(), "blocked:", "Attention Required" in page.title())

        print("\nfeeds seen:", seen)
        for sel in [
            "a[href*='stage-team-stats']",
            "dl",
            "dl#field, #field",
            "[data-backbone-model-attribute='field']",
            "#stage-team-stats-options li",
            "li a[data-value]",
            "table",
            "#statistics-team-table-summary",
            ".tab a",
        ]:
            print(f"{sel:42}: {page.locator(sel).count()}")

        ids = page.evaluate("() => Array.from(document.querySelectorAll('[id]')).map(e=>e.id).filter(i=>/stat|field/i.test(i)).slice(0,80)")
        print("\nids stat/field:", ids)

        # siblings/bars near the summary table
        bars = page.evaluate("() => Array.from(document.querySelectorAll('[data-value]')).slice(0,30).map(e=>`<${e.tagName}> data-value=${e.getAttribute('data-value')} txt=${(e.textContent||'').trim().slice(0,20)}`).slice(0,30)")
        print("\ndata-value elts:", bars)
        browser.close()


if __name__ == "__main__":
    main()