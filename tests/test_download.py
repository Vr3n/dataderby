"""Downloader tests: retry policy and payload validation.

These cover a real regression: sending ``Accept: text/csv`` made the source answer
HTTP 406, and a missing User-Agent made it answer 403. Both looked like flaky network
failures because they were retried.
"""

from __future__ import annotations

import urllib.error
from typing import Any, Literal

import pytest

from dataderby.fixtures.download import DownloadError, fetch_csv

PAYLOAD = b"Match Number,Round Number,Date,Location,Home Team,Away Team,Result\n"


class _Response:
    """Minimal stand-in for the object returned by urlopen."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc_info: object) -> Literal[False]:
        return False

    def read(self) -> bytes:
        return self._body


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.invalid", code, "error", {}, None)  # type: ignore[arg-type]


def test_permanent_http_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        calls.append(request)
        raise _http_error(406)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(DownloadError, match="not published"):
        fetch_csv("epl-2026")

    assert len(calls) == 1


def test_transient_error_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        calls.append(request)
        raise urllib.error.URLError("temporary")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    with pytest.raises(DownloadError, match="failed after 3 attempts"):
        fetch_csv("epl-2026", retries=3, backoff=0.0)

    assert len(calls) == 3


def test_non_csv_payload_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Any, timeout: float) -> _Response:
        return _Response(b"<html>gate page</html>")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(DownloadError, match="not a fixture CSV"):
        fetch_csv("epl-2026")


def test_successful_payload_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Any, timeout: float) -> _Response:
        return _Response(PAYLOAD)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert fetch_csv("epl-2026") == PAYLOAD


def test_cache_path_is_stable_for_a_timestamp(tmp_path: Any) -> None:
    from datetime import UTC, datetime
    from pathlib import Path

    from dataderby.fixtures.download import cache_path

    stamp = datetime(2026, 10, 20, 6, 0, 0, tzinfo=UTC)
    path = cache_path(Path(tmp_path), "epl-2026", stamp)

    assert path == Path(tmp_path) / "fixtures" / "raw" / "epl-2026" / (
        "2026-10-20T06-00-00.000000Z.csv"
    )
