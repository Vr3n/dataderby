"""Feed fetching tests against a local replay server and a fake session."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from dataderby.config import load_settings
from dataderby.contract import EXPECTED_STAT_COLUMNS, SECTIONS, VIEWS, Section, View
from dataderby.fetch import (
    Capture,
    FeedFetcher,
    FetchBlocked,
    FetchError,
    GatePage,
    SchemaDrift,
    feed_url,
)

_SPEC = load_settings(Path("config/stages.toml")).stages["epl-2026-2027"]
_SUBCATEGORY = {"summary": "all", "defensive": "defensive", "offensive": "offensive"}
_FIELD = {"overall": "Overall", "home": "Home", "away": "Away"}


def _payload(section: Section, view: View, *, columns: tuple[str, ...] | None = None) -> bytes:
    expected = columns or EXPECTED_STAT_COLUMNS[(section, view)]
    body = {
        "teamTableStats": [],
        "paging": {},
        "statColumns": list(expected),
    }
    return json.dumps(body, separators=(",", ":")).encode("utf-8")


class _ReplayServer(ThreadingHTTPServer):
    responses: dict[tuple[int, str, str], tuple[int, bytes, str]]
    requests: list[str]


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        server = self.server
        assert isinstance(server, _ReplayServer)
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        server.requests.append(self.path)
        try:
            key = (
                int(params["stageId"][0]),
                params["subcategory"][0],
                params["field"][0].lower(),
            )
        except (KeyError, IndexError, ValueError):
            status, body, content_type = 400, b"bad request", "text/plain"
        else:
            status, body, content_type = server.responses.get(
                key, (404, b"not found", "text/plain")
            )

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


@contextmanager
def _serve(
    responses: dict[tuple[int, str, str], tuple[int, bytes, str]],
) -> Iterator[tuple[str, _ReplayServer]]:
    server = _ReplayServer(("127.0.0.1", 0), _Handler)
    server.responses = responses
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/feed", server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _all_responses(
    *, body: bytes | None = None
) -> dict[tuple[int, str, str], tuple[int, bytes, str]]:
    return {
        (_SPEC.whoscored_stage_id, _SUBCATEGORY[section], _FIELD[view].lower()): (
            200,
            body if body is not None else _payload(section, view),
            "text/html",
        )
        for section in SECTIONS
        for view in VIEWS
    }


def test_feed_url_contains_stage_and_category() -> None:
    url = feed_url(_SPEC, "summary", "overall")

    assert "stageId=25544" in url
    assert "category=summaryteam" in url
    assert "subcategory=all" in url
    assert "field=Overall" in url


def test_fetches_nine_captures_in_summary_first_order() -> None:
    with _serve(_all_responses()) as (base_url, server):
        captures = FeedFetcher(
            base_url=base_url,
            spacing=0,
            sleep=lambda _: None,
        ).fetch_all(_SPEC, "token")

    assert len(captures) == 9
    assert [(capture.section, capture.view) for capture in captures] == [
        (section, view) for section in SECTIONS for view in VIEWS
    ]
    assert all(isinstance(capture, Capture) for capture in captures)
    assert len(server.requests) == 9


def test_bom_is_stripped_before_json_decode() -> None:
    responses = _all_responses()
    key = (_SPEC.whoscored_stage_id, "all", "overall")
    status, body, content_type = responses[key]
    responses[key] = (status, b"\xef\xbb\xbf" + body, content_type)

    with _serve(responses) as (base_url, _):
        captures = FeedFetcher(base_url=base_url, spacing=0, sleep=lambda _: None).fetch_all(
            _SPEC, "token"
        )

    assert captures[0].section == "summary"


def test_403_is_blocked() -> None:
    responses = _all_responses(body=b"")
    for key in responses:
        responses[key] = (403, b"blocked", "text/html")

    with _serve(responses) as (base_url, _), pytest.raises(FetchBlocked):
        FeedFetcher(
            base_url=base_url,
            spacing=0,
            max_attempts=1,
            sleep=lambda _: None,
        ).fetch_one(_SPEC, "summary", "overall", "token")


@pytest.mark.parametrize("body", [b"", b"<html>gate</html>", b'{"teamTableStats": ['])
def test_non_envelope_bodies_are_gate_pages(body: bytes) -> None:
    with _serve(_all_responses(body=body)) as (base_url, _), pytest.raises(GatePage):
        FeedFetcher(
            base_url=base_url,
            spacing=0,
            max_attempts=1,
            sleep=lambda _: None,
        ).fetch_one(_SPEC, "summary", "overall", "token")


def test_changed_columns_are_schema_drift() -> None:
    wrong = ("apps", "goal")
    responses = _all_responses()
    key = (_SPEC.whoscored_stage_id, "all", "overall")
    responses[key] = (200, _payload("summary", "overall", columns=wrong), "text/html")

    with _serve(responses) as (base_url, _), pytest.raises(SchemaDrift):
        FeedFetcher(
            base_url=base_url,
            spacing=0,
            max_attempts=1,
            sleep=lambda _: None,
        ).fetch_one(_SPEC, "summary", "overall", "token")


@dataclass
class _FakeResponse:
    status_code: int
    content: bytes
    headers: dict[str, str]


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> _FakeResponse:
        self.calls.append((url, headers))
        return self._responses.pop(0)


def test_retry_uses_two_then_four_seconds_and_keeps_the_third_attempt() -> None:
    session = _FakeSession(
        [
            _FakeResponse(500, b"", {}),
            _FakeResponse(500, b"", {}),
            _FakeResponse(200, _payload("summary", "overall"), {"content-type": "text/html"}),
        ]
    )
    sleeps: list[float] = []

    capture = FeedFetcher(
        session=session,
        base_url="http://replay/feed",
        spacing=0,
        max_attempts=3,
        sleep=sleeps.append,
        jitter=lambda: 0.0,
        now=lambda: datetime(2026, 10, 21, 10, 0, tzinfo=UTC),
    ).fetch_one(_SPEC, "summary", "overall", "token")

    assert capture.attempt == 3
    assert sleeps == [2.0, 4.0]
    assert session.calls[0][1] == {"Model-last-Mode": "token"}


def test_schema_drift_is_not_retried() -> None:
    session = _FakeSession(
        [
            _FakeResponse(
                200,
                _payload("summary", "overall", columns=("apps",)),
                {"content-type": "text/html"},
            )
        ]
    )

    with pytest.raises(SchemaDrift):
        FeedFetcher(
            session=session,
            base_url="http://replay/feed",
            spacing=0,
            sleep=lambda _: None,
        ).fetch_one(_SPEC, "summary", "overall", "token")

    assert len(session.calls) == 1


def test_non_200_is_retried() -> None:
    session = _FakeSession(
        [
            _FakeResponse(500, b"", {}),
            _FakeResponse(
                200,
                _payload("summary", "overall"),
                {"content-type": "text/html"},
            ),
        ]
    )
    sleeps: list[float] = []

    capture = FeedFetcher(
        session=session,
        base_url="http://replay/feed",
        spacing=0,
        max_attempts=2,
        sleep=sleeps.append,
        jitter=lambda: 0.0,
    ).fetch_one(_SPEC, "summary", "overall", "token")

    assert capture.attempt == 2
    assert sleeps == [2.0]


class _FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


def test_pacing_waits_1_2_seconds_between_successful_requests() -> None:
    clock = _FakeClock()
    session = _FakeSession(
        [
            _FakeResponse(
                200,
                _payload(section, view),
                {"content-type": "text/html"},
            )
            for section in SECTIONS
            for view in VIEWS
        ]
    )

    FeedFetcher(
        session=session,
        base_url="http://replay/feed",
        spacing=1.2,
        max_attempts=1,
        sleep=clock.sleep,
        clock=clock.now,
    ).fetch_all(_SPEC, "token")

    assert len(clock.sleeps) == 8
    assert all(abs(seconds - 1.2) < 1e-9 for seconds in clock.sleeps)


def test_a_403_is_not_retried() -> None:
    session = _FakeSession([_FakeResponse(403, b"", {})])

    with pytest.raises(FetchBlocked):
        FeedFetcher(
            session=session,
            base_url="http://replay/feed",
            spacing=0,
            max_attempts=3,
            sleep=lambda _: None,
        ).fetch_one(_SPEC, "summary", "overall", "token")

    assert len(session.calls) == 1


def test_a_429_honours_retry_after() -> None:
    session = _FakeSession(
        [
            _FakeResponse(429, b"", {"retry-after": "5"}),
            _FakeResponse(
                200,
                _payload("summary", "overall"),
                {"content-type": "text/html"},
            ),
        ]
    )
    sleeps: list[float] = []

    capture = FeedFetcher(
        session=session,
        base_url="http://replay/feed",
        spacing=0,
        max_attempts=2,
        sleep=sleeps.append,
        jitter=lambda: 0.0,
    ).fetch_one(_SPEC, "summary", "overall", "token")

    assert capture.attempt == 2
    assert sleeps == [5.0]


def test_a_404_is_not_retried() -> None:
    session = _FakeSession([_FakeResponse(404, b"", {})])

    with pytest.raises(FetchError):
        FeedFetcher(
            session=session,
            base_url="http://replay/feed",
            spacing=0,
            max_attempts=3,
            sleep=lambda _: None,
        ).fetch_one(_SPEC, "summary", "overall", "token")

    assert len(session.calls) == 1
