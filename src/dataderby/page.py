"""Live stage-page capture with Patchright."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from dataderby.contract import VIEWS, View
from dataderby.standings import RawStandingsRow

_TOKEN_RE = re.compile(r"gSiteHeaderValue\s*:\s*['\"]([^'\"]+)['\"]")

_STANDINGS_JS = """
() => {
  const table = document.querySelector('table[id^="standings-"]');
  if (!table) return [];
  return Array.from(table.querySelectorAll('tr[data-team-id]')).map((tr) => {
    const cells = Array.from(tr.querySelectorAll('td'));
    const first = cells[0];
    return {
      whoscored_team_id: Number(tr.getAttribute('data-team-id')),
      whoscored_team_name: first?.querySelector('a.team-link')?.innerText.trim() ?? '',
      rank: first?.querySelector('span')?.innerText.trim() ?? '',
      played: cells[1]?.innerText.trim() ?? '',
      won: cells[2]?.innerText.trim() ?? '',
      drawn: cells[3]?.innerText.trim() ?? '',
      lost: cells[4]?.innerText.trim() ?? '',
      goals_for: cells[5]?.innerText.trim() ?? '',
      goals_against: cells[6]?.innerText.trim() ?? '',
      goal_difference: cells[7]?.innerText.trim() ?? '',
      points: cells[8]?.innerText.trim() ?? '',
      form: cells[9]?.innerText.trim() ?? ''
    };
  });
}
"""

_TOKEN_JS = """
() => {
  try {
    return require.config.params.site.gSiteHeaderValue;
  } catch (error) {
    return null;
  }
}
"""

_STAGES_JS = """
() => Array.from(document.querySelectorAll('#stages option'))
  .map((option) => option.textContent.trim())
"""


@dataclass(frozen=True, slots=True)
class PageCapture:
    """The page HTML, token, labels, and raw standings rows from one load."""

    html: str
    token: str
    stages: tuple[str, ...]
    standings: dict[View, tuple[RawStandingsRow, ...]]
    captured_at: datetime
    url: str


def _rows_from_js(items: list[dict[str, Any]]) -> tuple[RawStandingsRow, ...]:
    return tuple(RawStandingsRow(**item) for item in items)


def _token_from_html(html: str) -> str | None:
    """Return ``gSiteHeaderValue`` from the page HTML, when it is present.

    The site used to expose the token through the AMD ``require`` object. On the
    live page in October 2026 that object is absent, but the inline bootstrap
    still contains the value. Reading both keeps the capture working whichever
    shape the page ships.

    Args:
        html: The document HTML.

    Returns:
        The token, or ``None`` when the page does not contain one.
    """
    match = _TOKEN_RE.search(html)
    return match.group(1) if match else None


def capture_page(url: str, *, timeout_ms: int = 45_000) -> PageCapture:
    """Load a WhoScored stage page in a headed Chromium and read the tables.

    Args:
        url: The stage's ``show`` URL.
        timeout_ms: Navigation and selector timeout.

    Returns:
        The page capture. ``standings`` is empty when the page has no league
        table, including knockout stages.

    Raises:
        RuntimeError: If the browser cannot load the page or read the token.
    """
    from patchright.sync_api import TimeoutError as PlaywrightTimeoutError
    from patchright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.route("**/*fingerprint*", lambda route: route.abort())
            page.route("**/*podname.com*", lambda route: route.abort())
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

            has_table = False
            try:
                page.wait_for_selector("table[id^='standings-']", timeout=timeout_ms)
                has_table = True
            except PlaywrightTimeoutError:
                has_table = False

            html = page.content()
            token = _token_from_html(html) or ""
            if not token:
                token_value = page.evaluate(_TOKEN_JS)
                token = "" if token_value is None else str(token_value)
            if not token:
                raise RuntimeError("page did not expose gSiteHeaderValue")
            stages = tuple(str(label) for label in page.evaluate(_STAGES_JS))

            standings: dict[View, tuple[RawStandingsRow, ...]] = {}
            if has_table:
                for view in VIEWS:
                    # The live page uses lower-case data-source values
                    # ("overall", "home", "away"); title-casing them silently
                    # matches nothing and leaves every view identical.
                    selector = f'a.option[data-source="{view}"]'
                    toggle = page.locator(selector)
                    if toggle.count():
                        toggle.first.click()
                        page.wait_for_timeout(400)
                    items = page.evaluate(_STANDINGS_JS)
                    if not isinstance(items, list):
                        raise RuntimeError(f"standings rows were not a list for {view}")
                    standings[view] = _rows_from_js(items)

            return PageCapture(
                html=html,
                token=token,
                stages=stages,
                standings=standings,
                captured_at=datetime.now(UTC),
                url=url,
            )
        finally:
            browser.close()
