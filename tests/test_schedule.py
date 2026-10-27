"""Scheduled-run helpers; DuckDB only for the CLI paths, no browser or network."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from dataderby.cli import main
from dataderby.config import load_settings
from dataderby.db import connect, migrate
from dataderby.schedule import (
    STALE_AFTER_HOURS,
    evaluate_freshness,
    ping_heartbeat,
    run_scheduled,
)
from tests.test_pipeline_cli import _config


def _row(
    age_seconds: float | None,
    *,
    stage_id: int = 25544,
    outcome: str | None = "accepted",
) -> tuple[object, ...]:
    return (2, 11141, stage_id, None, age_seconds, outcome, 1, 1)


def test_provisional_ceiling_is_36_hours() -> None:
    assert STALE_AFTER_HOURS == 36.0


def test_a_never_successful_stage_is_stale() -> None:
    [stage] = evaluate_freshness([_row(None)], max_age_seconds=36 * 3600)

    assert stage.stale is True


def test_an_age_past_the_ceiling_is_stale() -> None:
    [stage] = evaluate_freshness([_row(36 * 3600 + 1)], max_age_seconds=36 * 3600)

    assert stage.stale is True


def test_an_age_exactly_at_the_ceiling_is_still_fresh() -> None:
    [stage] = evaluate_freshness([_row(36 * 3600)], max_age_seconds=36 * 3600)

    assert stage.stale is False


def test_a_recent_success_is_fresh() -> None:
    [stage] = evaluate_freshness([_row(60.0)], max_age_seconds=36 * 3600)

    assert stage.stale is False


def test_mixed_stages_keep_their_order_and_flags() -> None:
    rows = [
        _row(60.0, stage_id=25544),
        _row(None, stage_id=25545, outcome=None),
        _row(200_000.0, stage_id=25546),
    ]

    evaluated = evaluate_freshness(rows, max_age_seconds=36 * 3600)

    assert [entry.whoscored_stage_id for entry in evaluated] == [25544, 25545, 25546]
    assert [entry.stale for entry in evaluated] == [False, True, True]


def test_a_2xx_ping_is_a_success() -> None:
    class _Response:
        status = 200

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    assert (
        ping_heartbeat("https://example.invalid/ping", opener=lambda *a, **k: _Response()) is True
    )


def test_a_failed_ping_never_raises() -> None:
    def _boom(*args: object, **kwargs: object) -> object:
        raise ConnectionError("monitor unreachable")

    assert ping_heartbeat("https://example.invalid/ping", opener=_boom) is False


def test_a_non_2xx_ping_is_a_failure() -> None:
    class _Response:
        status = 500

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    assert (
        ping_heartbeat("https://example.invalid/ping", opener=lambda *a, **k: _Response()) is False
    )


def test_a_successful_run_pings_and_never_alerts() -> None:
    calls: list[str] = []

    code = run_scheduled(
        lambda: 0,
        on_failure=lambda c: calls.append(f"alert:{c}"),
        on_success=lambda: calls.append("ping"),
    )

    assert code == 0
    assert calls == ["ping"]


def test_a_failed_run_alerts_and_never_pings() -> None:
    calls: list[str] = []

    code = run_scheduled(
        lambda: 4,
        on_failure=lambda c: calls.append(f"alert:{c}"),
        on_success=lambda: calls.append("ping"),
    )

    assert code == 4
    assert calls == ["alert:4"]


def test_a_held_lock_alerts_like_any_other_failure() -> None:
    seen: list[int] = []

    code = run_scheduled(lambda: 5, on_failure=seen.append)

    assert code == 5
    assert seen == [5]


def _checkpoint(
    db_path: Path,
    *,
    stage_id: int,
    last_success_at: datetime | None,
    outcome: str | None = "accepted",
) -> None:
    con = connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO pipeline_checkpoint (
                whoscored_tournament_id, whoscored_season_id, whoscored_stage_id,
                last_probe_at, last_success_at, last_outcome, attempt_count
            ) VALUES (2, 11141, ?, ?, ?, ?, 1)
            """,
            [stage_id, last_success_at, last_success_at, outcome],
        )
    finally:
        con.close()


def _db(tmp_path: Path, spec_stage_id: int = 25544) -> Path:
    from tests.test_whoscored_parse import _SPEC

    assert _SPEC.whoscored_stage_id == spec_stage_id
    config = _config(tmp_path)
    settings = load_settings(config)
    con = connect(settings.db_path)
    try:
        migrate(con)
    finally:
        con.close()
    return config


def test_freshness_check_passes_on_a_recent_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _db(tmp_path)
    _checkpoint(
        load_settings(config).db_path,
        stage_id=25544,
        last_success_at=datetime.now(UTC) - timedelta(hours=1),
    )

    assert main(["freshness", "--check", "--config", str(config)]) == 0

    out = capsys.readouterr().out
    assert "fresh" in out
    assert "STALE" not in out
    assert "0 of 1 stages stale" in out


def test_freshness_check_fails_on_a_stale_stage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _db(tmp_path)
    _checkpoint(
        load_settings(config).db_path,
        stage_id=25544,
        last_success_at=datetime(2020, 1, 1, tzinfo=UTC),
    )

    assert main(["freshness", "--check", "--config", str(config)]) == 6

    out = capsys.readouterr().out
    assert "STALE" in out
    assert "1 of 1 stages stale" in out


def test_freshness_check_fails_when_a_stage_never_succeeded(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _db(tmp_path)
    _checkpoint(
        load_settings(config).db_path,
        stage_id=25544,
        last_success_at=None,
        outcome=None,
    )

    assert main(["freshness", "--check", "--config", str(config)]) == 6

    assert "STALE" in capsys.readouterr().out


def test_freshness_check_json_marks_each_stage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _db(tmp_path)
    settings = load_settings(config)
    _checkpoint(settings.db_path, stage_id=25544, last_success_at=datetime.now(UTC))

    assert main(["freshness", "--check", "--json", "--config", str(config)]) == 0

    [entry] = json.loads(capsys.readouterr().out)
    assert entry["stale"] is False
    assert entry["max_age_seconds"] == 36 * 3600
    assert entry["accepted_snapshots"] == 0


def test_freshness_check_rejects_a_non_positive_ceiling(tmp_path: Path) -> None:
    config = _db(tmp_path)

    assert main(["freshness", "--check", "--max-age-hours", "0", "--config", str(config)]) == 4


def test_freshness_without_check_is_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _db(tmp_path)
    _checkpoint(
        load_settings(config).db_path,
        stage_id=25544,
        last_success_at=datetime(2020, 1, 1, tzinfo=UTC),
    )

    assert main(["freshness", "--config", str(config)]) == 0

    out = capsys.readouterr().out
    assert "STATUS" not in out
    assert "STALE" not in out
