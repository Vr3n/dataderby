"""P7 consumer-view tests; DuckDB only, no browser and no network."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from dataderby.config import StageSpec, load_settings
from dataderby.db import connect, migrate

_STAGES = load_settings(Path("config/stages.toml")).stages
_SPEC: StageSpec = _STAGES["epl-2026-2027"]
_NOW = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)

# Synthetic ids: a no-table stage and two stages that only appear in one table.
_NO_TABLE_STAGE_ID = 25545
_SNAPSHOT_ONLY_STAGE_ID = 25999
_RUN_ONLY_STAGE_ID = 25998


@pytest.fixture
def con(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = connect(tmp_path / "test.duckdb")
    migrate(connection)
    try:
        yield connection
    finally:
        connection.close()


def _insert_snapshot(
    con: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    *,
    observed_at: datetime,
    accepted_at: datetime | None = None,
    whoscored_stage_id: int | None = None,
) -> None:
    con.execute(
        """
        INSERT INTO competition_snapshot (
            snapshot_id, parent_snapshot_id, whoscored_tournament_id,
            whoscored_season_id, whoscored_stage_id, season_key,
            content_fingerprint, canonical_version, observed_at, accepted_at,
            capture_span_seconds, is_opta, whoscored_page_url, run_id
        ) VALUES (?, 'genesis', ?, ?, ?, ?, ?, 1, ?, ?, 0, true, ?, 'run_seed')
        """,
        [
            snapshot_id,
            _SPEC.whoscored_tournament_id,
            _SPEC.whoscored_season_id,
            whoscored_stage_id or _SPEC.whoscored_stage_id,
            _SPEC.season_key,
            f"fp_{snapshot_id}",
            observed_at,
            accepted_at or observed_at,
            _SPEC.whoscored_page_url,
        ],
    )


def _insert_team(
    con: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    whoscored_team_id: int,
    *,
    apps: int = 0,
    goal: float = 0.0,
    yellow_card: float = 0.0,
    red_card: float = 0.0,
    whoscored_team_name: str | None = None,
) -> None:
    con.execute(
        """
        INSERT INTO fact_team_snapshot (
            snapshot_id, whoscored_team_id, whoscored_team_name,
            apps_overall, summary_overall_goal,
            summary_overall_yellow_card, summary_overall_red_card
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            snapshot_id,
            whoscored_team_id,
            whoscored_team_name or f"Team {whoscored_team_id}",
            apps,
            goal,
            yellow_card,
            red_card,
        ],
    )


def _insert_standings(
    con: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    whoscored_team_id: int,
    *,
    rank: int,
    points: int,
    form: str,
    whoscored_team_name: str | None = None,
) -> None:
    con.execute(
        """
        INSERT INTO fact_standings_snapshot (
            snapshot_id, whoscored_team_id, whoscored_team_name,
            rank_overall, points_overall, form_overall,
            rank_home, points_home, form_home,
            rank_away, points_away, form_away
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            snapshot_id,
            whoscored_team_id,
            whoscored_team_name or f"Team {whoscored_team_id}",
            rank,
            points,
            form,
            rank,
            points,
            form,
            rank,
            points,
            form,
        ],
    )


def _insert_checkpoint(
    con: duckdb.DuckDBPyConnection,
    spec: StageSpec,
    *,
    last_success_at: datetime | None,
    attempt_count: int = 1,
) -> None:
    con.execute(
        """
        INSERT INTO pipeline_checkpoint (
            whoscored_tournament_id, whoscored_season_id, whoscored_stage_id,
            last_probe_at, last_success_at, last_outcome, attempt_count
        ) VALUES (?, ?, ?, ?, ?, 'accepted', ?)
        """,
        [
            spec.whoscored_tournament_id,
            spec.whoscored_season_id,
            spec.whoscored_stage_id,
            last_success_at,
            last_success_at,
            attempt_count,
        ],
    )


def _insert_run(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    *,
    whoscored_stage_id: int,
    observed_at: datetime = _NOW,
) -> None:
    con.execute(
        """
        INSERT INTO ingestion_run (
            run_id, mode, started_at, outcome, whoscored_tournament_id,
            whoscored_season_id, whoscored_stage_id
        ) VALUES (?, 'full', ?, 'accepted', ?, ?, ?)
        """,
        [
            run_id,
            observed_at,
            _SPEC.whoscored_tournament_id,
            _SPEC.whoscored_season_id,
            whoscored_stage_id,
        ],
    )


def test_migrate_creates_all_six_consumer_views(
    con: duckdb.DuckDBPyConnection,
) -> None:
    views = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_type = 'VIEW' ORDER BY table_name"
    ).fetchall()

    assert [row[0] for row in views] == [
        "v_latest_standings",
        "v_latest_team_state",
        "v_latest_team_with_standings",
        "v_pipeline_freshness",
        "v_snapshot_delta",
        "v_standings_history",
    ]


def test_latest_team_state_does_not_leak_a_team_from_an_older_snapshot(
    con: duckdb.DuckDBPyConnection,
) -> None:
    _insert_snapshot(con, "snap_old", observed_at=_NOW)
    _insert_team(con, "snap_old", 100, apps=10)
    _insert_team(con, "snap_old", 200, apps=10)

    _insert_snapshot(con, "snap_new", observed_at=_NOW + timedelta(days=1))
    _insert_team(con, "snap_new", 100, apps=11)

    rows = con.execute(
        "SELECT snapshot_id, whoscored_team_id, apps_overall FROM v_latest_team_state"
    ).fetchall()

    assert rows == [("snap_new", 100, 11)]


def test_snapshot_delta_leaves_a_gap_when_a_team_misses_a_snapshot(
    con: duckdb.DuckDBPyConnection,
) -> None:
    _insert_snapshot(con, "snap_a", observed_at=_NOW)
    _insert_team(con, "snap_a", 100, apps=10)
    _insert_team(con, "snap_a", 200, apps=10)

    _insert_snapshot(con, "snap_b", observed_at=_NOW + timedelta(days=1))
    _insert_team(con, "snap_b", 100, apps=11)

    _insert_snapshot(con, "snap_c", observed_at=_NOW + timedelta(days=2))
    _insert_team(con, "snap_c", 100, apps=12)
    _insert_team(con, "snap_c", 200, apps=11)

    rows = con.execute(
        """
        SELECT snapshot_id, previous_snapshot_id, whoscored_team_id, d_apps
        FROM v_snapshot_delta
        ORDER BY observed_at, whoscored_team_id
        """
    ).fetchall()

    assert rows == [
        ("snap_b", "snap_a", 100, 1),
        ("snap_c", "snap_b", 100, 1),
    ]


def test_snapshot_delta_flags_a_decreasing_apps_count_as_a_correction(
    con: duckdb.DuckDBPyConnection,
) -> None:
    _insert_snapshot(con, "snap_a", observed_at=_NOW)
    _insert_team(con, "snap_a", 100, apps=10, goal=5.0, yellow_card=2.0, red_card=0.0)

    _insert_snapshot(con, "snap_b", observed_at=_NOW + timedelta(days=1))
    _insert_team(con, "snap_b", 100, apps=9, goal=5.0, yellow_card=3.0, red_card=1.0)

    row = con.execute(
        """
        SELECT d_apps, d_goal, d_yellow_card, d_red_card, is_correction
        FROM v_snapshot_delta
        """
    ).fetchone()

    assert row == (-1, 0.0, 1.0, 1.0, True)


def test_backfill_does_not_change_the_latest_team_state(
    con: duckdb.DuckDBPyConnection,
) -> None:
    _insert_snapshot(con, "snap_new", observed_at=_NOW + timedelta(days=1))
    _insert_team(con, "snap_new", 100, apps=11)
    before = con.execute("SELECT snapshot_id, apps_overall FROM v_latest_team_state").fetchall()

    _insert_snapshot(
        con,
        "snap_backfill",
        observed_at=_NOW,
        accepted_at=_NOW + timedelta(days=2),
    )
    _insert_team(con, "snap_backfill", 100, apps=10)

    after = con.execute("SELECT snapshot_id, apps_overall FROM v_latest_team_state").fetchall()

    assert before == after == [("snap_new", 11)]


def test_latest_team_with_standings_joins_on_ids_and_keeps_knockout_nulls(
    con: duckdb.DuckDBPyConnection,
) -> None:
    _insert_snapshot(con, "snap_league", observed_at=_NOW)
    _insert_team(con, "snap_league", 100, apps=10, whoscored_team_name="Team Stats 100")
    _insert_team(con, "snap_league", 200, apps=10)
    _insert_standings(
        con,
        "snap_league",
        100,
        rank=1,
        points=30,
        form="wwd",
        whoscored_team_name="Standings 100",
    )
    _insert_standings(con, "snap_league", 200, rank=2, points=27, form="wlw")

    league = con.execute(
        """
        SELECT whoscored_team_id, whoscored_team_name, rank_overall, points_overall
        FROM v_latest_team_with_standings
        WHERE whoscored_stage_id = ?
        ORDER BY whoscored_team_id
        """,
        [_SPEC.whoscored_stage_id],
    ).fetchall()

    assert league == [
        (100, "Team Stats 100", 1, 30),
        (200, "Team 200", 2, 27),
    ]

    latest_standings = con.execute(
        """
        SELECT whoscored_team_id, rank_overall
        FROM v_latest_standings
        WHERE whoscored_stage_id = ?
        ORDER BY whoscored_team_id
        """,
        [_SPEC.whoscored_stage_id],
    ).fetchall()

    assert latest_standings == [(100, 1), (200, 2)]

    _insert_snapshot(
        con,
        "snap_no_table",
        observed_at=_NOW,
        whoscored_stage_id=_NO_TABLE_STAGE_ID,
    )
    _insert_team(con, "snap_no_table", 100, apps=3)
    _insert_team(con, "snap_no_table", 200, apps=3)

    knockout = con.execute(
        """
        SELECT whoscored_team_id, rank_overall, points_overall, form_overall
        FROM v_latest_team_with_standings
        WHERE whoscored_stage_id = ?
        ORDER BY whoscored_team_id
        """,
        [_NO_TABLE_STAGE_ID],
    ).fetchall()

    assert knockout == [(100, None, None, None), (200, None, None, None)]

    assert con.execute(
        "SELECT count(*) FROM v_latest_standings WHERE whoscored_stage_id = ?",
        [_NO_TABLE_STAGE_ID],
    ).fetchone() == (0,)


def test_standings_history_returns_one_series_row_per_snapshot(
    con: duckdb.DuckDBPyConnection,
) -> None:
    _insert_snapshot(con, "snap_a", observed_at=_NOW)
    _insert_standings(con, "snap_a", 100, rank=2, points=10, form="wwd")
    _insert_standings(con, "snap_a", 200, rank=1, points=12, form="www")

    _insert_snapshot(con, "snap_b", observed_at=_NOW + timedelta(days=1))
    _insert_standings(con, "snap_b", 100, rank=1, points=13, form="wwdw")

    rows = con.execute(
        """
        SELECT observed_at, rank_overall, points_overall, form_overall
        FROM v_standings_history
        WHERE whoscored_team_id = 100
        ORDER BY observed_at
        """
    ).fetchall()

    assert rows == [
        (_NOW.replace(tzinfo=None), 2, 10, "wwd"),
        ((_NOW + timedelta(days=1)).replace(tzinfo=None), 1, 13, "wwdw"),
    ]


def test_pipeline_freshness_returns_one_row_per_configured_stage(
    con: duckdb.DuckDBPyConnection,
) -> None:
    last_success_at = datetime.now(UTC) - timedelta(minutes=5)
    for spec in _STAGES.values():
        _insert_checkpoint(con, spec, last_success_at=last_success_at, attempt_count=4)

    rows = con.execute(
        """
        SELECT whoscored_tournament_id, whoscored_season_id, whoscored_stage_id,
               last_outcome, attempt_count, accepted_snapshots, age_seconds
        FROM v_pipeline_freshness
        ORDER BY whoscored_tournament_id, whoscored_stage_id
        """
    ).fetchall()

    addresses = {(row[0], row[1], row[2]) for row in rows}
    assert addresses == {
        (spec.whoscored_tournament_id, spec.whoscored_season_id, spec.whoscored_stage_id)
        for spec in _STAGES.values()
    }
    assert len(rows) == len(_STAGES)
    for row in rows:
        assert row[3] == "accepted"
        assert row[4] == 4
        assert row[5] == 0
        # Guards against comparing the naive UTC clock with a local-time
        # current_timestamp: the Asia/Calcutta session would add 19800 seconds.
        assert row[6] is not None
        assert 250 <= row[6] <= 3600


def test_pipeline_freshness_shows_stages_seen_only_in_a_run_or_snapshot(
    con: duckdb.DuckDBPyConnection,
) -> None:
    _insert_run(con, "run_only", whoscored_stage_id=_RUN_ONLY_STAGE_ID)
    _insert_snapshot(
        con,
        "snap_only",
        observed_at=_NOW,
        whoscored_stage_id=_SNAPSHOT_ONLY_STAGE_ID,
    )

    rows = con.execute(
        """
        SELECT whoscored_stage_id, last_probe_at, last_outcome,
               attempt_count, accepted_snapshots
        FROM v_pipeline_freshness
        ORDER BY whoscored_stage_id
        """
    ).fetchall()

    assert rows == [
        (_RUN_ONLY_STAGE_ID, None, None, 0, 0),
        (_SNAPSHOT_ONLY_STAGE_ID, None, None, 0, 1),
    ]


def test_pipeline_freshness_age_is_null_before_the_first_success(
    con: duckdb.DuckDBPyConnection,
) -> None:
    _insert_checkpoint(con, _SPEC, last_success_at=None)

    row = con.execute("SELECT last_success_at, age_seconds FROM v_pipeline_freshness").fetchone()

    assert row == (None, None)
