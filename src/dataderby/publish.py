"""Transactional publication of one validated candidate."""

from __future__ import annotations

import contextlib
import math
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

import duckdb

from dataderby.canonical import fingerprint
from dataderby.config import StageSpec
from dataderby.contract import MEASURE_COLUMNS, STANDINGS_MEASURES
from dataderby.landing import LandingResult
from dataderby.parse import Candidate
from dataderby.parse_standings import StandingsCandidate
from dataderby.validate import (
    Action,
    AssertionFailure,
    PublishBlocked,
    blocking_failures,
    run_assertions,
)


class Outcome(StrEnum):
    """The publish result for one attempt."""

    ACCEPTED = "accepted"
    NO_CHANGE = "no_change"


def sql_literal(value: Any) -> str:
    """Return a DuckDB SQL literal for a fact value.

    Args:
        value: ``int``, ``float``, ``str``, ``bool``, or ``None``.

    Returns:
        A literal that is safe to concatenate into a multi-row ``INSERT``.

    Raises:
        TypeError: If the value is not a supported scalar.
        ValueError: If a float is NaN or infinite.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite SQL value: {value!r}")
        return repr(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise TypeError(f"unsupported SQL literal: {type(value).__name__}")


def _literal_row(values: tuple[Any, ...]) -> str:
    return "(" + ", ".join(sql_literal(value) for value in values) + ")"


def insert_facts(
    con: duckdb.DuckDBPyConnection,
    candidate: Candidate,
    standings: StandingsCandidate,
    snapshot_id: str,
    team_ids: dict[int, str],
) -> tuple[int, int]:
    """Insert team and standings facts using literal ``VALUES`` rows.

    The two inserts run inside the caller's transaction. DuckDB 1.5.6 is much
    faster with one multi-row literal statement than with parameter binding.

    Args:
        con: Connection inside the publish transaction.
        candidate: Validated feed candidate.
        standings: Validated standings companion; empty for no-table stages.
        snapshot_id: Header id that owns the facts.
        team_ids: Canonical id per WhoScored team id; every candidate team
            must resolve (assertions A23/A24 run before this).

    Returns:
        ``(team_rows, standings_rows)`` actually inserted.
    """
    team_columns = (
        "snapshot_id",
        "whoscored_team_id",
        "whoscored_team_name",
        "dataderby_team_id",
        *MEASURE_COLUMNS,
    )
    team_values = [
        (
            snapshot_id,
            row.whoscored_team_id,
            row.whoscored_team_name,
            team_ids[row.whoscored_team_id],
            *(row.measures[column] for column in MEASURE_COLUMNS),
        )
        for row in candidate.rows
    ]
    if team_values:
        sql = f"INSERT INTO fact_team_snapshot ({', '.join(team_columns)}) VALUES " + ", ".join(
            _literal_row(row) for row in team_values
        )
        con.execute(sql)

    standings_columns = (
        "snapshot_id",
        "whoscored_team_id",
        "whoscored_team_name",
        "dataderby_team_id",
        *STANDINGS_MEASURES,
    )
    standings_values = [
        (
            snapshot_id,
            row.whoscored_team_id,
            row.whoscored_team_name,
            team_ids[row.whoscored_team_id],
            *(row.measures[column] for column in STANDINGS_MEASURES),
        )
        for row in standings.rows
    ]
    if standings_values:
        sql = (
            f"INSERT INTO fact_standings_snapshot ({', '.join(standings_columns)}) VALUES "
            + ", ".join(_literal_row(row) for row in standings_values)
        )
        con.execute(sql)

    return len(team_values), len(standings_values)


def latest_parent_snapshot(con: duckdb.DuckDBPyConnection, spec: StageSpec) -> str:
    """Return the latest accepted snapshot id by ``observed_at`` or genesis."""
    row = con.execute(
        """
        SELECT snapshot_id
        FROM competition_snapshot
        WHERE whoscored_tournament_id = ?
          AND whoscored_season_id = ?
          AND whoscored_stage_id = ?
        ORDER BY observed_at DESC, accepted_at DESC, snapshot_id DESC
        LIMIT 1
        """,
        [
            spec.whoscored_tournament_id,
            spec.whoscored_season_id,
            spec.whoscored_stage_id,
        ],
    ).fetchone()
    return str(row[0]) if row is not None else "genesis"


def _capture_span(run: LandingResult) -> float:
    times = [run.page.captured_at, *(capture.captured_at for capture in run.feeds)]
    return (max(times) - min(times)).total_seconds()


def _update_run(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    outcome: str,
    *,
    snapshot_id: str | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    con.execute(
        """
        UPDATE ingestion_run
        SET outcome = ?,
            finished_at = ?,
            accepted_snapshot_id = COALESCE(?, accepted_snapshot_id),
            error_code = ?,
            error_detail = ?
        WHERE run_id = ?
        """,
        [
            outcome,
            datetime.now(UTC),
            snapshot_id,
            error_code,
            error_detail,
            run_id,
        ],
    )


def _upsert_checkpoint(
    con: duckdb.DuckDBPyConnection,
    spec: StageSpec,
    *,
    outcome: str,
    snapshot_id: str | None = None,
    content_fingerprint: str | None = None,
    success: bool = False,
    abandoned_delta: int = 0,
) -> None:
    now = datetime.now(UTC)
    con.execute(
        """
        INSERT INTO pipeline_checkpoint (
            whoscored_tournament_id, whoscored_season_id, whoscored_stage_id,
            last_accepted_snapshot_id, last_committed_fingerprint,
            last_probe_at, last_success_at, last_outcome, attempt_count,
            abandoned_runs
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        ON CONFLICT (whoscored_tournament_id, whoscored_season_id, whoscored_stage_id)
        DO UPDATE SET
            last_accepted_snapshot_id = COALESCE(
                excluded.last_accepted_snapshot_id,
                pipeline_checkpoint.last_accepted_snapshot_id
            ),
            last_committed_fingerprint = COALESCE(
                excluded.last_committed_fingerprint,
                pipeline_checkpoint.last_committed_fingerprint
            ),
            last_probe_at = excluded.last_probe_at,
            last_success_at = CASE
                WHEN excluded.last_success_at IS NOT NULL
                THEN excluded.last_success_at
                ELSE pipeline_checkpoint.last_success_at
            END,
            last_outcome = excluded.last_outcome,
            attempt_count = pipeline_checkpoint.attempt_count + 1,
            abandoned_runs = pipeline_checkpoint.abandoned_runs + ?
        """,
        [
            spec.whoscored_tournament_id,
            spec.whoscored_season_id,
            spec.whoscored_stage_id,
            snapshot_id,
            content_fingerprint,
            now,
            now if success else None,
            outcome,
            abandoned_delta,
            abandoned_delta,
        ],
    )


def _existing_snapshot(
    con: duckdb.DuckDBPyConnection,
    parent: str,
    content_fingerprint: str,
) -> str | None:
    row = con.execute(
        """
        SELECT snapshot_id
        FROM competition_snapshot
        WHERE parent_snapshot_id = ? AND content_fingerprint = ?
        """,
        [parent, content_fingerprint],
    ).fetchone()
    return str(row[0]) if row is not None else None


def reconcile(con: duckdb.DuckDBPyConnection) -> int:
    """Resolve runs left ``running`` after an earlier crash.

    A run with a committed snapshot becomes ``accepted``; every other running
    run becomes ``abandoned``. Returns the number of runs changed.
    """
    rows = con.execute(
        """
        SELECT run_id, whoscored_tournament_id, whoscored_season_id, whoscored_stage_id
        FROM ingestion_run
        WHERE outcome = 'running'
        """
    ).fetchall()
    changed = 0
    for run_id, tournament_id, season_id, stage_id in rows:
        snapshot = con.execute(
            "SELECT snapshot_id FROM competition_snapshot WHERE run_id = ? LIMIT 1",
            [run_id],
        ).fetchone()
        if snapshot is not None:
            _update_run(con, str(run_id), "accepted", snapshot_id=str(snapshot[0]))
        else:
            _update_run(con, str(run_id), "abandoned")
            con.execute(
                """
                INSERT INTO pipeline_checkpoint (
                    whoscored_tournament_id, whoscored_season_id, whoscored_stage_id,
                    last_probe_at, last_outcome, abandoned_runs
                ) VALUES (?, ?, ?, ?, 'abandoned', 1)
                ON CONFLICT (whoscored_tournament_id, whoscored_season_id, whoscored_stage_id)
                DO UPDATE SET abandoned_runs = pipeline_checkpoint.abandoned_runs + 1
                """,
                [tournament_id, season_id, stage_id, datetime.now(UTC)],
            )
        changed += 1
    return changed


def _mark_failed_run(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    outcome: str,
    *,
    detail: str | None = None,
) -> None:
    with contextlib.suppress(duckdb.Error):
        _update_run(con, run_id, outcome, error_code=outcome, error_detail=detail)


def _ensure_canonical_ids(
    con: duckdb.DuckDBPyConnection,
    candidate: Candidate,
    spec: StageSpec,
) -> tuple[str, dict[int, str]]:
    """Ensure canonical stage and team ids for a candidate, then return them.

    A first publish cannot block on unknown teams: no facts exist yet to
    backfill mappings from, so creation here is mechanical, not curation.
    Source ids are stable, so insert-if-missing is deterministic. Curation
    still owns names (drift review), renames (update), and second sources
    (manual mapping rows). Assertions A23 and A24 run after this and verify
    every staged row resolves.

    Args:
        con: Connection inside the publish transaction.
        candidate: Validated feed candidate.
        spec: Configured stage.

    Returns:
        The stage canonical id and one canonical team id per candidate team.
    """
    from dataderby.dims import ensure_stage_mapping, ensure_team_mapping

    stage_id = ensure_stage_mapping(
        con,
        tournament_id=spec.whoscored_tournament_id,
        season_id=spec.whoscored_season_id,
        stage_id=spec.whoscored_stage_id,
        tournament_name=spec.competition,
        season_key=spec.season_key,
        stage_code=spec.stage,
        canonical_name=f"{spec.competition} {spec.season_key}",
    )
    team_ids = {
        row.whoscored_team_id: ensure_team_mapping(
            con, row.whoscored_team_id, row.whoscored_team_name
        )
        for row in candidate.rows
    }
    return stage_id, team_ids


def publish(
    con: duckdb.DuckDBPyConnection,
    candidate: Candidate,
    standings: StandingsCandidate,
    spec: StageSpec,
    run: LandingResult,
    *,
    allow_apps_decrease: bool = False,
    on_warning: Callable[[AssertionFailure], None] | None = None,
) -> Outcome:
    """Validate and publish one candidate in a single transaction.

    Args:
        con: Open DuckDB connection with the schema applied.
        candidate: Parsed feed candidate.
        standings: Parsed standings companion.
        spec: Configured stage.
        run: Landing result that owns the raw sweep.
        allow_apps_decrease: Explicit revocation override for A10.
        on_warning: Called once per WARN failure. Warnings never block; the
            callback is where an operator log or console line is written.

    Returns:
        ``ACCEPTED`` when a header and facts were committed, or ``NO_CHANGE``
        when the same content was already accepted.

    Raises:
        PublishBlocked: If a blocking or retry assertion fails.
        duckdb.Error: If the insert or commit fails; the transaction is rolled
            back before the exception escapes.
    """
    content_fingerprint = fingerprint(candidate, standings)
    cached = con.execute(
        """
        SELECT last_committed_fingerprint
        FROM pipeline_checkpoint
        WHERE whoscored_tournament_id = ?
          AND whoscored_season_id = ?
          AND whoscored_stage_id = ?
        """,
        [
            spec.whoscored_tournament_id,
            spec.whoscored_season_id,
            spec.whoscored_stage_id,
        ],
    ).fetchone()
    if cached is not None and cached[0] == content_fingerprint:
        con.execute("BEGIN")
        try:
            _upsert_checkpoint(con, spec, outcome=Outcome.NO_CHANGE.value)
            _update_run(con, run.run_id, Outcome.NO_CHANGE.value)
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        return Outcome.NO_CHANGE

    con.execute("BEGIN")
    try:
        stage_canonical_id, team_ids = _ensure_canonical_ids(con, candidate, spec)
        failures = run_assertions(
            con,
            candidate,
            standings,
            spec,
            run,
            allow_apps_decrease=allow_apps_decrease,
        )
        if on_warning is not None:
            for failure in failures:
                if failure.action is Action.WARN:
                    on_warning(failure)
        blocking = blocking_failures(failures)
        if blocking:
            raise PublishBlocked(blocking)

        parent = latest_parent_snapshot(con, spec)
        snapshot_id = f"snap_{uuid4().hex}"
        observed_at = run.observed_at
        accepted_at = datetime.now(UTC)
        inserted = con.execute(
            """
            INSERT INTO competition_snapshot (
                snapshot_id, parent_snapshot_id, whoscored_tournament_id,
                whoscored_season_id, whoscored_stage_id, season_key,
                content_fingerprint, canonical_version, observed_at, accepted_at,
                capture_span_seconds, is_opta, whoscored_page_url, run_id,
                dataderby_stage_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (parent_snapshot_id, content_fingerprint) DO NOTHING
            RETURNING snapshot_id
            """,
            [
                snapshot_id,
                parent,
                spec.whoscored_tournament_id,
                spec.whoscored_season_id,
                spec.whoscored_stage_id,
                spec.season_key,
                content_fingerprint,
                observed_at,
                accepted_at,
                _capture_span(run),
                candidate.is_opta,
                run.page.url,
                run.run_id,
                stage_canonical_id,
            ],
        ).fetchall()

        if not inserted:
            existing = _existing_snapshot(con, parent, content_fingerprint)
            _upsert_checkpoint(
                con,
                spec,
                outcome=Outcome.NO_CHANGE.value,
                snapshot_id=existing,
                content_fingerprint=content_fingerprint,
            )
            _update_run(con, run.run_id, Outcome.NO_CHANGE.value)
            con.execute("COMMIT")
            return Outcome.NO_CHANGE

        insert_facts(con, candidate, standings, snapshot_id, team_ids)
        _upsert_checkpoint(
            con,
            spec,
            outcome=Outcome.ACCEPTED.value,
            snapshot_id=snapshot_id,
            content_fingerprint=content_fingerprint,
            success=True,
        )
        _update_run(con, run.run_id, Outcome.ACCEPTED.value, snapshot_id=snapshot_id)
        con.execute("COMMIT")
        return Outcome.ACCEPTED
    except PublishBlocked as exc:
        con.execute("ROLLBACK")
        _mark_failed_run(
            con,
            run.run_id,
            "blocked",
            detail="; ".join(failure.assertion_id for failure in exc.failures),
        )
        raise
    except BaseException as exc:
        con.execute("ROLLBACK")
        _mark_failed_run(con, run.run_id, "crashed", detail=str(exc))
        raise
