"""Follow-up probe: DuckDB does not auto-abort a transaction after a constraint error.

This matters for the publish loop: an ``except`` block that swallows the error and
later commits would commit partial work. The plan must mandate an explicit rollback.
"""

import duckdb


def main() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v VARCHAR)")

    con.execute("BEGIN")
    con.execute("INSERT INTO t VALUES (1, 'a')")
    try:
        con.execute("INSERT INTO t VALUES (1, 'b')")
    except duckdb.ConstraintException:
        pass

    # if DuckDB auto-aborted, this would raise TransactionException on a closed tx
    still_open = True
    try:
        con.execute("INSERT INTO t VALUES (2, 'c')")
    except Exception as exc:  # noqa: BLE001 - probe only
        still_open = False
        print("second insert failed:", type(exc).__name__, exc)

    con.execute("COMMIT")
    rows = con.execute("SELECT * FROM t ORDER BY id").fetchall()
    print("transaction still usable after error:", still_open)
    print("committed rows:", rows)


if __name__ == "__main__":
    main()
