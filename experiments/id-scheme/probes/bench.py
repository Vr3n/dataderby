import sys, time, pathlib

sys.path.insert(0, ".")
import common
import importlib

mod = importlib.import_module("approaches.a_derived.publish")
base = common.load_base()
obs = common.synthesize(20, base)
con = common.fresh(pathlib.Path("work/bench.duckdb"))
mod.create_schema(con)
t0 = time.perf_counter()
for i, o in enumerate(obs[:5]):
    t = time.perf_counter()
    common.publish_once(con, mod, o, common.stamp(i))
    print("publish", i, round((time.perf_counter() - t) * 1000, 1), "ms", flush=True)
print("total", round((time.perf_counter() - t0) * 1000, 1))
