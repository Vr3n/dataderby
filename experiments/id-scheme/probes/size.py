import sys, pathlib, importlib

sys.path.insert(0, ".")
import common

mod = importlib.import_module("approaches.b_ulid.publish")
base = common.load_base()
for n in (100, 300, 500):
    obs = common.synthesize(n, base)
    p = common.WORK / f"size-{n}.duckdb"
    con = common.fresh(p)
    mod.create_schema(con)
    for i, o in enumerate(obs):
        common.publish_once(con, mod, o, common.stamp(i))
    con.execute("CHECKPOINT")
    con.close()
    size = p.stat().st_size
    print(n, size, round(size / n), "B/snapshot", round(size / (n * 20), 1), "B/row")
