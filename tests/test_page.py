"""Stage-page token and feed-transport tests; no browser and no network."""

from __future__ import annotations

import pytest

from dataderby.contract import SECTIONS, VIEWS
from dataderby.fetch import GatePage, SchemaDrift, feed_url
from dataderby.page import _token_from_html, collect_feeds
from tests.test_whoscored_parse import _SPEC, _captures


def test_reads_a_single_quoted_token_from_the_inline_bootstrap() -> None:
    html = "<script>gSiteHeaderValue: 'abc123',</script>"

    assert _token_from_html(html) == "abc123"


def test_reads_a_double_quoted_token() -> None:
    html = '<script>gSiteHeaderValue: "abc123"</script>'

    assert _token_from_html(html) == "abc123"


def test_returns_none_when_the_page_has_no_token() -> None:
    assert _token_from_html("<html><body>no token here</body></html>") is None


def _by_url() -> dict[str, bytes]:
    bodies = {(capture.section, capture.view): capture.body for capture in _captures()}
    return {
        feed_url(_SPEC, section, view): bodies[(section, view)]
        for section in SECTIONS
        for view in VIEWS
    }


def test_collect_feeds_returns_all_nine_in_order() -> None:
    by_url = _by_url()

    def fetch(url: str) -> tuple[int, bytes, str | None]:
        return 200, by_url[url], "application/json"

    feeds = collect_feeds(_SPEC, "token", fetch, sleep=lambda _: None)

    assert [(feed.section, feed.view) for feed in feeds] == [
        (section, view) for section in SECTIONS for view in VIEWS
    ]
    assert all(feed.status == 200 for feed in feeds)
    assert all(feed.attempt == 1 for feed in feeds)


def test_collect_feeds_honours_the_only_filter() -> None:
    by_url = _by_url()

    def fetch(url: str) -> tuple[int, bytes, str | None]:
        return 200, by_url[url], "application/json"

    feeds = collect_feeds(
        _SPEC,
        "token",
        fetch,
        only=(("summary", "overall"),),
        sleep=lambda _: None,
    )

    assert [(feed.section, feed.view) for feed in feeds] == [("summary", "overall")]


def test_collect_feeds_paces_between_requests() -> None:
    by_url = _by_url()
    sleeps: list[float] = []

    def fetch(url: str) -> tuple[int, bytes, str | None]:
        return 200, by_url[url], "application/json"

    collect_feeds(
        _SPEC,
        "token",
        fetch,
        only=(("summary", "overall"), ("summary", "home"), ("summary", "away")),
        pacing=1.2,
        sleep=sleeps.append,
    )

    assert sleeps == [1.2, 1.2]


def test_a_gate_page_is_retried_then_raised() -> None:
    calls = 0

    def gate(url: str) -> tuple[int, bytes, str | None]:
        nonlocal calls
        calls += 1
        return 200, b"<html>verify</html>", "text/html"

    with pytest.raises(GatePage):
        collect_feeds(
            _SPEC,
            "token",
            gate,
            only=(("summary", "overall"),),
            max_attempts=3,
            sleep=lambda _: None,
            jitter=lambda: 0.0,
        )

    assert calls == 3


def test_schema_drift_is_not_retried() -> None:
    calls = 0

    def drifted(url: str) -> tuple[int, bytes, str | None]:
        nonlocal calls
        calls += 1
        body = b'{"teamTableStats": [], "paging": {}, "statColumns": ["apps"]}'
        return 200, body, "application/json"

    with pytest.raises(SchemaDrift):
        collect_feeds(
            _SPEC,
            "token",
            drifted,
            only=(("summary", "overall"),),
            max_attempts=3,
            sleep=lambda _: None,
        )

    assert calls == 1
