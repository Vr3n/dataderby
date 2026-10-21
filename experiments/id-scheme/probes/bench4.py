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
ncols = 2 + len(common.MEASURES)
tuple_sql = ",".join("(" + ",".join("?" * ncols) + ")" for _ in rows)
flat = [v for row in rows for v in row]


def bench(label: str, ddl: str, insert_cols: str, ncols_used: int, use_flat: bool) -> None:
    con = common.fresh(pathlib.Path(f"work/b4-{label}.duckdb"))
    con.execute("CREATE TABLE parent (snapshot_id VARCHAR PRIMARY KEY)")
    con.execute("INSERT INTO parent VALUES ('s1')")
    con.execute(ddl)
    tup = ",".join("(" + ",".join("?" * ncols_used) + ")" for _ in rows)
    payload = flat if use_flat else [v for row in rows for v in row[:ncols_used]]
    start = time.perf_counter()
    con.execute(f"INSERT INTO fact ({insert_cols}) VALUES {tup}", payload)
    print(f"{label:22} {(time.perf_counter() - start) * 1000:9.1f} ms", flush=True)
    con.close()


base_ddl = f"""CREATE TABLE fact (
    snapshot_id VARCHAR NOT NULL,
    team_id INTEGER NOT NULL,
{body}
)"""
bench("nofk_nopk", base_ddl, f"snapshot_id, team_id, {cols}", ncols, True)

fk_ddl = f"""CREATE TABLE fact (
    snapshot_id VARCHAR NOT NULL REFERENCES parent(snapshot_id),
    team_id INTEGER NOT NULL,
{body}
)"""
bench("fk_nopk", fk_ddl, f"snapshot_id, team_id, {cols}", ncols, True)

pk_ddl = f"""CREATE TABLE fact (
    snapshot_id VARCHAR NOT NULL,
    team_id INTEGER NOT NULL,
{body},
    PRIMARY KEY (snapshot_id, team_id)
)"""
bench("nofk_pk", pk_ddl, f"snapshot_id, team_id, {cols}", ncols, True)

both_ddl = f"""CREATE TABLE fact (
    snapshot_id VARCHAR NOT NULL REFERENCES parent(snapshot_id),
    team_id INTEGER NOT NULL,
{body},
    PRIMARY KEY (snapshot_id, team_id)
)"""
bench("fk_pk", both_ddl, f"snapshot_id, team_id, {cols}", ncols, True)

# narrow table: FK + PK, 10 measures only
narrow = ", ".join(c.name for c in common.COLUMNS[:10])
narrow_body = ",\n".join(f"    {c.name} {c.sql_type}" for c in common.COLUMNS[:10])
narrow_rows = [["s1", row[1], *row[2:12]] for row in rows]
narrow_flat = [v for row in narrow_rows for v in row]
narrow_tup = ",".join("(" + ",".join("?" * 12) + ")" for _ in rows)
con = common.fresh(pathlib.Path("work/b4-narrow.duckdb"))
con.execute("CREATE TABLE parent (snapshot_id VARCHAR PRIMARY KEY)")
con.execute("INSERT INTO parent VALUES ('s1')")
con.execute(f"""CREATE TABLE fact (
    snapshot_id VARCHAR NOT NULL REFERENCES parent(snapshot_id),
    team_id INTEGER NOT NULL,
{narrow_body},
    PRIMARY KEY (snapshot_id, team_id))""")
start = time.perf_counter()
con.execute(f"INSERT INTO fact (snapshot_id, team_id, {narrow}) VALUES {narrow_tup}", narrow_flat)
print(f"{'fk_pk_10cols':22} {(time.perf_counter() - start) * 1000:9.1f} ms", flush=True)
con.close()
