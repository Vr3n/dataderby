import pathlib
import sys
import time

sys.path.insert(0, ".")
import common  # noqa: E402
import importlib  # noqa: E402

mod = importlib.import_module("approaches.a_derived.publish")
base = common.load_base()
obs = common.synthesize(1, base)
cols = ", ".join(common.MEASURES)
body = ",\n".join(f"    {c.name} {c.sql_type}" for c in common.COLUMNS)
rows = [["s1", r["team_id"], *[r[c] for c in common.MEASURES]] for r in obs[0]]


def make(label: str) -> "duckdb.DuckDBPyConnection":
    import duckdb

    con = common.fresh(pathlib.Path(f"work/b5-{label}.duckdb"))
    con.execute("CREATE TABLE parent (snapshot_id VARCHAR PRIMARY KEY)")
    con.execute("INSERT INTO parent VALUES ('s1')")
    con.execute(f"CREATE TABLE fact (snapshot_id VARCHAR, team_id INTEGER, {body})")
    return con


def timed(label: str, con, sql, payload=None) -> None:
    start = time.perf_counter()
    if payload is None:
        con.execute(sql)
    else:
        con.execute(sql, payload)
    print(f"{label:34} {(time.perf_counter() - start) * 1000:9.1f} ms", flush=True)


con = make("p20")
tup = ",".join("(" + ",".join("?" * 62) + ")" for _ in rows)
timed(
    "20 rows x 62 params", con, f"INSERT INTO fact VALUES {tup}", [v for row in rows for v in row]
)

con = make("p1")
tup1 = "(" + ",".join("?" * 62) + ")"
timed("1 row x 62 params", con, f"INSERT INTO fact VALUES {tup1}", rows[0])


def lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


con = make("lit")
tup_lit = ",".join("(" + ",".join(lit(v) for v in row) + ")" for row in rows)
timed("20 rows literal SQL", con, f"INSERT INTO fact VALUES {tup_lit}")

con = make("copy")
import csv
import tempfile

csv_path = pathlib.Path(tempfile.gettempdir()) / "opencode" / "fact.csv"
with csv_path.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.writer(fh)
    for row in rows:
        writer.writerow(row)
timed("20 rows COPY", con, f"COPY fact FROM '{csv_path.as_posix()}' (FORMAT csv, HEADER false)")

# executemany on a narrow table for comparison
con = make("execmany")
start = time.perf_counter()
con.executemany(f"INSERT INTO fact VALUES ({','.join('?' * 62)})", rows)
print(f"{'20 rows executemany':34} {(time.perf_counter() - start) * 1000:9.1f} ms", flush=True)
