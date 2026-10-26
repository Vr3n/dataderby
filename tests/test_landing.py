"""Landing tests with an injected page and feed fetcher."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import duckdb
import pytest

from dataderby.config import StageSpec, load_settings
from dataderby.contract import EXPECTED_STAT_COLUMNS, SECTIONS, VIEWS, Section, View
from dataderby.db import connect, migrate, transaction
from dataderby.fetch import Capture, FeedFetcher, FetchBlocked
from dataderby.landing import _insert_raw_captures, land_stage
from dataderby.page import PageCapture
from dataderby.standings import RawStandingsRow

_SPEC = load_settings(Path("config/stages.toml")).stages["epl-2026-2027"]
_OBSERVED = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
_URL = "https://www.whoscored.com/example"


@pytest.fixture
def con(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = connect(tmp_path / "test.duckdb")
    migrate(connection)
    try:
        yield connection
    finally:
        connection.close()


def _row(team_id: int, name: str, rank: int) -> RawStandingsRow:
    return RawStandingsRow(
        whoscored_team_id=team_id,
        whoscored_team_name=name,
        rank=str(rank),
        played="7",
        won="5",
        drawn="1",
        lost="1",
        goals_for="12",
        goals_against="5",
        goal_difference="7",
        points="16",
        form="wwdwl",
    )


def _page() -> PageCapture:
    rows = (_row(211, "Brighton", 1), _row(167, "Man City", 2))
    return PageCapture(
        html="<html>page</html>",
        token="token",
        stages=("Premier League",),
        standings={"overall": rows, "home": rows, "away": rows},
        captured_at=_OBSERVED,
        url=_URL,
    )


def _payload(section: Section, view: View) -> bytes:
    body = {
        "teamTableStats": [],
        "paging": {},
        "statColumns": list(EXPECTED_STAT_COLUMNS[(section, view)]),
    }
    return json.dumps(body, separators=(",", ":")).encode("utf-8")


def _feeds() -> tuple[Capture, ...]:
    return tuple(
        Capture(
            section=section,
            view=view,
            body=_payload(section, view),
            captured_at=_OBSERVED + timedelta(seconds=1),
            content_type="text/html",
            url=f"{_URL}?section={section}&view={view}",
        )
        for section in SECTIONS
        for view in VIEWS
    )


class _FakeFetcher:
    def __init__(
        self, feeds: tuple[Capture, ...] | None = None, error: Exception | None = None
    ) -> None:
        self._feeds = feeds
        self._error = error
        self.calls: list[tuple[StageSpec, str]] = []

    def fetch_all(self, spec: StageSpec, token: str) -> tuple[Capture, ...]:
        self.calls.append((spec, token))
        if self._error is not None:
            raise self._error
        assert self._feeds is not None
        return self._feeds


def test_landing_writes_page_standings_and_feeds_then_ledger(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    fetcher = _FakeFetcher(_feeds())

    result = land_stage(
        con,
        _SPEC,
        tmp_path / "raw",
        _page(),
        cast(FeedFetcher, fetcher),
        run_id="run_test",
        log_dir=tmp_path / "logs",
    )

    assert result.run_id == "run_test"
    assert result.observed_at == _OBSERVED
    assert len(result.raw_files) == 13
    assert len(fetcher.calls) == 1

    run = con.execute(
        """
        SELECT outcome, http_requests, observed_at
        FROM ingestion_run WHERE run_id = 'run_test'
        """
    ).fetchone()
    assert run is not None
    assert run[0] == "running"
    assert run[1] == 10
    assert run[2] is not None

    raw = con.execute("SELECT count(*) FROM raw_capture WHERE run_id = 'run_test'").fetchone()
    assert raw is not None
    assert raw[0] == 13
    assert (result.raw_files[0].path).exists()

    standings = json.loads(
        (
            tmp_path
            / "raw"
            / "2"
            / "11141"
            / "25544"
            / "2026-10-21T10-00-00.000000Z"
            / "standings__overall.json"
        ).read_text(encoding="utf-8")
    )
    assert standings["view"] == "overall"
    assert len(standings["rows"]) == 2


def test_pre_fetched_feeds_skip_the_fetcher(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    fetcher = _FakeFetcher(error=AssertionError("fetcher must not be called"))

    result = land_stage(
        con,
        _SPEC,
        tmp_path / "raw",
        _page(),
        cast(FeedFetcher, fetcher),
        feeds=_feeds(),
        run_id="run_prefetched",
        log_dir=tmp_path / "logs",
    )

    assert len(result.raw_files) == 13
    assert fetcher.calls == []


def test_landing_requires_a_feed_source(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fetcher or feeds"):
        land_stage(
            con,
            _SPEC,
            tmp_path / "raw",
            _page(),
            run_id="run_missing",
            log_dir=tmp_path / "logs",
        )


def test_raw_ledger_insert_is_idempotent(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    result = land_stage(
        con,
        _SPEC,
        tmp_path / "raw",
        _page(),
        cast(FeedFetcher, _FakeFetcher(_feeds())),
        run_id="run_test",
        log_dir=tmp_path / "logs",
    )

    with transaction(con):
        _insert_raw_captures(con, "run_test", result.raw_files)

    count = con.execute("SELECT count(*) FROM raw_capture WHERE run_id = 'run_test'").fetchone()
    assert count is not None
    assert count[0] == 13


def test_fetch_failure_marks_the_run_and_writes_no_raw(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    fetcher = _FakeFetcher(error=FetchBlocked("blocked"))

    with pytest.raises(FetchBlocked):
        land_stage(
            con,
            _SPEC,
            tmp_path / "raw",
            _page(),
            cast(FeedFetcher, fetcher),
            run_id="run_blocked",
            log_dir=tmp_path / "logs",
        )

    run = con.execute(
        "SELECT outcome, finished_at FROM ingestion_run WHERE run_id = 'run_blocked'"
    ).fetchone()
    assert run is not None
    assert run[0] == "fetch_failed"
    assert run[1] is not None
    assert not (tmp_path / "raw").exists()
