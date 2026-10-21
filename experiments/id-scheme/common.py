"""Shared fixture loader, canonicaliser, schema and publish loop.

Both approaches are measured through this module. Nothing approach-specific lives here
except the two schema switches (`unique_edge`, `parent_nullable`).
"""

from __future__ import annotations

import hashlib
import json
import math
import pathlib
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Sequence

import duckdb

ROOT = pathlib.Path(__file__).resolve().parent
CAPS = ROOT / "fixtures" / "caps"
WORK = ROOT / "work"
RESULTS = ROOT / "results"

GENESIS = "genesis"
STAGE = "4:11213:25662"

SECTIONS = ("summary", "defensive", "offensive")
VIEWS = ("overall", "home", "away")
CAP_PREFIX = {"summary": "all", "defensive": "defensive", "offensive": "offensive"}
CAP_VIEW = {"overall": "Overall", "home": "Home", "away": "Away"}

SUMMARY_OWN = ("goal", "yellowCard", "redCard", "possession", "passSuccess", "aerialWonPerGame")
DEFENSIVE_OWN = (
    "shotsConcededPerGame",
    "tacklePerGame",
    "interceptionPerGame",
    "foulsPerGame",
    "offsideGivenPerGame",
)
OFFENSIVE_OWN = ("shotOnTargetPerGame", "dribbleWonPerGame", "foulGivenPerGame")
OWN = {"summary": SUMMARY_OWN, "defensive": DEFENSIVE_OWN, "offensive": OFFENSIVE_OWN}

ADDITIVE = ("apps", "goal", "yellowCard", "redCard")


@dataclass(frozen=True)
class Column:
    name: str
    sql_type: str
    section: str
    view: str
    metric: str


def columns() -> list[Column]:
    """The 60 stored measures, in table order."""
    out: list[Column] = []
    for view in VIEWS:  # 9 shared, deduped
        out.append(Column(f"{view}_apps", "INTEGER", "summary", view, "apps"))
    for view in VIEWS:
        out.append(Column(f"{view}_rating", "DOUBLE", "summary", view, "rating"))
    for view in VIEWS:
        out.append(Column(f"{view}_shotsPerGame", "DOUBLE", "summary", view, "shotsPerGame"))
    for section in SECTIONS:  # 9, one per section/view
        for view in VIEWS:
            out.append(Column(f"{section}_{view}_ranking", "INTEGER", section, view, "ranking"))
    for section in SECTIONS:  # 42 section-owned
        for view in VIEWS:
            for metric in OWN[section]:
                out.append(Column(f"{section}_{view}_{metric}", "DOUBLE", section, view, metric))
    return out


COLUMNS = columns()
MEASURES = [c.name for c in COLUMNS]


def _read_caps() -> dict[tuple[str, str], dict[int, dict[str, Any]]]:
    out: dict[tuple[str, str], dict[int, dict[str, Any]]] = {}
    for section in SECTIONS:
        for view in VIEWS:
            path = CAPS / f"{CAP_PREFIX[section]}__{CAP_VIEW[view]}.json"
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            out[(section, view)] = {r["teamId"]: r for r in payload["teamTableStats"]}
    return out


def load_base() -> list[dict[str, Any]]:
    """Parse the nine captures into 20 rows of 60 measures.

    Also re-verifies the column-ownership assumptions the schema depends on.
    """
    caps = _read_caps()
    team_sets = [set(rows) for rows in caps.values()]
    if len({frozenset(s) for s in team_sets}) != 1:
        raise AssertionError("the nine captures disagree on the team set")

    teams = sorted(team_sets[0])
    rows: list[dict[str, Any]] = []
    for team in teams:
        row: dict[str, Any] = {"team_id": team}
        for col in COLUMNS:
            src = caps[(col.section, col.view)][team]
            row[col.name] = src[col.metric]

        # ownership checks: one owner, the others must agree
        for view in VIEWS:
            a = [caps[(s, view)][team]["apps"] for s in SECTIONS]
            if len(set(a)) != 1:
                raise AssertionError(f"apps disagree across sections: {a}")
            r = [caps[(s, view)][team]["rating"] for s in SECTIONS]
            if len(set(r)) != 1:
                raise AssertionError(f"rating disagree across sections: {r}")
            if (
                caps[("summary", view)][team]["shotsPerGame"]
                != caps[("offensive", view)][team]["shotsPerGame"]
            ):
                raise AssertionError("shotsPerGame disagrees summary/offensive")
        rows.append(row)
    return rows


def fingerprint(obs: Sequence[dict[str, Any]]) -> str:
    """Canonical content hash: row order, key order and float repr are all fixed."""
    payload = [
        {"team_id": row["team_id"], **{name: row[name] for name in MEASURES}}
        for row in sorted(obs, key=lambda r: r["team_id"])
    ]
    blob = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _additive_col(name: str) -> bool:
    return name.endswith("apps") or any(name.endswith(f"_{metric}") for metric in ADDITIVE)


def _clamp(name: str, value: float) -> float:
    if name.endswith("rating"):
        return min(10.0, max(0.0, value))
    if name.endswith("possession") or name.endswith("passSuccess"):
        return min(1.0, max(0.0, value))
    return min(1000.0, max(0.0, value))


def synthesize(
    count: int, base: Sequence[dict[str, Any]], seed: int = 7
) -> list[list[dict[str, Any]]]:
    """A deterministic, cumulative sequence of successive observations.

    State accumulates across steps, so `overall_apps` grows by exactly 1 per step and
    the four additive measures always satisfy `home + away = overall`.
    """
    rng = random.Random(seed)
    state = [dict(row) for row in base]
    for row in state:
        for view in VIEWS:
            row[f"{view}_apps"] = int(row[f"{view}_apps"])

    out: list[list[dict[str, Any]]] = []
    for step in range(count):
        side = "home" if step % 2 == 0 else "away"
        for row in state:
            row[f"{side}_apps"] = int(row[f"{side}_apps"]) + 1
            row["overall_apps"] = row["home_apps"] + row["away_apps"]

            for metric in ("goal", "yellowCard", "redCard"):
                inc = float(rng.randint(0, 2 if metric == "goal" else 1))
                row[f"summary_{side}_{metric}"] = float(row[f"summary_{side}_{metric}"]) + inc
                row[f"summary_overall_{metric}"] = (
                    row[f"summary_home_{metric}"] + row[f"summary_away_{metric}"]
                )

            for name in MEASURES:
                if name.endswith("ranking"):
                    row[name] = ((int(row[name]) - 1 + 1) % 20) + 1
                elif not _additive_col(name):
                    moved = float(row[name]) * (1.0 + rng.uniform(-0.01, 0.01))
                    row[name] = _clamp(name, moved)
        out.append([dict(row) for row in state])
    return out


def snapshot_ddl(unique_edge: bool, parent_nullable: bool) -> str:
    parent = "VARCHAR" if parent_nullable else "VARCHAR NOT NULL"
    edge = "\n    , UNIQUE (parent_snapshot_id, content_fingerprint)" if unique_edge else ""
    return f"""
CREATE TABLE competition_snapshot (
    snapshot_id          VARCHAR PRIMARY KEY,
    parent_snapshot_id   {parent},
    stage_id             VARCHAR NOT NULL,
    content_fingerprint  VARCHAR NOT NULL,
    observed_at          TIMESTAMP NOT NULL,
    accepted_at          TIMESTAMP NOT NULL{edge}
);"""


def fact_ddl() -> str:
    body = ",\n".join(f"    {c.name:38} {c.sql_type}" for c in COLUMNS)
    return f"""
CREATE TABLE fact_team_snapshot (
    snapshot_id VARCHAR NOT NULL
                REFERENCES competition_snapshot(snapshot_id),
    team_id     INTEGER NOT NULL,
{body},
    PRIMARY KEY (snapshot_id, team_id)
);"""


CHECKPOINT_DDL = """
CREATE TABLE checkpoint (
    stage_id          VARCHAR PRIMARY KEY,
    last_committed_fp VARCHAR,
    last_accepted_id  VARCHAR
);"""


def create_schema(
    con: duckdb.DuckDBPyConnection, *, unique_edge: bool = False, parent_nullable: bool = False
) -> None:
    con.execute(snapshot_ddl(unique_edge, parent_nullable))
    con.execute(fact_ddl())
    con.execute(CHECKPOINT_DDL)


def sql_literal(value: Any) -> str:
    """A safe SQL literal for internal, typed values.

    Used for the fact insert because DuckDB 1.5.6 binds parameters at ~4 ms each on
    Windows, which makes a 62-column x 20-row parameterised insert take ~2.5 s. Values
    here are ints, floats, None and our own short strings, and strings are escaped.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite float in fact row: {value!r}")
        return repr(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, datetime):
        return "TIMESTAMP '" + value.isoformat(sep=" ") + "'"
    raise TypeError(f"unsupported literal type: {type(value)!r}")


def insert_fact(con: duckdb.DuckDBPyConnection, sid: str, obs: Sequence[dict[str, Any]]) -> None:
    head = f"INSERT INTO fact_team_snapshot (snapshot_id, team_id, {', '.join(MEASURES)}) VALUES "
    tuples = []
    for row in obs:
        values = [sql_literal(sid), sql_literal(row["team_id"])]
        values.extend(sql_literal(row[name]) for name in MEASURES)
        tuples.append("(" + ",".join(values) + ")")
    con.execute(head + ",".join(tuples))


def publish_once(
    con: duckdb.DuckDBPyConnection,
    approach: Any,
    obs: Sequence[dict[str, Any]],
    as_of: datetime,
    stage: str = STAGE,
) -> dict[str, Any]:
    """One full pipeline step: compare, insert header + fact + checkpoint atomically."""
    fp = fingerprint(obs)
    row = con.execute(
        "SELECT last_committed_fp, last_accepted_id FROM checkpoint WHERE stage_id = ?", [stage]
    ).fetchone()
    if row and row[0] == fp:
        return {"accepted": False, "snapshot_id": row[1], "reason": "no_change", "fp": fp}

    parent = row[1] if row else GENESIS
    sid = approach.new_id(parent, stage, fp)

    con.execute("BEGIN")
    try:
        present, inserted = approach.insert_snapshot(con, sid, parent, stage, fp, as_of, as_of)
        if inserted:
            insert_fact(con, present, obs)
        con.execute(
            "INSERT INTO checkpoint (stage_id, last_committed_fp, last_accepted_id) "
            "VALUES (?, ?, ?) ON CONFLICT (stage_id) DO UPDATE SET "
            "last_committed_fp = excluded.last_committed_fp, "
            "last_accepted_id = excluded.last_accepted_id",
            [stage, fp, present],
        )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return {"accepted": True, "snapshot_id": present, "reason": "accepted", "fp": fp}


def connect(path: pathlib.Path) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def fresh(path: pathlib.Path) -> duckdb.DuckDBPyConnection:
    if path.exists():
        path.unlink()
    for suffix in (".wal",):
        side = path.with_suffix(path.suffix + suffix)
        if side.exists():
            side.unlink()
    return connect(path)


def scalar(con: duckdb.DuckDBPyConnection, sql: str, params: Sequence[Any] = ()) -> Any:
    row = con.execute(sql, list(params)).fetchone()
    return None if row is None else row[0]


def stamp(i: int, start: datetime | None = None) -> datetime:
    return (start or datetime(2026, 1, 1)) + timedelta(seconds=i)
