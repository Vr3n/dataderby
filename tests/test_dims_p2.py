"""P2 stage-identity tests: 007, A23/A24, publish wiring, view cutover."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from dataderby.cli import main
from dataderby.config import StageSpec
from dataderby.db import connect, migrate
from dataderby.dims import (
    backfill_stage_dims,
    backfill_team_dims,
    ensure_stage_mapping,
    ensure_team_mapping,
    fill_canonical_ids,
    unmapped_stages,
    unmapped_teams,
)
from dataderby.publish import Outcome, publish
from dataderby.validate import load_assertions, run_assertions
from tests.test_assertions import _SPEC, _clean, _insert_run
from tests.test_dims import _runtime as _archived_runtime
from tests.test_whoscored_parse import _TEAMS


@pytest.fixture
def con(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "dims_p2.duckdb")
    migrate(connection)
    try:
        yield connection
    finally:
        connection.close()


def _now() -> datetime:
    return datetime.now(UTC)


def _seed_header(
    con: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    observed: datetime,
    *,
    tournament_id: int = 2,
    season_id: int = 11141,
    stage_id: int = 25544,
) -> None:
    con.execute(
        """
        INSERT INTO competition_snapshot (
            snapshot_id, parent_snapshot_id, whoscored_tournament_id,
            whoscored_season_id, whoscored_stage_id, season_key,
            content_fingerprint, canonical_version, observed_at, accepted_at,
            capture_span_seconds, is_opta, whoscored_page_url, run_id
        ) VALUES (?, 'genesis', ?, ?, ?, '2026-2027',
                  ?, 1, ?, ?, 5.0, true, 'https://www.whoscored.com/x', 'run_seed')
        """,
        [snapshot_id, tournament_id, season_id, stage_id, f"fp_{snapshot_id}", observed, observed],
    )


def _seed_fact(con: duckdb.DuckDBPyConnection, snapshot_id: str, team_id: int, name: str) -> None:
    con.execute(
        "INSERT INTO fact_team_snapshot (snapshot_id, whoscored_team_id, whoscored_team_name)"
        " VALUES (?, ?, ?)",
        [snapshot_id, team_id, name],
    )


def _mapped(con: duckdb.DuckDBPyConnection, spec: StageSpec = _SPEC) -> None:
    for team_id in _TEAMS:
        ensure_team_mapping(con, team_id, f"Team {team_id}", seen_at=_now())
    ensure_stage_mapping(
        con,
        tournament_id=spec.whoscored_tournament_id,
        season_id=spec.whoscored_season_id,
        stage_id=spec.whoscored_stage_id,
        tournament_name=spec.competition,
        season_key=spec.season_key,
        stage_code=spec.stage,
        canonical_name=f"{spec.competition} {spec.season_key}",
        seen_at=_now(),
    )


def test_007_creates_stage_tables_and_canonical_columns(
    con: duckdb.DuckDBPyConnection,
) -> None:
    tables = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }
    assert "dim_stage" in tables
    assert "stage_source_key" in tables
    for table, column in [
        ("competition_snapshot", "dataderby_stage_id"),
        ("fact_team_snapshot", "dataderby_team_id"),
        ("fact_standings_snapshot", "dataderby_team_id"),
    ]:
        cols = {row[0] for row in con.execute(f"SELECT * FROM {table} LIMIT 0").description}
        assert column in cols


def test_backfill_stage_dims_counts(con: duckdb.DuckDBPyConnection) -> None:
    moment = _now()
    _seed_header(con, "snap_a", moment)
    _seed_header(con, "snap_b", moment, stage_id=29999)

    added = backfill_stage_dims(con)

    assert (added.stages, added.mappings) == (2, 2)
    assert unmapped_stages(con) == []
    assert backfill_stage_dims(con).stages == 0


def test_fill_canonical_ids_writes_old_rows(con: duckdb.DuckDBPyConnection) -> None:
    moment = _now()
    _seed_header(con, "snap_a", moment)
    _seed_fact(con, "snap_a", 13, "Arsenal")
    backfill_team_dims(con)
    backfill_stage_dims(con)

    filled = fill_canonical_ids(con)

    assert (filled.headers, filled.team_facts) == (1, 1)
    assert unmapped_teams(con) == []
    assert unmapped_stages(con) == []
    rerun = fill_canonical_ids(con)
    assert (rerun.headers, rerun.team_facts, rerun.standings_facts) == (1, 1, 0)


def test_publish_writes_canonical_ids(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    _insert_run(con, run)

    assert publish(con, candidate, standings, _SPEC, run) is Outcome.ACCEPTED

    header_id = con.execute("SELECT dataderby_stage_id FROM competition_snapshot").fetchone()[0]
    assert header_id is not None
    team_ids = {
        row[0]: row[1]
        for row in con.execute(
            "SELECT whoscored_team_id, dataderby_team_id FROM fact_team_snapshot"
        ).fetchall()
    }
    assert len(team_ids) == 20 and all(team_ids.values())
    stage_of_team = con.execute(
        "SELECT dataderby_stage_id FROM stage_source_key WHERE source = 'whoscored'"
    ).fetchone()[0]
    assert header_id == stage_of_team


def test_canonical_ids_are_stable_across_snapshots(
    con: duckdb.DuckDBPyConnection,
) -> None:
    from dataderby.parse import build_candidate
    from dataderby.parse_standings import parse_views
    from tests.test_assertions import _replace_measure
    from tests.test_publish import _run_at

    candidate, standings, run = _clean()
    _insert_run(con, run)
    assert publish(con, candidate, standings, _SPEC, run) is Outcome.ACCEPTED
    first = {
        row[0]: row[1]
        for row in con.execute(
            "SELECT whoscored_team_id, dataderby_team_id FROM fact_team_snapshot"
        ).fetchall()
    }

    second_run = _run_at("run_2", _now())
    candidate2 = build_candidate(list(second_run.feeds), _SPEC)
    candidate2 = _replace_measure(candidate2, 0, "rating_overall", 9.99)
    standings2 = parse_views(second_run.page, _SPEC)
    _insert_run(con, second_run)
    assert publish(con, candidate2, standings2, _SPEC, second_run) is Outcome.ACCEPTED
    second = {
        row[0]: row[1]
        for row in con.execute(
            """
            SELECT whoscored_team_id, dataderby_team_id FROM fact_team_snapshot
            WHERE snapshot_id <> (SELECT min(snapshot_id) FROM fact_team_snapshot)
            """
        ).fetchall()
    }
    assert first == second


def test_a23_fires_when_a_mapping_is_missing(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    _insert_run(con, run)
    _mapped(con)
    con.execute(
        "DELETE FROM team_source_key WHERE source_team_id = ?",
        [str(candidate.rows[0].whoscored_team_id)],
    )

    failures = run_assertions(con, candidate, standings, _SPEC, run)
    ids = {failure.assertion_id for failure in failures}

    assert "A23" in ids


def test_a24_fires_when_the_stage_mapping_is_missing(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    _insert_run(con, run)
    _mapped(con)
    con.execute("DELETE FROM stage_source_key WHERE source = 'whoscored'")

    failures = run_assertions(con, candidate, standings, _SPEC, run)
    ids = {failure.assertion_id for failure in failures}

    assert "A24" in ids


def test_clean_candidate_passes_a23_and_a24(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    _insert_run(con, run)
    _mapped(con)

    failures = run_assertions(con, candidate, standings, _SPEC, run)
    ids = {failure.assertion_id for failure in failures}

    assert "A23" not in ids and "A24" not in ids


def test_assertion_contract_includes_dims_ids() -> None:
    ids = [definition.assertion_id for definition in load_assertions()]

    assert "A23" in ids and "A24" in ids
    assert len(ids) == len(set(ids))


def _empty_config(tmp_path: Path) -> Path:
    path = tmp_path / "stages.toml"
    path.write_text(
        f"""[settings]
db_path = "{(tmp_path / "dims.duckdb").as_posix()}"
raw_dir = "{(tmp_path / "raw").as_posix()}"
log_dir = "{(tmp_path / "logs").as_posix()}"
""",
        encoding="utf-8",
    )
    return path


def test_map_team_cli_curates_a_new_club(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _empty_config(tmp_path)
    assert (
        main(["dims", "map-team", "--config", str(config), "--team-id", "999", "--name", "Test FC"])
        == 0
    )
    out = capsys.readouterr().out

    assert "999 (Test FC) -> dtm_" in out
    con = connect(tmp_path / "dims.duckdb", read_only=True)
    try:
        count = con.execute("SELECT count(*) FROM dim_team").fetchone()
    finally:
        con.close()
    assert count == (1,)


def test_map_stage_cli_curates_a_stage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from tests.test_pipeline_cli import _config as _pipe_config

    config = _pipe_config(tmp_path)
    assert main(["dims", "map-stage", "--config", str(config), "--stage", "epl-test"]) == 0
    out = capsys.readouterr().out

    assert "epl-test -> dst_" in out


def test_views_expose_canonical_names(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    _insert_run(con, run)
    assert publish(con, candidate, standings, _SPEC, run) is Outcome.ACCEPTED

    rows = con.execute(
        "SELECT count(*), count(canonical_team_name) FROM v_latest_team_state"
    ).fetchone()
    history = con.execute("SELECT count(canonical_team_name) FROM v_standings_history").fetchone()
    joined = con.execute("SELECT count(*) FROM v_latest_team_with_standings").fetchone()

    assert rows == (20, 20)
    assert history == (20,)
    assert joined == (20,)


def test_dims_backfill_uses_registry_names(tmp_path: Path) -> None:
    from tests.test_pipeline_cli import _config as _pipe_config

    config = _pipe_config(tmp_path)
    seen: list[str] = []
    assert main(["run", "--config", str(config)], runtime=_archived_runtime(seen)) == 0
    assert main(["dims", "backfill", "--config", str(config)]) == 0
    con = connect(tmp_path / "pipeline.duckdb", read_only=True)
    try:
        names = con.execute("SELECT tournament_name, canonical_name FROM dim_stage").fetchall()
    finally:
        con.close()

    assert names == [("Premier League", "Premier League 2026-2027")]


def test_dims_backfill_maps_stages_and_fills_ids(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tests.test_pipeline_cli import _config as _pipe_config

    config = _pipe_config(tmp_path)
    seen: list[str] = []
    assert main(["run", "--config", str(config)], runtime=_archived_runtime(seen)) == 0
    assert main(["dims", "backfill", "--config", str(config)]) == 0
    out = capsys.readouterr().out

    assert "coverage: 100% teams and stages mapped" in out
    con = connect(tmp_path / "pipeline.duckdb", read_only=True)
    try:
        nulls = con.execute(
            "SELECT count(*) FROM fact_team_snapshot WHERE dataderby_team_id IS NULL"
        ).fetchone()
    finally:
        con.close()
    assert nulls == (0,)
