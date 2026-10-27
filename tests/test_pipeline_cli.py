"""End-to-end command line tests; no browser and no network."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from dataderby.cli import Runtime, main
from dataderby.config import Settings
from dataderby.db import connect, migrate
from dataderby.fetch import Capture, SchemaDrift
from dataderby.lock import exclusive_lock
from dataderby.page import PageCapture, StageCapture
from tests.test_assertions import _page
from tests.test_whoscored_parse import _NOW, _SPEC, _captures

_TIMEOUT = timedelta(hours=1)


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "stages.toml"
    path.write_text(
        f"""
[settings]
db_path = "{(tmp_path / "pipeline.duckdb").as_posix()}"
raw_dir = "{(tmp_path / "raw").as_posix()}"
log_dir = "{(tmp_path / "logs").as_posix()}"

[[stage]]
key = "epl-test"
whoscored_tournament_id = {_SPEC.whoscored_tournament_id}
whoscored_season_id = {_SPEC.whoscored_season_id}
whoscored_stage_id = {_SPEC.whoscored_stage_id}
season_key = "{_SPEC.season_key}"
competition = "Premier League"
stage = "league"
expected_stages = ["league"]
expected_teams = {_SPEC.expected_teams}
whoscored_page_url = "{_SPEC.whoscored_page_url}"
has_league_table = true
""",
        encoding="utf-8",
    )
    return path


def _settings(tmp_path: Path) -> Settings:
    from dataderby.config import load_settings

    return load_settings(_config(tmp_path))


def _runtime(
    *,
    page: PageCapture | None = None,
    feeds: list[Capture] | None = None,
) -> Runtime:
    """A sweep that returns the page and feeds without a browser."""
    selected = feeds if feeds is not None else _captures()
    stage = StageCapture(page=page or _page(), feeds=tuple(selected))

    def sweep(
        url: str, spec: object, *, only: object = None, budget: object = None
    ) -> StageCapture:
        return stage

    return Runtime(sweep=sweep)


@pytest.fixture
def seeded(tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    """Run one stage once; yield (config path, database path)."""
    config = _config(tmp_path)
    assert main(["run", "--config", str(config)], runtime=_runtime()) == 0
    yield config, tmp_path / "pipeline.duckdb"


def _deducted_page() -> PageCapture:
    """A page whose first team in every split is four points short."""
    page = _page()
    standings = {
        view: tuple(
            replace(row, points=str(int(row.points) - 4)) if index == 0 else row
            for index, row in enumerate(rows)
        )
        for view, rows in page.standings.items()
    }
    return _page(standings=standings)


def _count(db_path: Path, table: str) -> int:
    con = connect(db_path, read_only=True)
    try:
        row = con.execute(f"SELECT count(*) FROM {table}").fetchone()
        return 0 if row is None else int(row[0])
    finally:
        con.close()


def test_stages_list_prints_the_registry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path)

    assert main(["stages", "list", "--config", str(config)]) == 0

    out = capsys.readouterr().out
    assert "epl-test" in out
    assert "Premier League" in out
    assert str(_SPEC.whoscored_stage_id) in out


def test_an_unknown_stage_is_a_config_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path)

    assert main(["run", "--stage", "nope", "--config", str(config)]) == 4

    assert "unknown stage" in capsys.readouterr().err


def test_usage_errors_use_the_config_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path)

    assert main(["run", "--not-a-flag", "--config", str(config)]) == 4

    assert "usage:" in capsys.readouterr().err


def test_a_run_publishes_one_snapshot(seeded: tuple[Path, Path]) -> None:
    _, db_path = seeded

    assert _count(db_path, "competition_snapshot") == 1
    assert _count(db_path, "fact_team_snapshot") == 20
    assert _count(db_path, "fact_standings_snapshot") == 20


def test_a_second_run_with_the_same_content_writes_no_snapshot(
    seeded: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    config, db_path = seeded
    later = _NOW + _TIMEOUT
    runtime = _runtime(
        page=_page(captured_at=later),
        feeds=[replace(capture, captured_at=later) for capture in _captures()],
    )

    assert main(["run", "--config", str(config)], runtime=runtime) == 0

    assert _count(db_path, "competition_snapshot") == 1
    assert "no_change" in capsys.readouterr().out


def test_a_held_lock_refuses_the_run_before_any_write(tmp_path: Path) -> None:
    config = _config(tmp_path)
    settings = _settings(tmp_path)

    with exclusive_lock(settings.db_path.parent / "pipeline.lock"):
        assert main(["run", "--config", str(config)], runtime=_runtime()) == 5

    assert not settings.db_path.exists()


def test_a_dry_run_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = _config(tmp_path)
    settings = _settings(tmp_path)

    assert main(["run", "--dry-run", "--config", str(config)], runtime=_runtime()) == 0

    assert not settings.db_path.exists()
    assert not settings.raw_dir.exists()
    assert "would publish 20 teams" in capsys.readouterr().out


def test_a_dry_run_prints_a_points_deduction(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path)
    settings = _settings(tmp_path)

    assert (
        main(
            ["run", "--dry-run", "--config", str(config)],
            runtime=_runtime(page=_deducted_page()),
        )
        == 0
    )

    out = capsys.readouterr().out
    assert "WARN A22" in out
    assert "adjustment -4" in out
    assert not settings.db_path.exists()


def test_a_run_logs_a_points_deduction_without_blocking(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path)
    settings = _settings(tmp_path)

    assert main(["run", "--config", str(config)], runtime=_runtime(page=_deducted_page())) == 0

    out = capsys.readouterr().out
    assert "accepted" in out
    assert "WARN A22" in out

    records = [
        json.loads(line)
        for path in settings.log_dir.glob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    warnings = [record for record in records if record["event"] == "publish.warning"]
    assert len(warnings) == 1
    assert warnings[0]["assertion_id"] == "A22"
    assert warnings[0]["rows"][0][-1] == -4

    con = connect(settings.db_path, read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM competition_snapshot").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM v_points_adjustments").fetchone()[0] == 1
    finally:
        con.close()


def test_freshness_reports_an_empty_pipeline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path)
    settings = _settings(tmp_path)
    con = connect(settings.db_path)
    try:
        migrate(con)
    finally:
        con.close()

    assert main(["freshness", "--config", str(config)]) == 0

    assert "no accepted snapshots" in capsys.readouterr().out


def test_freshness_json_after_a_run(
    seeded: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    config, _ = seeded

    assert main(["freshness", "--json", "--config", str(config)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 1
    assert payload[0]["accepted_snapshots"] == 1
    assert payload[0]["last_outcome"] == "accepted"
    assert payload[0]["age_seconds"] is not None


def test_verify_passes_on_a_clean_database(
    seeded: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    config, _ = seeded

    assert main(["verify", "--config", str(config)]) == 0

    out = capsys.readouterr().out
    assert "FAIL" not in out
    assert "headers without team facts" in out


def test_verify_detects_a_header_without_facts(
    seeded: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    config, db_path = seeded
    when = _NOW + timedelta(days=1)
    con = connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO competition_snapshot (
                snapshot_id, parent_snapshot_id, whoscored_tournament_id,
                whoscored_season_id, whoscored_stage_id, season_key,
                content_fingerprint, canonical_version, observed_at, accepted_at,
                capture_span_seconds, is_opta, whoscored_page_url, run_id
            ) VALUES ('snap_orphan', 'snap_1', 2, 11141, 25544, '2026-2027',
                      'fp_orphan', 1, ?, ?, 1.0, TRUE, ?, 'run_orphan')
            """,
            [when, when, _SPEC.whoscored_page_url],
        )
    finally:
        con.close()

    assert main(["verify", "--config", str(config)]) == 6

    out = capsys.readouterr().out
    assert "FAIL headers without team facts" in out


def test_replay_check_matches_the_published_fingerprint(
    seeded: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, _ = seeded
    bundle = next((tmp_path / "raw").rglob("page__show.html")).parent

    assert main(["replay", "--raw-dir", str(bundle), "--check", "--config", str(config)]) == 0

    assert "MATCH" in capsys.readouterr().out


def test_replay_check_detects_a_changed_payload(
    seeded: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, _ = seeded
    source = next((tmp_path / "raw").rglob("page__show.html")).parent
    copied = tmp_path / "copied" / source.relative_to(tmp_path / "raw")
    shutil.copytree(source, copied)

    payload_path = copied / "summary__overall.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["teamTableStats"][0]["possession"] = 0.99
    payload_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    assert main(["replay", "--raw-dir", str(copied), "--check", "--config", str(config)]) == 6

    assert "MISMATCH" in capsys.readouterr().out


def test_replay_rebuilds_into_a_scratch_database(
    seeded: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, _ = seeded
    bundle = next((tmp_path / "raw").rglob("page__show.html")).parent

    assert main(["replay", "--raw-dir", str(bundle), "--config", str(config)]) == 0

    assert "REPLAYED" in capsys.readouterr().out


def test_probe_reads_one_feed_without_touching_the_database(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path)
    settings = _settings(tmp_path)

    assert main(["probe", "--config", str(config)], runtime=_runtime()) == 0

    assert "20 teams" in capsys.readouterr().out
    assert not settings.db_path.exists()


def test_a_missing_config_is_a_config_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["stages", "list", "--config", str(tmp_path / "nope.toml")]) == 4

    assert "error:" in capsys.readouterr().err


def test_schema_drift_is_blocked_rather_than_a_fetch_failure(tmp_path: Path) -> None:
    config = _config(tmp_path)

    def drifting(
        url: str, spec: object, *, only: object = None, budget: object = None
    ) -> StageCapture:
        raise SchemaDrift("statColumns changed")

    runtime = Runtime(sweep=drifting)

    assert main(["run", "--config", str(config)], runtime=runtime) == 3
