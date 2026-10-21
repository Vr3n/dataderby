"""Schema and DuckDB helper tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from dataderby.contract import MEASURE_COLUMNS, STANDINGS_MEASURES
from dataderby.db import connect, migrate, transaction

_URL = (
    "https://www.whoscored.com/regions/252/tournaments/2/seasons/11141/"
    "stages/25544/show/england-premier-league-2026-2027"
)


@pytest.fixture
def con(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = connect(tmp_path / "test.duckdb")
    migrate(connection)
    try:
        yield connection
    finally:
        connection.close()


def _insert_header(
    con: duckdb.DuckDBPyConnection,
    *,
    snapshot_id: str = "snap_1",
    parent: str = "genesis",
    fingerprint: str = "fp_1",
    observed_at: str = "2026-10-21 10:00:00",
) -> None:
    con.execute(
        """
        INSERT INTO competition_snapshot (
            snapshot_id, parent_snapshot_id, whoscored_tournament_id,
            whoscored_season_id, whoscored_stage_id, season_key,
            content_fingerprint, canonical_version, observed_at, accepted_at,
            capture_span_seconds, is_opta, whoscored_page_url, run_id
        ) VALUES (?, ?, 2, 11141, 25544, '2026-2027', ?, 1, ?, ?, 1.0, TRUE, ?, 'run_1')
        """,
        [snapshot_id, parent, fingerprint, observed_at, observed_at, _URL],
    )


def _insert_team(
    con: duckdb.DuckDBPyConnection,
    snapshot_id: str = "snap_1",
    apps: int | None = 1,
) -> None:
    con.execute(
        """
        INSERT INTO fact_team_snapshot (
            snapshot_id, whoscored_team_id, whoscored_team_name, apps_overall
        ) VALUES (?, 211, 'Brighton', ?)
        """,
        [snapshot_id, apps],
    )


def test_connection_pins_the_session_timezone_to_utc(
    con: duckdb.DuckDBPyConnection,
) -> None:
    assert con.execute("SELECT current_setting('TimeZone')").fetchone()[0] == "UTC"


def test_aware_utc_timestamps_are_stored_as_utc(
    con: duckdb.DuckDBPyConnection,
) -> None:
    con.execute("CREATE TABLE stamp_probe (ts TIMESTAMP)")
    value = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
    con.execute("INSERT INTO stamp_probe VALUES (?)", [value])

    stored = con.execute("SELECT ts FROM stamp_probe").fetchone()[0]

    assert stored == value.replace(tzinfo=None)


def test_schema_can_be_applied_twice(con: duckdb.DuckDBPyConnection) -> None:
    migrate(con)

    tables = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_type = 'BASE TABLE' ORDER BY table_name"
    ).fetchall()
    assert [row[0] for row in tables] == [
        "competition_snapshot",
        "fact_standings_snapshot",
        "fact_team_snapshot",
        "ingestion_run",
        "pipeline_checkpoint",
        "raw_capture",
    ]


def test_fact_row_without_header_is_rejected(con: duckdb.DuckDBPyConnection) -> None:
    with pytest.raises(duckdb.ConstraintException):
        _insert_team(con)


def test_standings_row_without_header_is_rejected(con: duckdb.DuckDBPyConnection) -> None:
    with pytest.raises(duckdb.ConstraintException):
        con.execute(
            """
            INSERT INTO fact_standings_snapshot (
                snapshot_id, whoscored_team_id, whoscored_team_name
            ) VALUES ('missing', 211, 'Brighton')
            """
        )


def test_a_snapshot_can_have_no_standings_rows(con: duckdb.DuckDBPyConnection) -> None:
    _insert_header(con)
    _insert_team(con)

    count = con.execute("SELECT count(*) FROM fact_standings_snapshot").fetchone()
    assert count is not None
    assert count[0] == 0


def test_duplicate_parent_and_content_is_rejected(con: duckdb.DuckDBPyConnection) -> None:
    _insert_header(con)

    with pytest.raises(duckdb.ConstraintException):
        _insert_header(con, snapshot_id="snap_2", observed_at="2026-10-21 10:01:00")


def test_duplicate_stage_and_observed_at_is_rejected(con: duckdb.DuckDBPyConnection) -> None:
    _insert_header(con)

    with pytest.raises(duckdb.ConstraintException):
        _insert_header(con, snapshot_id="snap_2", parent="snap_1", fingerprint="fp_2")


def test_null_parent_is_not_a_uniqueness_guard(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE null_parent_probe (
            parent VARCHAR,
            content VARCHAR,
            UNIQUE (parent, content)
        )
        """
    )
    con.execute("INSERT INTO null_parent_probe VALUES (NULL, 'same')")
    con.execute("INSERT INTO null_parent_probe VALUES (NULL, 'same')")

    count = con.execute("SELECT count(*) FROM null_parent_probe").fetchone()
    assert count is not None
    assert count[0] == 2


def test_check_rejects_negative_and_accepts_null(con: duckdb.DuckDBPyConnection) -> None:
    _insert_header(con)

    with pytest.raises(duckdb.ConstraintException):
        _insert_team(con, apps=-1)

    _insert_team(con, apps=None)
    value = con.execute("SELECT apps_overall FROM fact_team_snapshot").fetchone()
    assert value is not None
    assert value[0] is None


def test_fact_measure_columns_match_the_contract(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute("PRAGMA table_info('fact_team_snapshot')").fetchall()
    names = [row[1] for row in rows]

    assert tuple(names[3:]) == MEASURE_COLUMNS


def test_standings_columns_match_the_contract(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute("PRAGMA table_info('fact_standings_snapshot')").fetchall()
    names = [row[1] for row in rows]

    assert tuple(names[3:]) == STANDINGS_MEASURES


def test_transaction_rolls_back_a_failed_block(con: duckdb.DuckDBPyConnection) -> None:
    with pytest.raises(RuntimeError), transaction(con):
        _insert_header(con)
        raise RuntimeError("fail after insert")

    count = con.execute("SELECT count(*) FROM competition_snapshot").fetchone()
    assert count is not None
    assert count[0] == 0


def test_transaction_commits_a_successful_block(con: duckdb.DuckDBPyConnection) -> None:
    with transaction(con):
        _insert_header(con)

    count = con.execute("SELECT count(*) FROM competition_snapshot").fetchone()
    assert count is not None
    assert count[0] == 1
