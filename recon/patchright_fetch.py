"""Capture the site's own feed request headers, then try a faithful page.fetch
(echo and modified subcategory) to see if in-page fetches can now pass."""

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
        real_hdrs: dict | None = None
        real_url: str | None = None

        def on_req(r) -> None:  # noqa: ANN001
            nonlocal real_hdrs, real_url
            if "statisticsfeed" in r.url and real_url is None:
                real_url = r.url
                real_hdrs = r.headers

        ctx.on("request", on_req)
        page = ctx.new_page()
        page.goto(PAGE, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(6000)
        print("blocked:", "Attention Required" in page.title())
        print("site feed url:", real_url)
        print("site feed req headers:", {k: v for k, v in (real_hdrs or {}).items()})

        # echo fetch of the same URL the site used
        # Rebuild the site's OWN header set (drop cookie; credentials include it later)
        hdrs = {
            k: v for k, v in (real_hdrs or {}).items()
            if k.lower() not in ("cookie", "content-length", "host", "content-type")
        }

        code = """
        async (url, headers) => {
          try {
            const r = await fetch(url, {method: 'GET', headers: headers, credentials: 'include'});
            const t = await r.text();
            return {status: r.status, len: t.length, head: t.slice(0, 90)};
          } catch (e) {
            return {err: String(e)};
          }
        }
        """
        res = page.evaluate(code, {"url": real_url, "headers": hdrs})
        print("\necho fetch (full headers):", res)

        if real_url:
            alt = real_url.replace("subcategory=all", "subcategory=defensive")
            res2 = page.evaluate(code, {"url": alt, "headers": hdrs})
            print("modified->defensive (full headers):", res2)
        browser.close()


if __name__ == "__main__":
    main()