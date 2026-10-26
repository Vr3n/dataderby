"""DuckDB connection, migration, and transaction helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import duckdb

_SQL_DIR = Path(__file__).resolve().parents[2] / "sql"
_THREADS = 4

_LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS schema_migration (
    version     VARCHAR PRIMARY KEY,
    checksum    VARCHAR NOT NULL,
    applied_at  TIMESTAMP WITH TIME ZONE NOT NULL
)
"""


class MigrationError(RuntimeError):
    """Raised when the migration ledger and the files on disk disagree."""


def _checksum(path: Path) -> str:
    """Return the SHA-256 of a migration file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _applied(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    """Return the applied versions and their recorded checksums."""
    rows = con.execute("SELECT version, checksum FROM schema_migration").fetchall()
    return {str(version): str(checksum) for version, checksum in rows}


def connect(path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection with the v1 settings.

    Every pipeline timestamp is stored as ``TIMESTAMP WITH TIME ZONE``, so the
    instant is unambiguous regardless of who reads it. The session timezone is
    still pinned to UTC: naive inputs and rendered values then mean UTC by
    default, and ``current_timestamp`` comparisons do not depend on the host.
    The pin is a convenience now, not the correctness mechanism.

    Args:
        path: Database file. Its parent is created for a writable connection.
        read_only: Open the existing file without allowing writes.

    Returns:
        An open DuckDB connection. The caller owns it and must close it.
    """
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(path), read_only=read_only)
    con.execute(f"PRAGMA threads={_THREADS}")
    con.execute("SET TimeZone='UTC'")
    return con


def migrate(con: duckdb.DuckDBPyConnection, sql_dir: Path = _SQL_DIR) -> None:
    """Apply unapplied ``*.sql`` migrations in lexical order, exactly once.

    Each file is identified by its name and recorded with the SHA-256 of its
    bytes. A second call applies nothing. An applied file whose checksum has
    changed is refused, because that means the history was edited after it ran.

    A database created before the ledger existed is adopted: the idempotent
    files run again and are then recorded. The directory passed here must be
    the full history, because an applied version with no file on disk is an
    error rather than a silent deletion.

    Args:
        con: Open DuckDB connection.
        sql_dir: Directory containing the migration files.

    Raises:
        MigrationError: If an applied file changed, or an applied version is
            missing from ``sql_dir``.
        duckdb.Error: If a migration fails; its transaction is rolled back and
            no ledger row is written.
    """
    con.execute(_LEDGER_DDL)
    applied = _applied(con)
    files = sorted(sql_dir.glob("*.sql"))
    on_disk = {path.name for path in files}

    missing = sorted(set(applied) - on_disk)
    if missing:
        raise MigrationError(f"applied migration files are missing: {', '.join(missing)}")

    for sql_path in files:
        version = sql_path.name
        checksum = _checksum(sql_path)

        if version in applied:
            if applied[version] != checksum:
                raise MigrationError(
                    f"{version} changed after it was applied "
                    f"(recorded {applied[version][:12]}, now {checksum[:12]})"
                )
            continue

        with transaction(con):
            con.execute(sql_path.read_text(encoding="utf-8"))
            con.execute(
                "INSERT INTO schema_migration (version, checksum, applied_at) VALUES (?, ?, ?)",
                [version, checksum, datetime.now(UTC)],
            )


@contextmanager
def transaction(con: duckdb.DuckDBPyConnection) -> Iterator[None]:
    """Run a block in one DuckDB transaction.

    A failing block is rolled back and the original exception is re-raised.
    ``COMMIT`` deliberately lives in the success path, never in ``finally``:
    DuckDB's abort state makes a later bare commit silently commit nothing.

    Args:
        con: Open DuckDB connection.

    Yields:
        Control to the caller's block.

    Raises:
        BaseException: The exception raised by the caller's block, after rollback.
    """
    con.execute("BEGIN")
    try:
        yield
    except BaseException:
        con.execute("ROLLBACK")
        raise
    else:
        con.execute("COMMIT")
