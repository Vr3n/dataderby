"""One coherent measurement pass for the deck: perf, storage, address stability."""

from __future__ import annotations

import importlib
import json
import pathlib
import statistics
import sys
import time

sys.path.insert(0, ".")
import common  # noqa: E402

MODULES = {"a": "approaches.a_derived.publish", "b": "approaches.b_ulid.publish"}
N = 300


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]


def measure(key: str) -> dict:
    mod = importlib.import_module(MODULES[key])
    base = common.load_base()
    obs = common.synthesize(N, base)
    path = common.WORK / f"final-{key}.duckdb"
    con = common.fresh(path)
    mod.create_schema(con)

    latencies: list[float] = []
    ids: list[str] = []
    for i, o in enumerate(obs):
        start = time.perf_counter()
        ids.append(common.publish_once(con, mod, o, common.stamp(i))["snapshot_id"])
        latencies.append((time.perf_counter() - start) * 1000)

    latest_sql = """
        SELECT count(*) FROM fact_team_snapshot f
        JOIN (SELECT snapshot_id FROM competition_snapshot
              WHERE stage_id = ? ORDER BY accepted_at DESC, snapshot_id DESC
              LIMIT 1) s USING (snapshot_id)
    """
    latest = []
    for _ in range(50):
        start = time.perf_counter()
        common.scalar(con, latest_sql, [common.STAGE])
        latest.append((time.perf_counter() - start) * 1000)

    delta_sql = """
        WITH o AS (
            SELECT f.overall_apps,
                   LAG(f.overall_apps) OVER (
                       PARTITION BY f.team_id
                       ORDER BY s.accepted_at, s.snapshot_id) AS prev
            FROM fact_team_snapshot f
            JOIN competition_snapshot s USING (snapshot_id))
        SELECT count(*) FROM o WHERE prev IS NOT NULL AND overall_apps - prev <> 1
    """
    delta = []
    for _ in range(20):
        start = time.perf_counter()
        common.scalar(con, delta_sql)
        delta.append((time.perf_counter() - start) * 1000)

    con.execute("CHECKPOINT")
    con.close()
    size = path.stat().st_size

    # rebuild in a second database from the same raw sequence
    rebuilt_path = common.WORK / f"final-{key}-rebuilt.duckdb"
    con2 = common.fresh(rebuilt_path)
    mod.create_schema(con2)
    rebuilt_ids = [
        common.publish_once(con2, mod, o, common.stamp(i))["snapshot_id"] for i, o in enumerate(obs)
    ]
    pinned_at = common.scalar(
        con2,
        "SELECT count(*) FROM fact_team_snapshot f "
        "JOIN competition_snapshot s USING (snapshot_id) "
        "WHERE s.stage_id = ? AND s.observed_at = ?",
        [common.STAGE, common.stamp(100)],
    )
    pinned_id = common.scalar(
        con2, "SELECT count(*) FROM fact_team_snapshot WHERE snapshot_id = ?", [ids[100]]
    )
    con2.close()

    body = latencies[5:]
    return {
        "approach": mod.NAME,
        "scheme": mod.SCHEME,
        "snapshots": N,
        "fact_rows": N * 20,
        "insert_ms_p50": round(statistics.median(body), 2),
        "insert_ms_p95": round(p95(body), 2),
        "insert_per_second": round(1000 / statistics.median(body), 1),
        "latest_ms_p50": round(statistics.median(latest), 2),
        "delta_ms_p50": round(statistics.median(delta), 2),
        "db_bytes": size,
        "bytes_per_snapshot": round(size / N, 0),
        "bytes_per_fact_row": round(size / (N * 20), 0),
        "id_length": len(ids[0]),
        "id_example": ids[0],
        "rebuild_ids_equal": ids == rebuilt_ids,
        "pinned_by_id_rows": pinned_id,
        "pinned_by_time_rows": pinned_at,
        "id_ascending_ratio": round(
            sum(1 for a, b in zip(ids, ids[1:]) if b > a) / (len(ids) - 1), 3
        ),
    }


def main() -> None:
    common.WORK.mkdir(parents=True, exist_ok=True)
    out = [measure("a"), measure("b")]
    (common.RESULTS / "final.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
