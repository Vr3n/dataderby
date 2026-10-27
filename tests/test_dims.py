"""P1 team-identity tests: dims DDL, backfill, archived/active split."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from dataderby.cli import Runtime, main
from dataderby.config import StageSpec, load_settings
from dataderby.db import connect, migrate
from dataderby.dims import WHOSCORED_SOURCE, backfill_team_dims, mint_team_id, unmapped_teams
from tests.test_assertions import _page
from tests.test_whoscored_parse import _SPEC, _captures

_STAGE_B = """[[stage]]
key = "epl-test-archived"
whoscored_tournament_id = 2
whoscored_season_id = 11142
whoscored_stage_id = 29999
season_key = "2025-2026"
competition = "Premier League"
stage = "league"
expected_stages = ["league"]
expected_teams = 20
whoscored_page_url = "https://www.whoscored.com/regions/252/tournaments/2/seasons/11142/stages/29999/show/england-premier-league-2025-2026"
has_league_table = true
active = false
"""


def _write_config(tmp_path: Path, *, archived: bool) -> Path:
    """Write a two-stage config; the second stage is archived when asked."""
    base = f"""[settings]
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
"""
    body = base + (_STAGE_B if archived else _STAGE_B.replace("active = false", "active = true"))
    path = tmp_path / "stages.toml"
    path.write_text(body, encoding="utf-8")
    return path


def _runtime(seen: list[str]) -> Runtime:
    """A sweep that records keys and rewrites urls to match each spec."""
    import re
    from dataclasses import replace

    from dataderby.page import StageCapture
    from tests.test_assertions import _PAGE_URL

    def sweep(
        url: str, spec: StageSpec, *, only: object = None, budget: object = None
    ) -> StageCapture:
        seen.append(spec.key)
        stage_id = spec.whoscored_stage_id
        season_id = spec.whoscored_season_id
        feeds = tuple(
            replace(capture, url=re.sub(r"stageId=\d+", f"stageId={stage_id}", capture.url))
            for capture in _captures()
        )
        page_url = re.sub(r"/stages/\d+/", f"/stages/{stage_id}/", _PAGE_URL)
        page_url = re.sub(r"/seasons/\d+/", f"/seasons/{season_id}/", page_url)
        page = _page(url=page_url)
        return StageCapture(page=page, feeds=feeds)

    return Runtime(sweep=sweep)


@pytest.fixture
def con(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "dims.duckdb")
    migrate(connection)
    try:
        yield connection
    finally:
        connection.close()


def _seed_header(con: duckdb.DuckDBPyConnection, snapshot_id: str, observed: datetime) -> None:
    con.execute(
        """
        INSERT INTO competition_snapshot (
            snapshot_id, parent_snapshot_id, whoscored_tournament_id,
            whoscored_season_id, whoscored_stage_id, season_key,
            content_fingerprint, canonical_version, observed_at, accepted_at,
            capture_span_seconds, is_opta, whoscored_page_url, run_id
        ) VALUES (?, 'genesis', 2, 11141, 25544, '2026-2027',
                  ?, 1, ?, ?, 5.0, true, 'https://www.whoscored.com/x', 'run_seed')
        """,
        [snapshot_id, f"fp_{snapshot_id}", observed, observed],
    )


def _seed_fact(con: duckdb.DuckDBPyConnection, snapshot_id: str, team_id: int, name: str) -> None:
    con.execute(
        "INSERT INTO fact_team_snapshot (snapshot_id, whoscored_team_id, whoscored_team_name)"
        " VALUES (?, ?, ?)",
        [snapshot_id, team_id, name],
    )


def test_migration_006_creates_dim_tables(con: duckdb.DuckDBPyConnection) -> None:
    tables = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }
    assert "dim_team" in tables
    assert "team_source_key" in tables


def test_backfill_maps_every_fact_team_once(con: duckdb.DuckDBPyConnection) -> None:
    now = datetime.now(UTC)
    _seed_header(con, "snap_a", now)
    _seed_header(con, "snap_b", now + timedelta(days=1))
    _seed_fact(con, "snap_a", 13, "Arsenal")
    _seed_fact(con, "snap_a", 167, "Manchester City")
    _seed_fact(con, "snap_b", 13, "Arsenal")

    added = backfill_team_dims(con)

    assert (added.teams, added.mappings) == (2, 2)
    assert unmapped_teams(con) == []
    rows = con.execute(
        "SELECT dataderby_team_id, canonical_name FROM dim_team ORDER BY canonical_name"
    ).fetchall()
    assert [name for _, name in rows] == ["Arsenal", "Manchester City"]
    assert rows[0][0] != rows[1][0]
    keys = con.execute(
        "SELECT source, source_team_id FROM team_source_key ORDER BY source_team_id"
    ).fetchall()
    assert keys == [(WHOSCORED_SOURCE, "13"), (WHOSCORED_SOURCE, "167")]


def test_backfill_is_idempotent(con: duckdb.DuckDBPyConnection) -> None:
    now = datetime.now(UTC)
    _seed_header(con, "snap_a", now)
    _seed_fact(con, "snap_a", 13, "Arsenal")

    first = backfill_team_dims(con)
    second = backfill_team_dims(con)

    assert (first.teams, first.mappings) == (1, 1)
    assert (second.teams, second.mappings) == (0, 0)
    assert con.execute("SELECT count(*) FROM dim_team").fetchone() == (1,)


def test_double_mapping_is_rejected(con: duckdb.DuckDBPyConnection) -> None:
    now = datetime.now(UTC)
    _seed_header(con, "snap_a", now)
    _seed_fact(con, "snap_a", 13, "Arsenal")
    backfill_team_dims(con)
    canonical = con.execute("SELECT dataderby_team_id FROM dim_team").fetchone()[0]

    with pytest.raises(duckdb.Error, match="uplicate key"):
        con.execute(
            "INSERT INTO team_source_key (dataderby_team_id, source, source_team_id)"
            " VALUES (?, ?, ?)",
            [canonical, WHOSCORED_SOURCE, "13"],
        )
    with pytest.raises(duckdb.Error, match="uplicate key"):
        con.execute(
            "INSERT INTO team_source_key (dataderby_team_id, source, source_team_id)"
            " VALUES (?, ?, ?)",
            [canonical, WHOSCORED_SOURCE, "14"],
        )


def test_unmapped_teams_lists_new_facts(con: duckdb.DuckDBPyConnection) -> None:
    now = datetime.now(UTC)
    _seed_header(con, "snap_a", now)
    _seed_fact(con, "snap_a", 13, "Arsenal")
    _seed_fact(con, "snap_a", 167, "Manchester City")
    backfill_team_dims(con)
    _seed_fact(con, "snap_a", 211, "Brighton")

    assert unmapped_teams(con) == [(211, "Brighton")]


def test_mint_team_id_shape() -> None:
    first, second = mint_team_id(), mint_team_id()

    assert first.startswith("dtm_") and len(first) == len("dtm_") + 12
    assert first != second


def test_active_defaults_to_true(tmp_path: Path) -> None:
    settings = load_settings(_write_config(tmp_path, archived=False))

    assert settings.stages["epl-test"].active is True


def test_active_false_parses(tmp_path: Path) -> None:
    settings = load_settings(_write_config(tmp_path, archived=True))

    assert settings.stages["epl-test-archived"].active is False


def test_run_without_stage_skips_archived(tmp_path: Path) -> None:
    config = _write_config(tmp_path, archived=True)
    seen: list[str] = []

    assert main(["run", "--config", str(config)], runtime=_runtime(seen)) == 0
    assert seen == ["epl-test"]


def test_run_with_explicit_stage_still_runs_archived(tmp_path: Path) -> None:
    config = _write_config(tmp_path, archived=True)
    seen: list[str] = []

    assert (
        main(
            ["run", "--config", str(config), "--stage", "epl-test-archived"],
            runtime=_runtime(seen),
        )
        == 0
    )
    assert seen == ["epl-test-archived"]


def _age_checkpoint(db_path: Path, stage_id: int, when: datetime) -> None:
    con = connect(db_path)
    try:
        con.execute(
            "UPDATE pipeline_checkpoint SET last_success_at = ? WHERE whoscored_stage_id = ?",
            [when, stage_id],
        )
    finally:
        con.close()


def test_freshness_check_skips_archived(tmp_path: Path) -> None:
    config = _write_config(tmp_path, archived=True)
    assert main(["run", "--config", str(config)], runtime=_runtime([])) == 0
    db_path = tmp_path / "pipeline.duckdb"
    _age_checkpoint(db_path, 29999, datetime(2020, 1, 1, tzinfo=UTC))

    assert main(["freshness", "--config", str(config), "--check", "--max-age-hours", "1"]) == 0


def test_freshness_check_flags_stale_when_active(tmp_path: Path) -> None:
    config = _write_config(tmp_path, archived=False)
    assert main(["run", "--config", str(config)], runtime=_runtime([])) == 0
    db_path = tmp_path / "pipeline.duckdb"
    _age_checkpoint(db_path, 29999, datetime(2020, 1, 1, tzinfo=UTC))

    assert main(["freshness", "--config", str(config), "--check", "--max-age-hours", "1"]) == 6


def test_dims_backfill_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = _write_config(tmp_path, archived=True)
    assert main(["run", "--config", str(config)], runtime=_runtime([])) == 0

    assert main(["dims", "backfill", "--config", str(config)]) == 0
    out = capsys.readouterr().out
    assert "coverage: 100%" in out

    con = connect(tmp_path / "pipeline.duckdb", read_only=True)
    try:
        count = con.execute("SELECT count(*) FROM dim_team").fetchone()
    finally:
        con.close()
    assert count == (20,)

    assert main(["dims", "backfill", "--config", str(config)]) == 0
    assert "0 teams, 0 mappings added" in capsys.readouterr().out
