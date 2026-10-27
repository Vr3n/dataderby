"""Dump #stages dropdown options (value + label) for given season URLs."""

from __future__ import annotations

import argparse
import json

_JS = """
() => Array.from(document.querySelectorAll('#stages option')).map((o) => ({
  value: o.value, label: o.textContent.trim()
}))
"""


def main(argv: list[str] | None = None) -> int:
    from patchright.sync_api import sync_playwright

    parser = argparse.ArgumentParser()
    parser.add_argument("urls", nargs="+")
    args = parser.parse_args(argv)
    out: dict[str, object] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.route("**/*fingerprint*", lambda route: route.abort())
            for url in args.urls:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(1500)
                out[url] = page.evaluate(_JS)
        finally:
            browser.close()
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
