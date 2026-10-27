"""Transactional publication and restart-reconciliation tests."""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dataderby.config import StageSpec
from dataderby.db import connect, migrate
from dataderby.dims import ensure_team_mapping
from dataderby.landing import LandingResult
from dataderby.parse import Candidate, TeamRow, build_candidate
from dataderby.parse_standings import StandingsCandidate, parse_views
from dataderby.publish import (
    Outcome,
    insert_facts,
    latest_parent_snapshot,
    publish,
    reconcile,
    sql_literal,
)
from dataderby.validate import PublishBlocked
from tests.test_assertions import (
    _SPEC,
    _insert_run,
    _page,
    _replace_measure,
    _replace_standings_measure,
)
from tests.test_whoscored_parse import _captures

_NOW = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)


@pytest.fixture
def con(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = connect(tmp_path / "test.duckdb")
    migrate(connection)
    try:
        yield connection
    finally:
        connection.close()


def _run_at(
    run_id: str,
    observed_at: datetime,
    *,
    feeds: list | None = None,
) -> LandingResult:
    feed_captures = [
        replace(capture, captured_at=observed_at)
        for capture in (feeds if feeds is not None else _captures())
    ]
    return LandingResult(
        run_id=run_id,
        observed_at=observed_at,
        page=_page(captured_at=observed_at),
        feeds=tuple(feed_captures),
        raw_files=(),
    )


def _prepare(
    con: duckdb.DuckDBPyConnection,
    run: LandingResult,
    spec: StageSpec = _SPEC,
) -> tuple[Candidate, StandingsCandidate]:
    _insert_run(con, run, spec)
    candidate = build_candidate(list(run.feeds), spec)
    standings = parse_views(run.page, spec)
    return candidate, standings


def _count(con: duckdb.DuckDBPyConnection, table: str) -> int:
    return int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])


def test_publish_accepts_and_writes_one_atomic_snapshot(
    con: duckdb.DuckDBPyConnection,
) -> None:
    run = _run_at("run_1", _NOW)
    candidate, standings = _prepare(con, run)

    outcome = publish(con, candidate, standings, _SPEC, run)

    assert outcome is Outcome.ACCEPTED
    assert _count(con, "competition_snapshot") == 1
    assert _count(con, "fact_team_snapshot") == 20
    assert _count(con, "fact_standings_snapshot") == 20
    header = con.execute(
        "SELECT parent_snapshot_id, run_id, capture_span_seconds FROM competition_snapshot"
    ).fetchone()
    assert header is not None
    assert header[0] == "genesis"
    assert header[1] == "run_1"
    assert header[2] == 0.0
    checkpoint = con.execute(
        "SELECT last_outcome, last_accepted_snapshot_id, attempt_count FROM pipeline_checkpoint"
    ).fetchone()
    assert checkpoint is not None
    assert checkpoint[0] == "accepted"
    assert checkpoint[1] is not None
    assert checkpoint[2] == 1
    assert con.execute("SELECT outcome FROM ingestion_run").fetchone()[0] == "accepted"


def test_a_deducted_total_publishes_and_the_view_shows_the_gap(
    con: duckdb.DuckDBPyConnection,
) -> None:
    run = _run_at("run_deduction", _NOW)
    candidate, standings = _prepare(con, run)
    points = int(standings.rows[0].measures["points_overall"])  # type: ignore[arg-type]
    deducted = _replace_standings_measure(standings, 0, "points_overall", points - 4)
    warnings: list[object] = []

    outcome = publish(con, candidate, deducted, _SPEC, run, on_warning=warnings.append)

    assert outcome is Outcome.ACCEPTED
    [warning] = warnings
    assert warning.assertion_id == "A22"  # type: ignore[attr-defined]
    rows = con.execute(
        """
        SELECT whoscored_team_id, points_reported, points_expected, points_adjustment
        FROM v_points_adjustments
        """
    ).fetchall()
    assert rows == [(deducted.rows[0].whoscored_team_id, points - 4, points, -4)]
    stored = con.execute(
        "SELECT points_overall FROM fact_standings_snapshot WHERE whoscored_team_id = ?",
        [deducted.rows[0].whoscored_team_id],
    ).fetchone()
    assert stored == (points - 4,)


def test_publish_same_content_is_idempotent(
    con: duckdb.DuckDBPyConnection,
) -> None:
    first = _run_at("run_1", _NOW)
    candidate, standings = _prepare(con, first)
    assert publish(con, candidate, standings, _SPEC, first) is Outcome.ACCEPTED

    second = _run_at("run_2", _NOW + timedelta(hours=1))
    _insert_run(con, second)
    second_candidate = build_candidate(list(second.feeds), _SPEC)
    second_standings = parse_views(second.page, _SPEC)

    assert publish(con, second_candidate, second_standings, _SPEC, second) is Outcome.NO_CHANGE
    assert _count(con, "competition_snapshot") == 1
    assert _count(con, "fact_team_snapshot") == 20
    assert (
        con.execute("SELECT outcome FROM ingestion_run WHERE run_id = 'run_2'").fetchone()[0]
        == "no_change"
    )
    checkpoint = con.execute(
        "SELECT last_outcome, attempt_count FROM pipeline_checkpoint"
    ).fetchone()
    assert checkpoint == ("no_change", 2)


def test_a_then_b_then_a_creates_a_new_history_edge(
    con: duckdb.DuckDBPyConnection,
) -> None:
    first = _run_at("run_1", _NOW)
    candidate_a, standings = _prepare(con, first)
    assert publish(con, candidate_a, standings, _SPEC, first) is Outcome.ACCEPTED

    second = _run_at("run_2", _NOW + timedelta(hours=1))
    _insert_run(con, second)
    candidate_b = _replace_measure(candidate_a, 0, "summary_overall_possession", 0.61)
    assert publish(con, candidate_b, standings, _SPEC, second) is Outcome.ACCEPTED

    third = _run_at("run_3", _NOW + timedelta(hours=2))
    _insert_run(con, third)
    assert publish(con, candidate_a, standings, _SPEC, third) is Outcome.ACCEPTED

    assert _count(con, "competition_snapshot") == 3
    parents = [
        row[0]
        for row in con.execute(
            "SELECT parent_snapshot_id FROM competition_snapshot ORDER BY observed_at"
        ).fetchall()
    ]
    assert parents[0] == "genesis"
    assert len(set(parents)) == 3


def test_backfill_uses_the_latest_observed_snapshot_as_parent(
    con: duckdb.DuckDBPyConnection,
) -> None:
    latest = _run_at("run_latest", _NOW + timedelta(hours=2))
    candidate, standings = _prepare(con, latest)
    assert publish(con, candidate, standings, _SPEC, latest) is Outcome.ACCEPTED
    latest_id = con.execute("SELECT snapshot_id FROM competition_snapshot").fetchone()[0]

    backfill = _run_at("run_backfill", _NOW)
    _insert_run(con, backfill)
    backfill_candidate = _replace_measure(candidate, 0, "summary_overall_possession", 0.62)
    assert latest_parent_snapshot(con, _SPEC) == latest_id
    assert publish(con, backfill_candidate, standings, _SPEC, backfill) is Outcome.ACCEPTED

    rows = con.execute(
        "SELECT parent_snapshot_id FROM competition_snapshot WHERE run_id = 'run_backfill'"
    ).fetchall()
    assert rows == [(latest_id,)]
    newest = con.execute(
        "SELECT snapshot_id FROM competition_snapshot ORDER BY observed_at DESC LIMIT 1"
    ).fetchone()[0]
    assert newest == latest_id


def test_blocking_assertion_rolls_back_and_marks_run(
    con: duckdb.DuckDBPyConnection,
) -> None:
    run = _run_at("run_1", _NOW)
    candidate, standings = _prepare(con, run)
    poisoned = _replace_measure(candidate, 0, "apps_home", 99)

    with pytest.raises(PublishBlocked):
        publish(con, poisoned, standings, _SPEC, run)

    assert _count(con, "competition_snapshot") == 0
    assert _count(con, "fact_team_snapshot") == 0
    assert _count(con, "fact_standings_snapshot") == 0
    assert con.execute("SELECT outcome FROM ingestion_run").fetchone()[0] == "blocked"


def test_insert_failure_rolls_back_the_whole_snapshot(
    con: duckdb.DuckDBPyConnection,
) -> None:
    first = _run_at("run_1", _NOW)
    candidate, standings = _prepare(con, first)
    assert publish(con, candidate, standings, _SPEC, first) is Outcome.ACCEPTED

    conflicting = _run_at("run_2", _NOW)
    _insert_run(con, conflicting)
    changed = _replace_measure(candidate, 0, "summary_overall_possession", 0.63)

    with pytest.raises(duckdb.Error):
        publish(con, changed, standings, _SPEC, conflicting)

    assert _count(con, "competition_snapshot") == 1
    assert _count(con, "fact_team_snapshot") == 20
    assert (
        con.execute("SELECT outcome FROM ingestion_run WHERE run_id = 'run_2'").fetchone()[0]
        == "crashed"
    )


def test_no_table_stage_publishes_no_standings(
    con: duckdb.DuckDBPyConnection,
) -> None:
    spec = _SPEC.model_copy(update={"has_league_table": False})
    run = _run_at("run_1", _NOW)
    run = LandingResult(
        run_id=run.run_id,
        observed_at=run.observed_at,
        page=_page(captured_at=run.observed_at, standings={}),
        feeds=run.feeds,
        raw_files=(),
    )
    _insert_run(con, run, spec)
    candidate = build_candidate(list(run.feeds), spec)
    standings = parse_views(run.page, spec)

    assert publish(con, candidate, standings, spec, run) is Outcome.ACCEPTED
    assert _count(con, "fact_standings_snapshot") == 0


def test_sql_literal_round_trips_adversarial_strings(
    con: duckdb.DuckDBPyConnection,
) -> None:
    values = (
        "O'Reilly",
        "x'; DROP TABLE competition_snapshot; --",
        "line one\nline two",
        "back\\slash",
    )

    for value in values:
        assert con.execute(f"SELECT {sql_literal(value)}").fetchone()[0] == value


@settings(deadline=None)
@given(
    st.text(
        alphabet=st.characters(blacklist_categories=("Cc", "Cs")),
        max_size=100,
    )
)
def test_sql_literal_round_trips_arbitrary_text(value: str) -> None:
    con = duckdb.connect(":memory:")
    try:
        assert con.execute(f"SELECT {sql_literal(value)}").fetchone()[0] == value
    finally:
        con.close()


def test_sql_literal_rejects_non_finite_and_unknown_values() -> None:
    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError):
            sql_literal(value)
    with pytest.raises(TypeError):
        sql_literal(object())


def test_insert_facts_uses_names_verbatim(
    con: duckdb.DuckDBPyConnection,
) -> None:
    run = _run_at("run_1", _NOW)
    candidate, standings = _prepare(con, run)
    row = candidate.rows[0]
    renamed = Candidate(
        candidate.whoscored_tournament_id,
        candidate.is_opta,
        (
            TeamRow(row.whoscored_team_id, "O'Reilly", row.measures),
            *candidate.rows[1:],
        ),
    )
    con.execute("BEGIN")
    con.execute(
        """
        INSERT INTO competition_snapshot (
            snapshot_id, parent_snapshot_id, whoscored_tournament_id,
            whoscored_season_id, whoscored_stage_id, season_key,
            content_fingerprint, canonical_version, observed_at, accepted_at,
            capture_span_seconds, is_opta, whoscored_page_url, run_id
        ) VALUES ('snap_1', 'genesis', ?, ?, ?, '2026/27', 'fp', 1, ?, ?, 0,
                  true, ?, 'run_1')
        """,
        [
            _SPEC.whoscored_tournament_id,
            _SPEC.whoscored_season_id,
            _SPEC.whoscored_stage_id,
            _NOW,
            _NOW,
            run.page.url,
        ],
    )
    insert_facts(
        con,
        renamed,
        standings,
        "snap_1",
        {
            row.whoscored_team_id: ensure_team_mapping(
                con, row.whoscored_team_id, row.whoscored_team_name
            )
            for row in renamed.rows
        },
    )
    con.execute("COMMIT")

    name = con.execute(
        "SELECT whoscored_team_name FROM fact_team_snapshot WHERE whoscored_team_id = ?",
        [row.whoscored_team_id],
    ).fetchone()[0]
    assert name == "O'Reilly"


def test_publish_without_a_table_writes_team_facts_only(
    con: duckdb.DuckDBPyConnection,
) -> None:
    spec = _SPEC.model_copy(update={"has_league_table": False})
    run = _run_at("run_no_table", _NOW)
    _insert_run(con, run, spec)
    candidate = build_candidate(list(run.feeds), spec)
    standings = StandingsCandidate(rows=())

    assert publish(con, candidate, standings, spec, run) is Outcome.ACCEPTED
    assert _count(con, "fact_team_snapshot") == 20
    assert _count(con, "fact_standings_snapshot") == 0


def test_reconcile_accepts_committed_and_abandons_uncommitted_runs(
    con: duckdb.DuckDBPyConnection,
) -> None:
    accepted = _run_at("run_accepted", _NOW)
    candidate, standings = _prepare(con, accepted)
    assert publish(con, candidate, standings, _SPEC, accepted) is Outcome.ACCEPTED
    con.execute(
        "UPDATE ingestion_run SET outcome = 'running', finished_at = NULL "
        "WHERE run_id = 'run_accepted'"
    )

    abandoned = _run_at("run_abandoned", _NOW + timedelta(hours=1))
    _insert_run(con, abandoned)

    assert reconcile(con) == 2
    outcomes = dict(con.execute("SELECT run_id, outcome FROM ingestion_run").fetchall())
    assert outcomes["run_accepted"] == "accepted"
    assert outcomes["run_abandoned"] == "abandoned"
    assert con.execute("SELECT abandoned_runs FROM pipeline_checkpoint").fetchone()[0] == 1
