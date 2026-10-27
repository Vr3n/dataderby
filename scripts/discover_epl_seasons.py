"""Discover EPL season and stage ids from the WhoScored tournament page.

Opens the Premier League tournament page in one headed browser, reads the
``#seasons`` dropdown (option value holds the season address, label holds the
season name), then visits each season and records the selected stage ``show``
link plus every stage tab. Output is JSON on stdout; nothing is written.

    uv run python scripts/discover_epl_seasons.py

Needs the live source and a browser, so this never runs in CI.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

_SEASONS_JS = """
() => Array.from(document.querySelectorAll('#seasons option')).map((o) => ({
  value: o.value, label: o.textContent.trim()
}))
"""

_STAGE_JS = """
() => ({
  selected: document.querySelector('#sub-navigation a.selected')?.href ?? null,
  tabs: Array.from(document.querySelectorAll('#sub-navigation a')).map((a) => ({
    href: a.href, text: a.textContent.trim()
  })),
  stages: Array.from(document.querySelectorAll('#stages option')).map((o) => o.textContent.trim())
})
"""

_TOURNAMENT_URL = "https://www.whoscored.com/regions/252/tournaments/2"
_STAGE_ID_RE = re.compile(r"/stages/(\d+)/")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tournament-url", default=_TOURNAMENT_URL)
    parser.add_argument("--timeout-ms", type=int, default=45_000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    from patchright.sync_api import sync_playwright

    args = _parse_args(argv)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.route("**/*fingerprint*", lambda route: route.abort())
            page.goto(args.tournament_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
            page.wait_for_timeout(2_000)
            seasons = page.evaluate(_SEASONS_JS)
            if not isinstance(seasons, list) or not seasons:
                print("no seasons in dropdown", file=sys.stderr)
                return 1
            out: list[dict[str, object]] = []
            for entry in seasons:
                if not isinstance(entry, dict):
                    continue
                season_url = f"https://www.whoscored.com{entry.get('value', '')}"
                label = str(entry.get("label", ""))
                page.goto(season_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
                page.wait_for_timeout(1_500)
                info = page.evaluate(_STAGE_JS)
                if not isinstance(info, dict):
                    info = {}
                selected = str(info.get("selected") or "")
                match = _STAGE_ID_RE.search(selected)
                out.append(
                    {
                        "season_label": label,
                        "season_url": season_url,
                        "show_url": selected,
                        "stage_id": int(match.group(1)) if match else None,
                        "tabs": info.get("tabs", []),
                        "stages": info.get("stages", []),
                    }
                )
        finally:
            browser.close()
    print(json.dumps(out, indent=2))
    missing = [row["season_label"] for row in out if not row["stage_id"]]
    if missing:
        print(f"no stage id for: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
