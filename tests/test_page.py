"""Stage-page token extraction tests; no browser and no network."""

from __future__ import annotations

from dataderby.page import _token_from_html


def test_reads_a_single_quoted_token_from_the_inline_bootstrap() -> None:
    html = "<script>gSiteHeaderValue: 'abc123',</script>"

    assert _token_from_html(html) == "abc123"


def test_reads_a_double_quoted_token() -> None:
    html = '<script>gSiteHeaderValue: "abc123"</script>'

    assert _token_from_html(html) == "abc123"


def test_returns_none_when_the_page_has_no_token() -> None:
    assert _token_from_html("<html><body>no token here</body></html>") is None
