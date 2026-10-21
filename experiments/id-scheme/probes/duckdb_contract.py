"""Verify the DuckDB behaviours the implementation plan depends on.

Run: uv run --no-project --with duckdb python experiments/id-scheme/probes/duckdb_contract.py
"""

import duckdb

DDL = """
CREATE TABLE snap (
    snapshot_id VARCHAR PRIMARY KEY,
    parent_snapshot_id VARCHAR NOT NULL DEFAULT 'genesis',
    content_fingerprint VARCHAR NOT NULL,
    UNIQUE (parent_snapshot_id, content_fingerprint)
);
"""


def main() -> None:
    con = duckdb.connect()
    con.execute(DDL)

    first = con.execute(
        "INSERT INTO snap VALUES ('s1', 'genesis', 'fp1') "
        "ON CONFLICT DO NOTHING RETURNING snapshot_id"
    ).fetchall()
    print("first insert returning :", first)

    second = con.execute(
        "INSERT INTO snap VALUES ('s2', 'genesis', 'fp1') "
        "ON CONFLICT DO NOTHING RETURNING snapshot_id"
    ).fetchall()
    print("duplicate returning    :", second)
    print("row count              :", con.execute("SELECT count(*) FROM snap").fetchone()[0])

    # the NULL-root trap, for the record
    con.execute("CREATE TABLE bad (parent VARCHAR, fp VARCHAR, UNIQUE (parent, fp))")
    con.execute("INSERT INTO bad VALUES (NULL, 'x')")
    con.execute("INSERT INTO bad VALUES (NULL, 'x')")
    print("NULL-root duplicates   :", con.execute("SELECT count(*) FROM bad").fetchone()[0])

    # transaction rollback leaves nothing behind
    con.execute("BEGIN")
    con.execute("INSERT INTO snap VALUES ('s3', 's1', 'fp3')")
    con.execute("ROLLBACK")
    print("after rollback         :", con.execute("SELECT count(*) FROM snap").fetchone()[0])

    # does a failed statement abort the whole transaction?
    con.execute("BEGIN")
    con.execute("INSERT INTO snap VALUES ('s4', 's1', 'fp4')")
    try:
        con.execute("INSERT INTO snap VALUES ('s1', 'genesis', 'fpX')")
    except duckdb.ConstraintException as exc:
        print("pk violation           :", type(exc).__name__)
    con.execute("ROLLBACK")
    print("after failed tx        :", con.execute("SELECT count(*) FROM snap").fetchone()[0])

    print("duckdb version         :", duckdb.__version__)


if __name__ == "__main__":
    main()
