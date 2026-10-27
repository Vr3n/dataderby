"""Post-publish drift checks; DuckDB only, no browser and no network."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from dataderby.cli import main
from dataderby.config import load_settings
from dataderby.db import connect, migrate
from dataderby.drift import THRESHOLDS, DriftFinding, check_drift, record_drift
from tests.test_pipeline_cli import _config
from tests.test_views import _SPEC, _insert_snapshot, _insert_standings, _insert_team

_NOW = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)


@pytest.fixture
def con(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = connect(tmp_path / "test.duckdb")
    migrate(connection)
    try:
        yield connection
    finally:
        connection.close()


def _seed_pair(
    con: duckdb.DuckDBPyConnection,
    old_teams: tuple[int, ...],
    new_teams: tuple[int, ...],
) -> tuple[str, str]:
    """Two accepted snapshots one hour apart with team and standings rows."""
    _insert_snapshot(con, "snap_old", observed_at=_NOW)
    _insert_snapshot(con, "snap_new", observed_at=_NOW + timedelta(hours=1))
    for team_id in old_teams:
        _insert_team(con, "snap_old", team_id, apps=10)
        _insert_standings(con, "snap_old", team_id, rank=1, points=20, form="wwd", won=6, drawn=2)
    for team_id in new_teams:
        _insert_team(con, "snap_new", team_id, apps=10)
        _insert_standings(con, "snap_new", team_id, rank=1, points=20, form="wwd", won=6, drawn=2)
    return "snap_new", "snap_old"


def test_thresholds_live_in_one_table() -> None:
    assert set(THRESHOLDS) == {"null_rate_delta_max", "observed_lag_hours_max"}
    assert THRESHOLDS["null_rate_delta_max"] == 0.10
    assert THRESHOLDS["observed_lag_hours_max"] == 6.0


def test_identical_snapshots_have_no_drift(con: duckdb.DuckDBPyConnection) -> None:
    current, _ = _seed_pair(con, (100, 200), (100, 200))

    assert check_drift(con, _SPEC, current) == ()


def test_a_first_snapshot_has_no_baseline(con: duckdb.DuckDBPyConnection) -> None:
    _insert_snapshot(con, "snap_only", observed_at=_NOW)
    _insert_team(con, "snap_only", 100, apps=10)
    _insert_standings(con, "snap_only", 100, rank=1, points=20, form="wwd", won=6, drawn=2)

    assert check_drift(con, _SPEC, "snap_only") == ()


def test_a_dropped_team_fires_row_count_and_team_set(
    con: duckdb.DuckDBPyConnection,
) -> None:
    current, _ = _seed_pair(con, (100, 200), (100,))

    findings = check_drift(con, _SPEC, current)
    checks = {finding.check for finding in findings}

    assert {"row_count", "team_set"} <= checks
    team_set = next(finding for finding in findings if finding.check == "team_set")
    assert "removed=[200]" in team_set.detail
    assert "added=[]" in team_set.detail


def test_a_swapped_team_fires_team_set_without_row_count(
    con: duckdb.DuckDBPyConnection,
) -> None:
    current, _ = _seed_pair(con, (100, 200), (100, 300))

    findings = check_drift(con, _SPEC, current)
    checks = {finding.check for finding in findings}

    assert "team_set" in checks
    assert "row_count" not in checks


def test_a_column_going_empty_fires_null_rate(
    con: duckdb.DuckDBPyConnection,
) -> None:
    current, _ = _seed_pair(con, (100, 200), (100, 200))
    con.execute("UPDATE fact_team_snapshot SET apps_overall = NULL WHERE snapshot_id = 'snap_new'")

    findings = check_drift(con, _SPEC, current)

    [finding] = [f for f in findings if f.check == "null_rate"]
    assert "apps_overall" in finding.detail
    assert "0.00->1.00" in finding.detail


def test_a_small_null_wobble_does_not_fire(con: duckdb.DuckDBPyConnection) -> None:
    old = tuple(range(100, 120))
    current, _ = _seed_pair(con, old, old)
    con.execute(
        "UPDATE fact_team_snapshot SET apps_overall = NULL "
        "WHERE snapshot_id = 'snap_new' AND whoscored_team_id = 100"
    )

    findings = check_drift(con, _SPEC, current)

    assert "null_rate" not in {finding.check for finding in findings}


def test_a_snapshot_accepted_late_fires_observed_lag(
    con: duckdb.DuckDBPyConnection,
) -> None:
    current, _ = _seed_pair(con, (100, 200), (100, 200))

    assert "observed_lag" not in {finding.check for finding in check_drift(con, _SPEC, current)}

    con.execute(
        "UPDATE competition_snapshot SET accepted_at = ? WHERE snapshot_id = 'snap_new'",
        [_NOW + timedelta(hours=12)],
    )

    findings = check_drift(con, _SPEC, current)

    [finding] = [f for f in findings if f.check == "observed_lag"]
    assert "11.0 h" in finding.detail


def test_an_unknown_snapshot_reports_no_baseline(
    con: duckdb.DuckDBPyConnection,
) -> None:
    _seed_pair(con, (100, 200), (100, 200))

    [finding] = check_drift(con, _SPEC, "snap_missing")

    assert finding.check == "baseline"


def test_a_non_newest_snapshot_is_not_compared_backwards(
    con: duckdb.DuckDBPyConnection,
) -> None:
    _, old = _seed_pair(con, (100, 200), (100, 200))

    [finding] = check_drift(con, _SPEC, old)

    assert finding.check == "baseline"


def test_record_drift_writes_a_jsonl_event(tmp_path: Path) -> None:
    record_drift(
        (DriftFinding(check="row_count", detail="2 vs 1"),),
        snapshot_id="snap_new",
        stage_key="epl-test",
        log_dir=tmp_path / "logs",
    )

    [path] = list((tmp_path / "logs").glob("*.jsonl"))
    event = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

    assert event["event"] == "drift.check"
    assert event["drifted"] is True
    assert event["findings"] == [{"check": "row_count", "detail": "2 vs 1"}]


def _seed_cli_db(db_path: Path, *, drop_team: bool) -> None:
    con = connect(db_path)
    try:
        migrate(con)
        old = (100, 200)
        new = (100,) if drop_team else (100, 200)
        _insert_snapshot(con, "snap_old", observed_at=_NOW)
        _insert_snapshot(con, "snap_new", observed_at=_NOW + timedelta(hours=1))
        for team_id in old:
            _insert_team(con, "snap_old", team_id, apps=10)
            _insert_standings(
                con, "snap_old", team_id, rank=1, points=20, form="wwd", won=6, drawn=2
            )
        for team_id in new:
            _insert_team(con, "snap_new", team_id, apps=10)
            _insert_standings(
                con, "snap_new", team_id, rank=1, points=20, form="wwd", won=6, drawn=2
            )
    finally:
        con.close()


def test_drift_command_reports_no_drift_and_logs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path)
    settings = load_settings(config)
    _seed_cli_db(settings.db_path, drop_team=False)

    assert main(["drift", "--config", str(config)]) == 0

    out = capsys.readouterr().out
    assert "no drift" in out
    events = [
        json.loads(line)
        for path in settings.log_dir.glob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert [e for e in events if e["event"] == "drift.check" and not e["drifted"]]


def test_drift_command_reports_findings_without_blocking(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path)
    settings = load_settings(config)
    _seed_cli_db(settings.db_path, drop_team=True)

    assert main(["drift", "--config", str(config)]) == 0

    out = capsys.readouterr().out
    assert "DRIFT row_count" in out
    assert "DRIFT team_set" in out
