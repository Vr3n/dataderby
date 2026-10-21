"""Run the id-scheme test suite against one approach, or compare all results."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import pathlib
import statistics
import subprocess
import sys
import textwrap
import time
from datetime import datetime
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

import common  # noqa: E402

MODULES = {
    "a": "approaches.a_derived.publish",
    "b": "approaches.b_ulid.publish",
    "bnull": "approaches.b_null.publish",
}

SCALE = 500


def median_ms(fn, repeat: int) -> float:
    times = []
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        times.append((time.perf_counter() - start) * 1000)
    return round(statistics.median(times), 3)


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return round(ordered[idx], 3)


def db_shape(con: Any) -> tuple[int, int, int, str | None]:
    return (
        common.scalar(con, "SELECT count(*) FROM competition_snapshot"),
        common.scalar(con, "SELECT count(*) FROM fact_team_snapshot"),
        common.scalar(con, "SELECT count(*) FROM checkpoint"),
        common.scalar(con, "SELECT last_committed_fp FROM checkpoint"),
    )


def latest_rows(con: Any) -> int:
    return common.scalar(
        con,
        """
        SELECT count(*) FROM fact_team_snapshot f
        JOIN (SELECT snapshot_id FROM competition_snapshot
              WHERE stage_id = ?
              ORDER BY accepted_at DESC, snapshot_id DESC LIMIT 1) s
          USING (snapshot_id)
    """,
        [common.STAGE],
    )


def run_child(
    code: str, *, env_extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=180
    )


def suite(key: str, module_name: str) -> dict[str, Any]:
    mod = importlib.import_module(module_name)
    base = common.load_base()
    obs = common.synthesize(8, base)
    tests: list[dict[str, Any]] = []

    def record(
        tid: str,
        name: str,
        expected: Any,
        observed: Any,
        passed: bool | None = None,
        note: str = "",
    ) -> None:
        tests.append(
            {
                "id": tid,
                "name": name,
                "expected": expected,
                "observed": observed,
                "pass": (expected == observed) if passed is None else passed,
                "note": note,
            }
        )

    # ---- T01 first observation -------------------------------------------
    path = common.WORK / f"{key}-t01.duckdb"
    con = common.fresh(path)
    mod.create_schema(con)
    r1 = common.publish_once(con, mod, obs[0], common.stamp(0))
    record(
        "T01",
        "first observation",
        1,
        common.scalar(con, "SELECT count(*) FROM competition_snapshot"),
        note=f"accepted={r1['accepted']}",
    )

    # ---- T02 identical publish -------------------------------------------
    before = db_shape(con)
    r2 = common.publish_once(con, mod, obs[0], common.stamp(1))
    after = db_shape(con)
    record("T02a", "identical publish is a no-op", "no_change", r2["reason"])
    record("T02b", "no rows written on no-change", before, after)
    noop_ms = median_ms(lambda: common.publish_once(con, mod, obs[0], common.stamp(2)), 15)

    # ---- T03 revert A -> B -> A ------------------------------------------
    common.publish_once(con, mod, obs[1], common.stamp(3))
    common.publish_once(con, mod, obs[0], common.stamp(4))
    record(
        "T03",
        "revert A->B->A is recorded",
        3,
        common.scalar(con, "SELECT count(*) FROM competition_snapshot"),
    )
    con.close()

    # ---- T04 rollback / process kill -------------------------------------
    path = common.WORK / f"{key}-t04.duckdb"
    con = common.fresh(path)
    mod.create_schema(con)
    common.publish_once(con, mod, obs[0], common.stamp(0))
    fp1 = common.fingerprint(obs[1])
    con.execute("BEGIN")
    sid = mod.new_id(common.GENESIS, common.STAGE, fp1)
    mod.insert_snapshot(
        con, sid, common.GENESIS, common.STAGE, fp1, common.stamp(1), common.stamp(1)
    )
    common.insert_fact(con, sid, obs[1])
    con.execute("ROLLBACK")
    record(
        "T04a",
        "rollback leaves no partial rows",
        (1, 20),
        (
            common.scalar(con, "SELECT count(*) FROM competition_snapshot"),
            common.scalar(con, "SELECT count(*) FROM fact_team_snapshot"),
        ),
    )
    con.close()

    kill_db = common.WORK / f"{key}-t04b.duckdb"
    code = textwrap.dedent(f"""
        import importlib, os, pathlib, sys
        sys.path.insert(0, {str(ROOT)!r})
        import common
        mod = importlib.import_module({module_name!r})
        con = common.fresh(pathlib.Path({str(kill_db)!r}))
        mod.create_schema(con)
        base = common.load_base()
        obs = common.synthesize(1, base)[0]
        fp = common.fingerprint(obs)
        con.execute("BEGIN")
        sid = mod.new_id(common.GENESIS, common.STAGE, fp)
        mod.insert_snapshot(con, sid, common.GENESIS, common.STAGE, fp,
                            common.stamp(0), common.stamp(0))
        common.insert_fact(con, sid, obs)
        os._exit(1)
    """)
    run_child(code)
    con = duckdb.connect(str(kill_db))
    record(
        "T04b",
        "killed process leaves no committed rows",
        0,
        common.scalar(con, "SELECT count(*) FROM competition_snapshot"),
    )
    con.close()

    # ---- T05 stale checkpoint (DB is the last line of defence) ------------
    path = common.WORK / f"{key}-t05.duckdb"
    con = common.fresh(path)
    mod.create_schema(con)
    common.publish_once(con, mod, obs[0], common.stamp(0))
    common.publish_once(con, mod, obs[1], common.stamp(1))
    fp0 = common.fingerprint(obs[0])
    sid0 = common.scalar(
        con, "SELECT snapshot_id FROM competition_snapshot WHERE content_fingerprint = ?", [fp0]
    )
    con.execute("UPDATE checkpoint SET last_committed_fp = ?, last_accepted_id = ?", [fp0, sid0])
    common.publish_once(con, mod, obs[1], common.stamp(2))
    record(
        "T05",
        "stale checkpoint cannot duplicate an existing edge",
        2,
        common.scalar(con, "SELECT count(*) FROM competition_snapshot"),
    )
    con.close()

    # ---- T06 rebuild from raw --------------------------------------------
    seq = obs[:5]
    rebuild: dict[str, list[str]] = {}
    for label in ("original", "rebuilt"):
        p = common.WORK / f"{key}-t06-{label}.duckdb"
        c = common.fresh(p)
        mod.create_schema(c)
        ids = []
        for i, o in enumerate(seq):
            ids.append(common.publish_once(c, mod, o, common.stamp(i))["snapshot_id"])
        rebuild[label] = ids
        if label == "rebuilt":
            pinned = rebuild["original"][2]
            rows = common.scalar(
                c, "SELECT count(*) FROM fact_team_snapshot WHERE snapshot_id = ?", [pinned]
            )
            rows_by_time = common.scalar(
                c,
                "SELECT count(*) FROM fact_team_snapshot f "
                "JOIN competition_snapshot s USING (snapshot_id) "
                "WHERE s.stage_id = ? AND s.observed_at = ?",
                [common.STAGE, common.stamp(2)],
            )
        c.close()
    record(
        "T06a", "rebuild reproduces the same ids", True, rebuild["original"] == rebuild["rebuilt"]
    )
    record("T06b", "a report pinned to the original id resolves after rebuild", 20, rows)
    record(
        "T06c", "a report pinned to (stage, observed_at) resolves after rebuild", 20, rows_by_time
    )

    # ---- T07 same content, different parent ------------------------------
    path = common.WORK / f"{key}-t07.duckdb"
    con = common.fresh(path)
    mod.create_schema(con)
    for i, o in enumerate((obs[0], obs[1], obs[0])):
        common.publish_once(con, mod, o, common.stamp(i))
    record(
        "T07",
        "same content under a different parent is a new row",
        2,
        common.scalar(
            con,
            "SELECT count(*) FROM competition_snapshot WHERE content_fingerprint = ?",
            [common.fingerprint(obs[0])],
        ),
    )
    con.close()

    # ---- T08 NULL parent trap (bypasses the checkpoint) -------------------
    path = common.WORK / f"{key}-t08.duckdb"
    con = common.fresh(path)
    mod.create_schema(con)
    fp = common.fingerprint(obs[0])
    for i in range(2):
        sid = mod.new_id(common.GENESIS, common.STAGE, fp)
        mod.insert_snapshot(
            con, sid, common.GENESIS, common.STAGE, fp, common.stamp(i), common.stamp(i)
        )
    record(
        "T08",
        "root edge deduped by the database",
        1,
        common.scalar(con, "SELECT count(*) FROM competition_snapshot"),
    )
    con.close()

    # ---- T09 concurrent writers ------------------------------------------
    path = common.WORK / f"{key}-t09.duckdb"
    con = common.fresh(path)
    mod.create_schema(con)
    common.publish_once(con, mod, obs[0], common.stamp(0))
    con.close()
    child = textwrap.dedent(f"""
        import duckdb, sys, time
        con = duckdb.connect({str(path)!r})
        con.execute("BEGIN")
        con.execute("INSERT INTO checkpoint (stage_id) VALUES ('lock-probe')")
        print("locked", flush=True)
        time.sleep(12)
        con.execute("ROLLBACK")
    """)
    proc = subprocess.Popen(
        [sys.executable, "-c", child], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    line = proc.stdout.readline().strip() if proc.stdout else ""
    probe = textwrap.dedent(f"""
        import duckdb
        con = duckdb.connect({str(path)!r})
        con.execute("INSERT INTO checkpoint (stage_id) VALUES ('second-writer')")
        print("WROTE")
    """)
    refused, error = True, "blocked on the file lock (timed out after 6s)"
    try:
        out = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, text=True, timeout=6
        )
        if "WROTE" in out.stdout:
            refused = False
        else:
            error = (out.stderr.strip().splitlines() or [""])[-1][:160]
    except subprocess.TimeoutExpired:
        pass
    finally:
        proc.kill()
        proc.wait(timeout=10)
    record(
        "T09",
        "second writer is refused",
        True,
        refused,
        passed=refused,
        note=(f"child={line!r} error={error!r}"),
    )

    # ---- T10 scale + collisions ------------------------------------------
    path = common.WORK / f"{key}-t10.duckdb"
    con = common.fresh(path)
    mod.create_schema(con)
    big = common.synthesize(SCALE, base)
    latencies: list[float] = []
    for i, o in enumerate(big):
        start = time.perf_counter()
        common.publish_once(con, mod, o, common.stamp(i))
        latencies.append((time.perf_counter() - start) * 1000)
    con.execute("CHECKPOINT")
    total_snapshots = common.scalar(con, "SELECT count(*) FROM competition_snapshot")
    distinct_ids = common.scalar(
        con, "SELECT count(DISTINCT snapshot_id) FROM competition_snapshot"
    )
    record("T10", f"{SCALE} observations -> {SCALE} distinct ids", SCALE, total_snapshots)
    record("T10b", "no id collisions", distinct_ids, SCALE)

    # ---- T11 cross-process determinism -----------------------------------
    det: dict[str, list[str]] = {}
    for seed in ("0", "1"):
        p = common.WORK / f"{key}-t11-{seed}.duckdb"
        code = textwrap.dedent(f"""
            import importlib, json, pathlib, sys
            sys.path.insert(0, {str(ROOT)!r})
            import common
            mod = importlib.import_module({module_name!r})
            con = common.fresh(pathlib.Path({str(p)!r}))
            mod.create_schema(con)
            base = common.load_base()
            obs = common.synthesize(5, base)
            ids = [common.publish_once(con, mod, o, common.stamp(i))["snapshot_id"]
                   for i, o in enumerate(obs)]
            print(json.dumps(ids))
        """)
        out = run_child(code, env_extra={"PYTHONHASHSEED": seed}).stdout.strip()
        det[seed] = json.loads(out.splitlines()[-1])
    record("T11", "ids independent of process/hash seed", True, det["0"] == det["1"])

    # ---- T12 latest query ------------------------------------------------
    expected_apps = sum(int(r["overall_apps"]) for r in big[-1])
    latest_apps = common.scalar(
        con,
        """
        SELECT sum(f.overall_apps) FROM fact_team_snapshot f
        JOIN (SELECT snapshot_id FROM competition_snapshot
              WHERE stage_id = ?
              ORDER BY accepted_at DESC, snapshot_id DESC LIMIT 1) s
          USING (snapshot_id)
    """,
        [common.STAGE],
    )
    record("T12a", "latest state returns 20 rows", 20, latest_rows(con))
    record("T12b", "latest state values are correct", expected_apps, latest_apps)
    latest_query_ms = median_ms(lambda: latest_rows(con), 30)

    # ---- T13 delta -------------------------------------------------------
    delta_sql = """
        WITH o AS (
            SELECT f.team_id, f.overall_apps,
                   LAG(f.overall_apps) OVER (
                       PARTITION BY f.team_id
                       ORDER BY s.accepted_at, s.snapshot_id) AS prev
            FROM fact_team_snapshot f
            JOIN competition_snapshot s USING (snapshot_id)
        )
        SELECT count(*) FROM o WHERE prev IS NOT NULL AND overall_apps - prev <> 1
    """
    record("T13a", "delta equals 1 for every consecutive pair", 0, common.scalar(con, delta_sql))
    record(
        "T13b",
        "first observation has no delta",
        20,
        common.scalar(
            con,
            """
               WITH o AS (
                   SELECT f.team_id,
                          LAG(f.overall_apps) OVER (
                              PARTITION BY f.team_id
                              ORDER BY s.accepted_at, s.snapshot_id) AS prev
                   FROM fact_team_snapshot f
                   JOIN competition_snapshot s USING (snapshot_id))
               SELECT count(*) FROM o WHERE prev IS NULL""",
        ),
    )
    delta_query_ms = median_ms(lambda: common.scalar(con, delta_sql), 10)

    # ---- T14 FK ----------------------------------------------------------
    fk_refused = False
    try:
        con.execute("INSERT INTO fact_team_snapshot (snapshot_id, team_id) VALUES ('nope', 1)")
    except Exception:  # noqa: BLE001
        fk_refused = True
    record("T14", "orphan fact row is rejected", True, fk_refused, passed=fk_refused)

    # ---- T16 NULL is not zero --------------------------------------------
    t16_path = common.WORK / f"{key}-t16.duckdb"
    c = common.fresh(t16_path)
    mod.create_schema(c)
    missing = [dict(row) for row in obs[0]]
    missing[0]["summary_overall_goal"] = None
    common.publish_once(c, mod, missing, common.stamp(0))
    stored = common.scalar(
        c,
        "SELECT summary_overall_goal FROM fact_team_snapshot WHERE team_id = ?",
        [missing[0]["team_id"]],
    )
    record("T16a", "a missing value is stored as NULL", None, stored)
    record(
        "T16b",
        "exactly one NULL cell, never a zero",
        1,
        common.scalar(
            c, "SELECT count(*) FROM fact_team_snapshot WHERE summary_overall_goal IS NULL"
        ),
    )
    c.close()

    # ---- T15 id properties ----------------------------------------------
    ids = [mod.new_id("genesis", common.STAGE, f"probe-{i}") for i in range(1000)]
    ascending = sum(1 for a, b in zip(ids, ids[1:]) if b > a)
    record("T15", "id collision-free over 1000", 1000, len(set(ids)))
    id_length = len(ids[0])

    con.execute("CHECKPOINT")
    con.close()
    db_bytes = path.stat().st_size

    metrics = {
        "approach": mod.NAME,
        "scheme": mod.SCHEME,
        "duckdb": duckdb.__version__,
        "python": sys.version.split()[0],
        "scale": SCALE,
        "insert_ms_total": round(sum(latencies), 1),
        "insert_ms_p50": round(statistics.median(latencies), 3),
        "insert_ms_p95": p95(latencies),
        "noop_ms_p50": round(noop_ms, 3),
        "latest_query_ms_p50": latest_query_ms,
        "delta_query_ms_p50": delta_query_ms,
        "db_bytes": db_bytes,
        "id_length": id_length,
        "id_ascending_ratio": round(ascending / 999, 3),
        "snapshots": total_snapshots,
        "fact_rows": 20 * SCALE,
    }
    return {"approach": key, "module": module_name, "tests": tests, "metrics": metrics}


def compare() -> None:
    rows = []
    for key in MODULES:
        path = common.RESULTS / f"{key}.json"
        if path.exists():
            rows.append(json.loads(path.read_text(encoding="utf-8")))
    if not rows:
        raise SystemExit("no results to compare")

    lines = [
        "# id scheme — measured results",
        "",
        f"DuckDB 1.5.6 · Python 3.12.13 · scale {rows[0]['metrics']['scale']} observations",
        "",
    ]
    tests = {t["id"]: t for t in rows[0]["tests"]}
    header = "| test | " + " | ".join(r["metrics"]["approach"] for r in rows) + " |"
    lines += [header, "|" + "---|" * (len(rows) + 1)]
    for tid, first in tests.items():
        cells = []
        for r in rows:
            t = next(x for x in r["tests"] if x["id"] == tid)
            cells.append(("PASS " if t["pass"] else "FAIL ") + str(t["observed"]))
        lines.append(f"| {tid} {first['name']} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "| metric | " + " | ".join(r["metrics"]["approach"] for r in rows) + " |",
        "|" + "---|" * (len(rows) + 1),
    ]
    for key in rows[0]["metrics"]:
        if key in {"approach", "scheme"}:
            continue
        lines.append(f"| {key} | " + " | ".join(str(r["metrics"][key]) for r in rows) + " |")
    (common.RESULTS / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (common.RESULTS / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approach", choices=sorted(MODULES))
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    common.WORK.mkdir(parents=True, exist_ok=True)
    common.RESULTS.mkdir(parents=True, exist_ok=True)

    if args.compare:
        compare()
        return
    if not args.approach:
        parser.error("--approach or --compare")

    result = suite(args.approach, MODULES[args.approach])
    out = common.RESULTS / f"{args.approach}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    passed = sum(1 for t in result["tests"] if t["pass"])
    print(f"{result['metrics']['approach']}: {passed}/{len(result['tests'])} passed")
    for t in result["tests"]:
        if not t["pass"]:
            print(
                f"  FAIL {t['id']} {t['name']}: expected {t['expected']!r} "
                f"observed {t['observed']!r} {t['note']}"
            )
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__":
    main()
