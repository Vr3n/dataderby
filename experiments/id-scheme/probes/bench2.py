import sys, time, pathlib

sys.path.insert(0, ".")
import common, importlib

mod = importlib.import_module("approaches.a_derived.publish")
base = common.load_base()
obs = common.synthesize(3, base)
con = common.fresh(pathlib.Path("work/b2.duckdb"))
mod.create_schema(con)


def t(label, fn):
    s = time.perf_counter()
    r = fn()
    print(f"{label:22} {(time.perf_counter() - s) * 1000:9.1f} ms", flush=True)
    return r


fp = t("fingerprint", lambda: common.fingerprint(obs[0]))
for i, o in enumerate(obs):
    fp = common.fingerprint(o)
    sid = mod.new_id("genesis" if i == 0 else prev, common.STAGE, fp)
    t("  begin", lambda: con.execute("BEGIN"))
    t(
        "  insert_snapshot",
        lambda: mod.insert_snapshot(
            con,
            sid,
            "genesis" if i == 0 else prev,
            common.STAGE,
            fp,
            common.stamp(i),
            common.stamp(i),
        ),
    )
    t("  insert_fact", lambda: common.insert_fact(con, sid, o))
    t(
        "  checkpoint",
        lambda: con.execute(
            "INSERT INTO checkpoint (stage_id,last_committed_fp,last_accepted_id) VALUES (?,?,?) ON CONFLICT (stage_id) DO UPDATE SET last_committed_fp=excluded.last_committed_fp, last_accepted_id=excluded.last_accepted_id",
            [common.STAGE, fp, sid],
        ),
    )
    t("  commit", lambda: con.execute("COMMIT"))
    prev = sid
