"""DuckDB connection, migration, and transaction helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb

_SQL_DIR = Path(__file__).resolve().parents[2] / "sql"
_THREADS = 4


def connect(path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection with the v1 settings.

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
    return con


def migrate(con: duckdb.DuckDBPyConnection, sql_dir: Path = _SQL_DIR) -> None:
    """Apply every ``*.sql`` migration in lexical order.

    The v1 schema uses ``CREATE ... IF NOT EXISTS``, so running this function
    twice is safe. A future migration that is not idempotent must carry its own
    guard.

    Args:
        con: Open DuckDB connection.
        sql_dir: Directory containing the migration files.
    """
    for sql_path in sorted(sql_dir.glob("*.sql")):
        con.execute(sql_path.read_text(encoding="utf-8"))


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
