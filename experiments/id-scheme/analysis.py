"""Cross-cutting integrity checks and derived KPIs."""

from __future__ import annotations

import importlib
import json
import pathlib
import random
import statistics
import sys
import time

sys.path.insert(0, ".")
import common  # noqa: E402

MODULES = {
    "a": "approaches.a_derived.publish",
    "b": "approaches.b_ulid.publish",
    "bnull": "approaches.b_null.publish",
}


def canonical_checks(obs: list[dict]) -> dict:
    """A cosmetically different payload must not create a new version."""
    base = common.fingerprint(obs)

    shuffled = list(obs)
    random.Random(3).shuffle(shuffled)
    reordered = common.fingerprint(shuffled)

    keys = list(obs[0])
    random.Random(5).shuffle(keys)
    rebuilt = [{k: row[k] for k in keys} for row in obs]
    key_order = common.fingerprint(rebuilt)

    roundtrip = json.loads(json.dumps(obs))
    via_json = common.fingerprint(roundtrip)

    one_changed = [dict(row) for row in obs]
    one_changed[0]["summary_overall_goal"] += 1.0
    changed = common.fingerprint(one_changed)

    return {
        "row_reorder_stable": base == reordered,
        "key_reorder_stable": base == key_order,
        "json_roundtrip_stable": base == via_json,
        "one_value_change_detected": base != changed,
    }


def spurious_version(key: str) -> dict:
    """Publishing the same state twice must not add a snapshot, even reordered."""
    mod = importlib.import_module(MODULES[key])
    base = common.load_base()
    obs = common.synthesize(3, base)
    con = common.fresh(pathlib.Path(f"work/spur-{key}.duckdb"))
    mod.create_schema(con)
    common.publish_once(con, mod, obs[0], common.stamp(0))
    shuffled = list(obs[0])
    random.Random(9).shuffle(shuffled)
    result = common.publish_once(con, mod, shuffled, common.stamp(1))
    count = common.scalar(con, "SELECT count(*) FROM competition_snapshot")
    con.close()
    return {"reason": result["reason"], "snapshots": count}


def rebuild_time(key: str, n: int = 200) -> dict:
    mod = importlib.import_module(MODULES[key])
    base = common.load_base()
    obs = common.synthesize(n, base)
    con = common.fresh(pathlib.Path(f"work/rebuild-{key}.duckdb"))
    mod.create_schema(con)
    start = time.perf_counter()
    ids = []
    for i, o in enumerate(obs):
        ids.append(common.publish_once(con, mod, o, common.stamp(i))["snapshot_id"])
    elapsed = (time.perf_counter() - start) * 1000
    con.execute("CHECKPOINT")
    size = pathlib.Path(f"work/rebuild-{key}.duckdb").stat().st_size
    con.close()
    return {
        "approach": mod.NAME,
        "snapshots": n,
        "rebuild_ms_total": round(elapsed, 1),
        "rebuild_ms_per_snapshot": round(elapsed / n, 3),
        "db_bytes": size,
        "bytes_per_snapshot": round(size / n, 1),
        "bytes_per_fact_row": round(size / (n * 20), 1),
        "id_examples": ids[:3],
        "id_length": len(ids[0]),
    }


def main() -> None:
    base = common.load_base()
    obs = common.synthesize(3, base)
    result = {
        "canonical": canonical_checks(obs[0]),
        "spurious": {k: spurious_version(k) for k in MODULES},
        "rebuild": {k: rebuild_time(k) for k in ("a", "b")},
    }
    path = common.RESULTS / "analysis.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
