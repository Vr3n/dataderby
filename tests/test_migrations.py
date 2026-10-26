"""Migration ledger tests: ordering, idempotence, tamper detection, rollback."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from dataderby.db import MigrationError, connect, migrate


@pytest.fixture
def con(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = connect(tmp_path / "migrations.duckdb")
    try:
        yield connection
    finally:
        connection.close()


def _write(directory: Path, name: str, sql: str) -> Path:
    path = directory / name
    path.write_text(sql, encoding="utf-8")
    return path


def _ledger(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    return con.execute("SELECT version, checksum FROM schema_migration ORDER BY version").fetchall()


def test_fresh_database_applies_every_file_and_records_its_checksum(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    first = _write(sql_dir, "001_first.sql", "CREATE TABLE first (id INTEGER);")
    second = _write(sql_dir, "002_second.sql", "CREATE TABLE second (id INTEGER);")

    migrate(con, sql_dir)

    assert [version for version, _ in _ledger(con)] == ["001_first.sql", "002_second.sql"]
    assert _ledger(con) == [
        ("001_first.sql", hashlib.sha256(first.read_bytes()).hexdigest()),
        ("002_second.sql", hashlib.sha256(second.read_bytes()).hexdigest()),
    ]
    assert con.execute("SELECT count(*) FROM first").fetchone() == (0,)
    assert con.execute("SELECT count(*) FROM second").fetchone() == (0,)


def test_second_run_applies_nothing_and_keeps_the_original_timestamps(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    _write(sql_dir, "001_first.sql", "CREATE TABLE first (id INTEGER);")

    migrate(con, sql_dir)
    before = con.execute("SELECT version, checksum, applied_at FROM schema_migration").fetchall()

    migrate(con, sql_dir)

    assert (
        con.execute("SELECT version, checksum, applied_at FROM schema_migration").fetchall()
        == before
    )


def test_a_changed_applied_file_is_refused(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    path = _write(sql_dir, "001_first.sql", "CREATE TABLE first (id INTEGER);")
    migrate(con, sql_dir)

    path.write_text("CREATE TABLE first (id INTEGER, note VARCHAR);", encoding="utf-8")

    with pytest.raises(
        MigrationError, match=re.escape("001_first.sql changed after it was applied")
    ):
        migrate(con, sql_dir)


def test_a_missing_applied_file_is_refused(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    path = _write(sql_dir, "001_first.sql", "CREATE TABLE first (id INTEGER);")
    migrate(con, sql_dir)

    path.unlink()

    with pytest.raises(
        MigrationError,
        match=re.escape("applied migration files are missing: 001_first.sql"),
    ):
        migrate(con, sql_dir)


def test_a_failing_migration_leaves_no_table_and_no_ledger_row(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    _write(sql_dir, "001_first.sql", "CREATE TABLE first (id INTEGER);")
    _write(
        sql_dir,
        "002_broken.sql",
        "CREATE TABLE half (id INTEGER);\nTHIS IS NOT SQL;",
    )

    with pytest.raises(duckdb.Error):
        migrate(con, sql_dir)

    tables = {
        name
        for (name,) in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }
    assert "first" in tables
    assert "half" not in tables
    assert [version for version, _ in _ledger(con)] == ["001_first.sql"]


def test_a_database_without_a_ledger_is_adopted_and_recorded(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    _write(sql_dir, "001_first.sql", "CREATE TABLE IF NOT EXISTS first (id INTEGER);")

    # A database created before the ledger existed: the table is there, the
    # ledger is not.
    con.execute("CREATE TABLE first (id INTEGER)")
    assert "schema_migration" not in {
        name
        for (name,) in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }

    migrate(con, sql_dir)

    assert [version for version, _ in _ledger(con)] == ["001_first.sql"]


def test_files_are_applied_in_lexical_order(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    _write(sql_dir, "001_create.sql", "CREATE TABLE ordered (id INTEGER);")
    _write(sql_dir, "002_insert.sql", "INSERT INTO ordered VALUES (1);")

    migrate(con, sql_dir)

    assert con.execute("SELECT id FROM ordered").fetchall() == [(1,)]
