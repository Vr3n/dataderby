"""Does a mid-chain backfill re-address the snapshots after it?

A derived id is a function of its parent, so inserting an observation in the middle
changes the parent of every later snapshot. This measures the blast radius.
"""

from __future__ import annotations

import importlib
import json
import pathlib
import sys

sys.path.insert(0, ".")
import duckdb  # noqa: E402

import common  # noqa: E402

MODULES = {"a": "approaches.a_derived.publish", "b": "approaches.b_ulid.publish"}


def build(key: str, sequence: list[list[dict]], label: str) -> tuple[list[str], pathlib.Path]:
    mod = importlib.import_module(MODULES[key])
    path = common.WORK / f"backfill-{key}-{label}.duckdb"
    con = common.fresh(path)
    mod.create_schema(con)
    ids = [
        common.publish_once(con, mod, obs, common.stamp(i))["snapshot_id"]
        for i, obs in enumerate(sequence)
    ]
    con.close()
    return ids, path


def main() -> None:
    base = common.load_base()
    obs = common.synthesize(12, base)
    # an observation we "missed" first time round: a distinct state between obs[0] and obs[1]
    backfill = [dict(row) for row in obs[0]]
    for row in backfill:
        row["summary_overall_goal"] = float(row["summary_overall_goal"]) + 0.5

    out = {}
    for key in ("a", "b"):
        ids_before, _ = build(key, obs[:6], "straight")
        ids_after, path_after = build(key, [obs[0], backfill, *obs[1:6]], "backfilled")

        # snapshot i in the straight build corresponds to i+1 in the backfilled build
        tail_before = ids_before[1:]
        tail_after = ids_after[2:]

        con = duckdb.connect(str(path_after), read_only=True)
        out[key] = {
            "approach": key,
            "tail_ids_equal": tail_before == tail_after,
            "changed_of_tail": sum(1 for x, y in zip(tail_before, tail_after) if x != y),
            "tail_size": len(tail_before),
            "pinned_by_id_rows": common.scalar(
                con,
                "SELECT count(*) FROM fact_team_snapshot WHERE snapshot_id = ?",
                [tail_before[0]],
            ),
            "pinned_by_time_rows": common.scalar(
                con,
                "SELECT count(*) FROM fact_team_snapshot f "
                "JOIN competition_snapshot s USING (snapshot_id) "
                "WHERE s.stage_id = ? AND s.observed_at = ?",
                [common.STAGE, common.stamp(1)],
            ),
        }
        con.close()

    (common.RESULTS / "backfill.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
