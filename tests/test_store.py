"""SQLite storage tests: idempotency, change detection and constraints."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from dataderby.fixtures.competitions import Competition
from dataderby.fixtures.parse import Fixture, parse_csv
from dataderby.fixtures.store import (
    connect,
    initialise,
    upsert_competition,
    upsert_fixtures,
)
from tests.helpers import ROWS, csv_bytes

COMPETITION = Competition("test", "test-2026", "Test League", "Testland")
SEEN_AT = "2026-10-19T00:00:00Z"


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(tmp_path / "fixtures.sqlite3")
    initialise(connection)
    yield connection
    connection.close()


def _seed(connection: sqlite3.Connection, fixtures: list[Fixture]) -> None:
    upsert_competition(
        connection,
        COMPETITION,
        fixture_count=len(fixtures),
        played_count=sum(1 for fixture in fixtures if fixture.status == "played"),
        fixturedownload_url="https://example.invalid/test-2026-UTC.csv",
        fetched_at=SEEN_AT,
    )


def test_first_write_inserts_every_row(connection: sqlite3.Connection) -> None:
    fixtures = parse_csv(COMPETITION, csv_bytes())
    _seed(connection, fixtures)

    result = upsert_fixtures(connection, fixtures, seen_at=SEEN_AT)
    connection.commit()

    assert result.inserted == 2
    assert result.updated == 0
    assert result.unchanged == 0
    assert connection.execute("SELECT count(*) FROM fixtures").fetchone()[0] == 2


def test_second_write_is_a_no_op(connection: sqlite3.Connection) -> None:
    fixtures = parse_csv(COMPETITION, csv_bytes())
    _seed(connection, fixtures)
    upsert_fixtures(connection, fixtures, seen_at=SEEN_AT)
    connection.commit()

    result = upsert_fixtures(connection, fixtures, seen_at="2026-10-20T00:00:00Z")
    connection.commit()

    assert result.inserted == 0
    assert result.updated == 0
    assert result.unchanged == 2


def test_changed_score_is_updated_and_first_seen_is_preserved(
    connection: sqlite3.Connection,
) -> None:
    fixtures = parse_csv(COMPETITION, csv_bytes())
    _seed(connection, fixtures)
    upsert_fixtures(connection, fixtures, seen_at=SEEN_AT)
    connection.commit()

    changed_row = (*ROWS[0][:6], "4 - 0")
    changed = parse_csv(COMPETITION, csv_bytes(rows=(changed_row, ROWS[1])))
    result = upsert_fixtures(connection, changed, seen_at="2026-10-20T00:00:00Z")
    connection.commit()

    row = connection.execute(
        "SELECT home_score, first_seen_at, last_seen_at FROM fixtures WHERE match_number = 1"
    ).fetchone()

    assert result.updated == 1
    assert result.unchanged == 1
    assert row["home_score"] == 4
    assert row["first_seen_at"] == SEEN_AT
    assert row["last_seen_at"] == "2026-10-20T00:00:00Z"


def test_fact_without_competition_is_rejected(connection: sqlite3.Connection) -> None:
    fixtures = parse_csv(COMPETITION, csv_bytes())

    with pytest.raises(sqlite3.IntegrityError):
        upsert_fixtures(connection, fixtures, seen_at=SEEN_AT)


def test_played_fixture_requires_both_scores(connection: sqlite3.Connection) -> None:
    fixtures = parse_csv(COMPETITION, csv_bytes())
    _seed(connection, fixtures)
    broken = replace(fixtures[0], home_score=None)

    with pytest.raises(sqlite3.IntegrityError):
        upsert_fixtures(connection, [broken], seen_at=SEEN_AT)


def test_upcoming_view_uses_utc_cutoff(connection: sqlite3.Connection) -> None:
    rows = (
        ROWS[0],
        ("2", "1", "22/08/2099 11:30", "MKM Stadium", "Hull", "Man Utd", ""),
    )
    fixtures = parse_csv(COMPETITION, csv_bytes(rows=rows))
    _seed(connection, fixtures)
    upsert_fixtures(connection, fixtures, seen_at=SEEN_AT)
    connection.commit()

    upcoming = connection.execute("SELECT kickoff_ist FROM v_upcoming_fixtures").fetchall()

    assert len(upcoming) == 1
    assert upcoming[0]["kickoff_ist"] == "2099-08-22T17:00:00+05:30"
