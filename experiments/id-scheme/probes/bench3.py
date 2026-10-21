import sys, time, pathlib

sys.path.insert(0, ".")
import common, importlib

mod = importlib.import_module("approaches.a_derived.publish")
base = common.load_base()
obs = common.synthesize(2, base)
cols = ", ".join(common.MEASURES)
con = common.fresh(pathlib.Path("work/b3.duckdb"))
mod.create_schema(con)
fp = common.fingerprint(obs[0])
sid = mod.new_id("genesis", common.STAGE, fp)
mod.insert_snapshot(con, sid, "genesis", common.STAGE, fp, common.stamp(0), common.stamp(0))

rows = [[sid, r["team_id"], *[r[c] for c in common.MEASURES]] for r in obs[0]]

# variant 1: executemany (20 separate executions)
s = time.perf_counter()
con.executemany(
    f"INSERT INTO fact_team_snapshot (snapshot_id, team_id, {cols}) VALUES ({','.join('?' * (2 + len(common.MEASURES)))})",
    rows,
)
print("executemany", round((time.perf_counter() - s) * 1000, 1), "ms")

con.execute("DELETE FROM fact_team_snapshot")
# variant 2: one multi-row VALUES statement
tuples = ",".join("(" + ",".join("?" * (2 + len(common.MEASURES))) + ")" for _ in rows)
flat = [v for row in rows for v in row]
s = time.perf_counter()
con.execute(f"INSERT INTO fact_team_snapshot (snapshot_id, team_id, {cols}) VALUES {tuples}", flat)
print("multivalues", round((time.perf_counter() - s) * 1000, 1), "ms")

con.execute("DELETE FROM fact_team_snapshot")
# variant 3: insert from a temp table via executemany on a narrow temp, then insert-select
s = time.perf_counter()
con.execute("CREATE TEMP TABLE stage_fact AS SELECT * FROM fact_team_snapshot LIMIT 0")
con.executemany(
    f"INSERT INTO stage_fact (snapshot_id, team_id, {cols}) VALUES ({','.join('?' * (2 + len(common.MEASURES)))})",
    rows,
)
con.execute("INSERT INTO fact_team_snapshot SELECT * FROM stage_fact")
print("temp+select", round((time.perf_counter() - s) * 1000, 1), "ms")
