"""Service tests: refresh, idempotency, and failure reporting."""

from __future__ import annotations

from pathlib import Path

import pytest

from dataderby.fixtures.competitions import Competition
from dataderby.fixtures.download import DownloadError
from dataderby.fixtures.service import RefreshError, refresh
from dataderby.fixtures.store import connect
from tests.helpers import csv_bytes

COMPETITION = Competition("test", "test-2026", "Test League", "Testland")


def _fetcher(slug: str) -> bytes:
    assert slug == COMPETITION.slug
    return csv_bytes()


def test_refresh_stores_fixtures(tmp_path: Path) -> None:
    result = refresh(
        tmp_path / "fixtures.sqlite3",
        tmp_path / "data",
        (COMPETITION,),
        fetcher=_fetcher,
    )

    assert result.fixture_count == 2
    assert result.competitions[0].played == 1
    assert result.competitions[0].inserted == 2
    assert result.competitions[0].csv_path.exists()


def test_refresh_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "fixtures.sqlite3"
    data = tmp_path / "data"
    refresh(db, data, (COMPETITION,), fetcher=_fetcher)

    second = refresh(db, data, (COMPETITION,), fetcher=_fetcher)

    assert second.competitions[0].inserted == 0
    assert second.competitions[0].updated == 0
    assert second.competitions[0].unchanged == 2
    connection = connect(db)
    try:
        assert connection.execute("SELECT count(*) FROM fixtures").fetchone()[0] == 2
    finally:
        connection.close()


def test_download_failure_propagates(tmp_path: Path) -> None:
    def failing(slug: str) -> bytes:
        raise DownloadError(f"{slug}: unavailable")

    with pytest.raises(DownloadError, match="unavailable"):
        refresh(
            tmp_path / "fixtures.sqlite3",
            tmp_path / "data",
            (COMPETITION,),
            fetcher=failing,
        )


def test_parse_failure_is_collected(tmp_path: Path) -> None:
    def drifted(slug: str) -> bytes:
        return b"Wrong,Columns\n1,2\n"

    with pytest.raises(RefreshError) as caught:
        refresh(
            tmp_path / "fixtures.sqlite3",
            tmp_path / "data",
            (COMPETITION,),
            fetcher=drifted,
        )

    assert "unexpected columns" in caught.value.result.failures[0]
    assert caught.value.result.competitions == ()
