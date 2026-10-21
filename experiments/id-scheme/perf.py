"""Repeated insert benchmark, so a 5-10% difference is not mistaken for a result."""

from __future__ import annotations

import importlib
import json
import pathlib
import statistics
import sys
import time

sys.path.insert(0, ".")
import common  # noqa: E402

MODULES = {
    "a": "approaches.a_derived.publish",
    "b": "approaches.b_ulid.publish",
}


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]


def measure(key: str, n: int = 150, reps: int = 3) -> dict:
    mod = importlib.import_module(MODULES[key])
    base = common.load_base()
    obs = common.synthesize(n, base)
    latencies: list[float] = []
    for rep in range(reps):
        con = common.fresh(pathlib.Path(f"work/perf-{key}-{rep}.duckdb"))
        mod.create_schema(con)
        for i, o in enumerate(obs):
            start = time.perf_counter()
            common.publish_once(con, mod, o, common.stamp(i))
            latencies.append((time.perf_counter() - start) * 1000)
        con.close()

    noop: list[float] = []
    con = common.fresh(pathlib.Path(f"work/perf-{key}-noop.duckdb"))
    mod.create_schema(con)
    common.publish_once(con, mod, obs[0], common.stamp(0))
    for i in range(60):
        start = time.perf_counter()
        common.publish_once(con, mod, obs[0], common.stamp(i + 1))
        noop.append((time.perf_counter() - start) * 1000)
    con.close()

    body = latencies[10:]  # drop warm-up
    return {
        "approach": mod.NAME,
        "n": n,
        "reps": reps,
        "publishes": len(body),
        "p50_ms": round(statistics.median(body), 3),
        "mean_ms": round(statistics.fmean(body), 3),
        "p95_ms": round(p95(body), 3),
        "noop_p50_ms": round(statistics.median(noop), 3),
        "noop_p95_ms": round(p95(noop), 3),
    }


def main() -> None:
    common.WORK.mkdir(parents=True, exist_ok=True)
    out = [measure("a"), measure("b")]
    path = common.RESULTS / "perf.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
