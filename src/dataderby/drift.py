"""Post-publish drift checks: compare a snapshot with its predecessor.

Assertions run **before** commit and protect the warehouse from a bad write.
These checks run **after** commit and watch for a bad state that passed the
assertions: a short cohort, a swapped team set, a column that silently went
empty, or a snapshot accepted with a stale observation clock.

Rules, from issue #11:

- A drift finding **cannot** roll back a committed transaction. It is recorded,
  reported, and left in place; a human decides.
- Drift never blocks the next run.
- Results are emitted as JSONL through :mod:`dataderby.observe` so they join
  the existing run log.
- All thresholds live in :data:`THRESHOLDS`, not scattered through code.

Distribution drift (a units change that keeps the shape valid) is deliberately
**not** implemented: season measures are cumulative, so means and totals grow
legitimately between snapshots and any fixed threshold would false-positive
every matchday. It needs a baselined rate-of-change model first; the runbook
records that as an open item.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from dataderby.config import StageSpec
from dataderby.observe import log as log_event

#: The drift thresholds. One table, in one place.
THRESHOLDS: dict[str, float] = {
    # A measure whose null fraction rises by more than this between two
    # snapshots is drifting (a column silently going empty).
    "null_rate_delta_max": 0.10,
    # A snapshot accepted more than this many hours after it was observed
    # was sitting somewhere before commit.
    "observed_lag_hours_max": 6.0,
}

_TEAM_KEY_COLUMNS = ("snapshot_id", "whoscored_team_id", "whoscored_team_name")


@dataclass(frozen=True, slots=True)
class DriftFinding:
    """One failed drift check and the evidence for it."""

    check: str
    detail: str


def _stage_snapshots(con: duckdb.DuckDBPyConnection, spec: StageSpec, limit: int = 2) -> list[str]:
    """Return the newest snapshot ids for a stage, newest first.

    Uses the same ordering rule as ``v_latest_*``: ``observed_at`` first,
    then ``accepted_at``, then ``snapshot_id``. History never uses
    ``accepted_at`` as the ordering clock.
    """
    rows = con.execute(
        """
        SELECT snapshot_id
        FROM competition_snapshot
        WHERE whoscored_tournament_id = ?
          AND whoscored_season_id = ?
          AND whoscored_stage_id = ?
        ORDER BY observed_at DESC, accepted_at DESC, snapshot_id DESC
        LIMIT ?
        """,
        [
            spec.whoscored_tournament_id,
            spec.whoscored_season_id,
            spec.whoscored_stage_id,
            limit,
        ],
    ).fetchall()
    return [str(row[0]) for row in rows]


def _team_ids(con: duckdb.DuckDBPyConnection, snapshot_id: str) -> set[int]:
    rows = con.execute(
        "SELECT whoscored_team_id FROM fact_team_snapshot WHERE snapshot_id = ?",
        [snapshot_id],
    ).fetchall()
    return {int(row[0]) for row in rows}


def _measure_columns(con: duckdb.DuckDBPyConnection) -> tuple[str, ...]:
    rows = con.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'fact_team_snapshot'
          AND column_name NOT IN ('snapshot_id', 'whoscored_team_id', 'whoscored_team_name')
        ORDER BY column_name
        """
    ).fetchall()
    return tuple(str(row[0]) for row in rows)


def _null_rates(
    con: duckdb.DuckDBPyConnection, snapshot_id: str, columns: tuple[str, ...]
) -> dict[str, float]:
    """Return the null fraction of each measure column for one snapshot."""
    count_row = con.execute(
        "SELECT count(*) FROM fact_team_snapshot WHERE snapshot_id = ?",
        [snapshot_id],
    ).fetchone()
    assert count_row is not None
    total = int(count_row[0])
    if total == 0 or not columns:
        return {}
    selects = ", ".join(
        f"sum(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END) AS {column}" for column in columns
    )
    (counts,) = con.execute(
        f"SELECT {selects} FROM fact_team_snapshot WHERE snapshot_id = ?",
        [snapshot_id],
    ).fetchall()
    return {column: float(counts[i]) / total for i, column in enumerate(columns)}


def check_drift(
    con: duckdb.DuckDBPyConnection,
    spec: StageSpec,
    snapshot_id: str,
) -> tuple[DriftFinding, ...]:
    """Compare one committed snapshot with its predecessor.

    Args:
        con: Open DuckDB connection with the schema applied.
        spec: Configured stage.
        snapshot_id: The newly committed snapshot to check.

    Returns:
        Findings, newest-check first. An empty tuple means no drift.
        Never raises for missing history: a first snapshot has no baseline,
        so there is nothing to compare.
    """
    snapshots = _stage_snapshots(con, spec)
    if snapshot_id not in snapshots:
        return (
            DriftFinding(
                check="baseline",
                detail=f"snapshot {snapshot_id} is not committed for stage {spec.key}",
            ),
        )
    if len(snapshots) < 2 or snapshots[0] != snapshot_id:
        # First snapshot, or not the newest: no baseline to compare against.
        # Checking a non-latest snapshot against its successor would invert
        # the comparison, so only newest-vs-previous is supported.
        if len(snapshots) < 2:
            return ()
        return (
            DriftFinding(
                check="baseline",
                detail=f"snapshot {snapshot_id} is not the newest for stage {spec.key}",
            ),
        )
    current, previous = snapshots[0], snapshots[1]

    findings: list[DriftFinding] = []

    current_ids = _team_ids(con, current)
    previous_ids = _team_ids(con, previous)
    if len(current_ids) != len(previous_ids):
        findings.append(
            DriftFinding(
                check="row_count",
                detail=(
                    f"{len(previous_ids)} teams in {previous}, {len(current_ids)} in {current}"
                ),
            )
        )
    added = sorted(current_ids - previous_ids)
    removed = sorted(previous_ids - current_ids)
    if added or removed:
        findings.append(
            DriftFinding(
                check="team_set",
                detail=f"added={added} removed={removed}",
            )
        )

    columns = _measure_columns(con)
    current_rates = _null_rates(con, current, columns)
    previous_rates = _null_rates(con, previous, columns)
    delta_max = THRESHOLDS["null_rate_delta_max"]
    drifted = sorted(
        column
        for column in columns
        if current_rates.get(column, 0.0) - previous_rates.get(column, 0.0) > delta_max
    )
    if drifted:
        findings.append(
            DriftFinding(
                check="null_rate",
                detail=(
                    f"null fraction rose by more than {delta_max:g}: "
                    + ", ".join(
                        f"{column} "
                        f"{previous_rates.get(column, 0.0):.2f}"
                        f"->{current_rates.get(column, 0.0):.2f}"
                        for column in drifted
                    )
                ),
            )
        )

    header = con.execute(
        "SELECT observed_at, accepted_at FROM competition_snapshot WHERE snapshot_id = ?",
        [current],
    ).fetchone()
    if header is not None and header[0] is not None and header[1] is not None:
        lag_hours = (header[1] - header[0]).total_seconds() / 3600
        lag_max = THRESHOLDS["observed_lag_hours_max"]
        if lag_hours > lag_max:
            findings.append(
                DriftFinding(
                    check="observed_lag",
                    detail=(f"accepted {lag_hours:.1f} h after observed (limit {lag_max:g} h)"),
                )
            )

    return tuple(findings)


def record_drift(
    findings: tuple[DriftFinding, ...],
    *,
    snapshot_id: str,
    stage_key: str,
    log_dir: Path,
    now: datetime | None = None,
) -> None:
    """Write one JSONL drift event through the existing run log."""
    log_event(
        "drift.check",
        log_dir=log_dir,
        snapshot_id=snapshot_id,
        stage_key=stage_key,
        drifted=bool(findings),
        findings=[{"check": finding.check, "detail": finding.detail} for finding in findings],
        checked_at=(now or datetime.now(UTC)).isoformat(),
    )
