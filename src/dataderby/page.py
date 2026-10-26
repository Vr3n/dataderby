"""Live stage capture and the browser-backed feed transport."""

from __future__ import annotations

import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from dataderby.config import StageSpec
from dataderby.contract import SECTIONS, VIEWS, Section, View
from dataderby.fetch import (
    Capture,
    FetchBlocked,
    FetchError,
    GatePage,
    RequestBudget,
    SchemaDrift,
    feed_url,
    parse_envelope,
    retry_after_seconds,
)
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

_FEED_JS = """
async (args) => {
  const response = await fetch(args.url, {
    headers: {
      'Model-last-Mode': args.token,
      'Accept': 'application/json, text/javascript, */*; q=0.01',
      'X-Requested-With': 'XMLHttpRequest'
    },
    credentials: 'include'
  });
  return {
    status: response.status,
    type: response.headers.get('content-type'),
    retryAfter: response.headers.get('retry-after'),
    body: await response.text()
  };
}
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


@dataclass(frozen=True, slots=True)
class StageCapture:
    """A page and its feeds, captured in one browser session."""

    page: PageCapture
    feeds: tuple[Capture, ...]


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


def _read_page(page: Any, url: str, timeout_ms: int) -> PageCapture:
    """Navigate a loaded browser page and read the table, token, and labels."""
    from patchright.sync_api import TimeoutError as PlaywrightTimeoutError

    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

    has_table = False
    try:
        page.wait_for_selector("table[id^='standings-']", timeout=timeout_ms)
        has_table = True
    except PlaywrightTimeoutError:
        has_table = False
    page.wait_for_timeout(1_000)

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


def capture_page(url: str, *, timeout_ms: int = 45_000) -> PageCapture:
    """Load a WhoScored stage page in a headed Chromium and read the tables.

    This is the page-only path. Use :func:`capture_stage` when the feeds are
    needed too, so the page and the feeds share one browser session.

    Args:
        url: The stage's ``show`` URL.
        timeout_ms: Navigation and selector timeout.

    Returns:
        The page capture. ``standings`` is empty when the page has no league
        table, including knockout stages.

    Raises:
        RuntimeError: If the browser cannot load the page or read the token.
    """
    from patchright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.route("**/*fingerprint*", lambda route: route.abort())
            page.route("**/*podname.com*", lambda route: route.abort())
            return _read_page(page, url, timeout_ms)
        finally:
            browser.close()


def _fetch_one(page: Any, url: str, token: str) -> tuple[int, bytes, str | None, str | None]:
    """Fetch one feed from inside the page's own session."""
    result = page.evaluate(_FEED_JS, {"url": url, "token": token})
    if not isinstance(result, dict):
        raise FetchError("feed fetch returned no result")
    body = str(result.get("body", "")).encode("utf-8")
    content_type = result.get("type")
    retry_after = result.get("retryAfter")
    return (
        int(result.get("status", 0)),
        body,
        str(content_type) if content_type else None,
        str(retry_after) if retry_after else None,
    )


def collect_feeds(
    spec: StageSpec,
    token: str,
    fetch_one: Callable[[str], tuple[int, bytes, str | None, str | None]],
    *,
    only: tuple[tuple[Section, View], ...] | None = None,
    pacing: float = 1.2,
    max_attempts: int = 3,
    budget: RequestBudget | None = None,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> tuple[Capture, ...]:
    """Fetch and validate one stage's feeds, with pacing, retries, and a budget.

    The transport is injected as ``fetch_one``: in production it runs JavaScript
    in the page; in tests it returns canned bytes. That keeps the retry,
    pacing, budget, and envelope rules testable without a browser.

    Policy: 403 is terminal, 429 honours ``Retry-After`` (capped at 60 s), other
    4xx are terminal, and 5xx or a gate page are retried.

    Args:
        spec: Stage to fetch.
        token: ``Model-last-Mode`` token from the page.
        fetch_one: Callable returning
            ``(status, body, content_type, retry_after)`` for a URL.
        only: Optional subset of ``(section, view)`` pairs. Defaults to all nine.
        pacing: Seconds between requests.
        max_attempts: Attempts per feed.
        budget: Shared request ceiling. Defaults to a fresh budget of 20.
        sleep: Injectable sleep, for tests.
        jitter: Injectable jitter, for tests.
        now: Injectable clock, for tests.

    Returns:
        Accepted captures in request order.

    Raises:
        FetchBlocked: Immediately on HTTP 403.
        FetchBudgetExceeded: If the budget is exhausted.
        SchemaDrift: Immediately, because a changed column list is not transient.
        FetchError: If a feed cannot be accepted after every attempt.
    """
    pairs = only if only is not None else tuple((s, v) for s in SECTIONS for v in VIEWS)
    feed_budget = budget if budget is not None else RequestBudget(limit=20)
    feeds: list[Capture] = []
    first_request = True

    def pace() -> None:
        nonlocal first_request
        if not first_request:
            sleep(pacing)
        first_request = False

    for section, view in pairs:
        url = feed_url(spec, section, view)
        last_error: FetchError | None = None

        for attempt in range(1, max_attempts + 1):
            feed_budget.consume()
            pace()
            delay: float | None = None
            try:
                status, body, content_type, retry_after = fetch_one(url)
            except FetchError:
                raise
            except Exception as exc:
                last_error = FetchError(f"{section}/{view}: request failed: {exc}")
            else:
                if status == 403:
                    raise FetchBlocked(f"{section}/{view}: HTTP 403")
                if status == 429:
                    wait = retry_after_seconds(retry_after)
                    last_error = FetchError(f"{section}/{view}: HTTP 429")
                    delay = min(60.0, wait) if wait is not None else None
                elif 400 <= status < 500:
                    raise FetchError(f"{section}/{view}: HTTP {status}")
                elif status != 200:
                    last_error = FetchError(f"{section}/{view}: HTTP {status}")
                else:
                    try:
                        parse_envelope(body, section, view)
                    except SchemaDrift:
                        raise
                    except GatePage as exc:
                        last_error = exc
                    else:
                        feeds.append(
                            Capture(
                                section=section,
                                view=view,
                                body=body,
                                captured_at=now(),
                                content_type=content_type,
                                url=url,
                                status=status,
                                attempt=attempt,
                            )
                        )
                        break

            if attempt < max_attempts:
                sleep(delay if delay is not None else 2**attempt + jitter())
        else:
            if last_error is None:
                raise FetchError(f"{section}/{view}: no attempt was made")
            raise last_error

    return tuple(feeds)


def capture_stage(
    url: str,
    spec: StageSpec,
    *,
    only: tuple[tuple[Section, View], ...] | None = None,
    budget: RequestBudget | None = None,
    timeout_ms: int = 45_000,
) -> StageCapture:
    """Capture a stage page and its feeds in one browser session.

    The feeds are requested by the page itself, so they carry the session the
    site created. That is the difference between JSON and a 200 HTML error page.

    Args:
        url: The stage's ``show`` URL.
        spec: Stage configuration, used to build the feed URLs.
        only: Optional subset of feeds, used by ``probe``.
        budget: Shared request ceiling for the run.
        timeout_ms: Navigation and selector timeout.

    Returns:
        The page and its accepted feed captures.

    Raises:
        RuntimeError: If the page cannot be read.
        FetchError: If a feed cannot be accepted.
    """
    from patchright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        try:
            context = browser.new_context()
            page = context.new_page()
            page_capture = _read_page(page, url, timeout_ms)
            feeds = collect_feeds(
                spec,
                page_capture.token,
                lambda feed: _fetch_one(page, feed, page_capture.token),
                only=only,
                budget=budget,
            )
            return StageCapture(page=page_capture, feeds=feeds)
        finally:
            browser.close()
