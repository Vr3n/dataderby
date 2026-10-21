"""Probe the transaction protocol the publisher will use.

Questions:
1. Does a bare COMMIT after an aborted transaction raise, or silently roll back?
2. Does the connection context manager roll back on exception?
"""

import duckdb


def bare_commit() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    con.execute("BEGIN")
    con.execute("INSERT INTO t VALUES (1)")
    try:
        con.execute("INSERT INTO t VALUES (1)")
    except duckdb.ConstraintException:
        pass
    try:
        con.execute("COMMIT")
        outcome = "commit returned without error"
    except Exception as exc:  # noqa: BLE001 - probe only
        outcome = f"commit raised {type(exc).__name__}"
    print(
        "bare COMMIT after abort:",
        outcome,
        "| rows:",
        con.execute("SELECT count(*) FROM t").fetchone()[0],
    )


def context_manager() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    try:
        with con:
            con.execute("INSERT INTO t VALUES (1)")
            con.execute("INSERT INTO t VALUES (2)")
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    print("context manager rollback | rows:", con.execute("SELECT count(*) FROM t").fetchone()[0])

    with con:
        con.execute("INSERT INTO t VALUES (3)")
    print("context manager commit   | rows:", con.execute("SELECT count(*) FROM t").fetchone()[0])


if __name__ == "__main__":
    bare_commit()
    context_manager()
