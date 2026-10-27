"""Publish-contract assertion tests; DuckDB only, no browser and no network."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from dataderby.config import StageSpec
from dataderby.contract import View
from dataderby.db import connect, migrate
from dataderby.dims import ensure_stage_mapping, ensure_team_mapping
from dataderby.fetch import Capture
from dataderby.landing import LandingResult
from dataderby.page import PageCapture
from dataderby.parse import Candidate, TeamRow, build_candidate
from dataderby.parse_standings import StandingsCandidate, parse_views
from dataderby.standings import RawStandingsRow
from dataderby.validate import (
    Action,
    AssertionFailure,
    blocking_failures,
    load_assertions,
    run_assertions,
)
from tests.test_whoscored_parse import _SPEC, _TEAMS, _captures

_NOW = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
_PAGE_URL = (
    "https://www.whoscored.com/regions/252/tournaments/2/seasons/11141/"
    "stages/25544/show/england-premier-league-2026-2027"
)


@pytest.fixture
def con(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = connect(tmp_path / "test.duckdb")
    migrate(connection)
    for team_id in _TEAMS:
        ensure_team_mapping(connection, team_id, f"Team {team_id}")
    ensure_stage_mapping(
        connection,
        tournament_id=_SPEC.whoscored_tournament_id,
        season_id=_SPEC.whoscored_season_id,
        stage_id=_SPEC.whoscored_stage_id,
        tournament_name=_SPEC.competition,
        season_key=_SPEC.season_key,
        stage_code=_SPEC.stage,
        canonical_name=f"{_SPEC.competition} {_SPEC.season_key}",
    )
    try:
        yield connection
    finally:
        connection.close()


def _raw_standings(view: View, team_id: int, name: str, rank: int) -> RawStandingsRow:
    if view == "overall":
        played, won, drawn, lost = 10, 6, 2, 2
        goals_for, goals_against, points = 15, 9, 20
        form = "wwdllw"
    elif view == "home":
        played, won, drawn, lost = 5, 3, 1, 1
        goals_for, goals_against, points = 8, 4, 10
        form = "wwdlw"
    else:
        played, won, drawn, lost = 5, 3, 1, 1
        goals_for, goals_against, points = 7, 5, 10
        form = "wwdlw"
    return RawStandingsRow(
        whoscored_team_id=team_id,
        whoscored_team_name=name,
        rank=str(rank),
        played=str(played),
        won=str(won),
        drawn=str(drawn),
        lost=str(lost),
        goals_for=str(goals_for),
        goals_against=str(goals_against),
        goal_difference=str(goals_for - goals_against),
        points=str(points),
        form=form,
    )


def _page(
    *,
    url: str = _PAGE_URL,
    captured_at: datetime = _NOW,
    standings: dict[View, tuple[RawStandingsRow, ...]] | None = None,
) -> PageCapture:
    if standings is None:
        standings = {
            view: tuple(
                _raw_standings(view, team_id, f"Team {team_id}", rank)
                for rank, team_id in enumerate(_TEAMS, start=1)
            )
            for view in ("overall", "home", "away")
        }
    return PageCapture(
        html="<html></html>",
        token="token",
        stages=(),
        standings=standings,
        captured_at=captured_at,
        url=url,
    )


def _run(
    page: PageCapture | None = None,
    feeds: list[Capture] | None = None,
    *,
    run_id: str = "run_1",
    observed_at: datetime = _NOW,
) -> LandingResult:
    return LandingResult(
        run_id=run_id,
        observed_at=observed_at,
        page=page or _page(),
        feeds=tuple(feeds if feeds is not None else _captures()),
        raw_files=(),
    )


def _clean(
    *,
    run: LandingResult | None = None,
) -> tuple[Candidate, StandingsCandidate, LandingResult]:
    landing = run or _run()
    candidate = build_candidate(list(landing.feeds), _SPEC)
    standings = parse_views(landing.page, _SPEC)
    return candidate, standings, landing


def _insert_run(
    con: duckdb.DuckDBPyConnection,
    run: LandingResult,
    spec: StageSpec = _SPEC,
) -> None:
    con.execute(
        """
        INSERT INTO ingestion_run (
            run_id, mode, started_at, outcome, whoscored_tournament_id,
            whoscored_season_id, whoscored_stage_id
        ) VALUES (?, 'full', ?, 'running', ?, ?, ?)
        """,
        [
            run.run_id,
            run.observed_at,
            spec.whoscored_tournament_id,
            spec.whoscored_season_id,
            spec.whoscored_stage_id,
        ],
    )


def _ids(failures: list[AssertionFailure]) -> set[str]:
    return {failure.assertion_id for failure in failures}


def test_assertion_file_loads_all_contract_ids() -> None:
    definitions = load_assertions()
    ids = [definition.assertion_id for definition in definitions]

    assert set(ids) == {*(f"A{number}" for number in range(1, 23)), "A7U", "A23", "A24"}
    assert len(ids) == len(set(ids))
    assert {definition.action for definition in definitions} == {
        Action.BLOCK,
        Action.RETRY,
        Action.WARN,
    }
    assert all(definition.sql for definition in definitions)


def test_assertion_loader_reads_every_contract_file(tmp_path: Path) -> None:
    (tmp_path / "002_assertions.sql").write_text("-- @@A1|BLOCK\n-- SELECT 1\n", encoding="utf-8")
    (tmp_path / "005_assertions.sql").write_text("-- @@A22|WARN\n-- SELECT 2\n", encoding="utf-8")

    definitions = load_assertions(tmp_path)

    assert [definition.assertion_id for definition in definitions] == ["A1", "A22"]


def test_assertion_loader_rejects_a_duplicate_id_across_files(tmp_path: Path) -> None:
    (tmp_path / "002_assertions.sql").write_text("-- @@A1|BLOCK\n-- SELECT 1\n", encoding="utf-8")
    (tmp_path / "005_assertions.sql").write_text("-- @@A1|WARN\n-- SELECT 2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate assertion id"):
        load_assertions(tmp_path)


def test_assertion_loader_rejects_a_marker_without_sql(tmp_path: Path) -> None:
    (tmp_path / "002_assertions.sql").write_text("-- @@A1|BLOCK\n", encoding="utf-8")

    with pytest.raises(ValueError, match="has no SQL"):
        load_assertions(tmp_path)


def test_assertion_loader_rejects_a_directory_without_a_contract(tmp_path: Path) -> None:
    (tmp_path / "001_schema.sql").write_text("SELECT 1;\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="no assertion files"):
        load_assertions(tmp_path)


def test_clean_candidate_passes_every_assertion(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    _insert_run(con, run)

    failures = run_assertions(con, candidate, standings, _SPEC, run)

    assert failures == []


def test_a1_expected_team_count_blocks(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    short = Candidate(
        whoscored_tournament_id=candidate.whoscored_tournament_id,
        is_opta=candidate.is_opta,
        rows=candidate.rows[:-1],
    )

    failures = run_assertions(con, short, standings, _SPEC, run)

    assert "A1" in _ids(failures)


def test_a2_duplicate_team_ids_block(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    duplicate = Candidate(
        whoscored_tournament_id=candidate.whoscored_tournament_id,
        is_opta=candidate.is_opta,
        rows=(*candidate.rows, candidate.rows[0]),
    )

    failures = run_assertions(con, duplicate, standings, _SPEC, run)

    assert "A2" in _ids(failures)


def test_a3_missing_feed_capture_blocks(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    short_run = _run(feeds=list(run.feeds)[:-1])

    failures = run_assertions(con, candidate, standings, _SPEC, short_run)

    assert "A3" in _ids(failures)


def test_a4_different_team_set_blocks(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    captures = list(run.feeds)
    first = captures[0]
    short_body = _body_for("summary", "overall", _TEAMS[:-1])
    captures[0] = Capture(
        section=first.section,
        view=first.view,
        body=short_body,
        captured_at=first.captured_at,
        content_type=first.content_type,
        url=first.url,
    )
    bad_run = _run(feeds=captures)

    failures = run_assertions(con, candidate, standings, _SPEC, bad_run)

    assert "A4" in _ids(failures)
    assert (
        next(failure for failure in failures if failure.assertion_id == "A4").action is Action.RETRY
    )


def _body_for(section: str, view: str, teams: list[int]) -> bytes:
    from tests.test_whoscored_parse import _body

    return _body(section, view, teams)  # type: ignore[arg-type]


def _replace_measure(
    candidate: Candidate, team_index: int, column: str, value: object
) -> Candidate:
    rows = list(candidate.rows)
    row = rows[team_index]
    measures = dict(row.measures)
    measures[column] = value
    rows[team_index] = TeamRow(row.whoscored_team_id, row.whoscored_team_name, measures)
    return Candidate(candidate.whoscored_tournament_id, candidate.is_opta, tuple(rows))


def test_a5_split_totals_must_add_up(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    poisoned = _replace_measure(candidate, 0, "apps_home", 99)

    failures = run_assertions(con, poisoned, standings, _SPEC, run)

    assert "A5" in _ids(failures)
    assert (
        next(failure for failure in failures if failure.assertion_id == "A5").action is Action.RETRY
    )


def test_a6_shared_measure_must_agree_across_sections(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    captures = list(run.feeds)
    for index, capture in enumerate(captures):
        if (capture.section, capture.view) == ("offensive", "overall"):
            captures[index] = Capture(
                section=capture.section,
                view=capture.view,
                body=_body_with_override("offensive", "overall", 100, "shotsPerGame", 99.0),
                captured_at=capture.captured_at,
                content_type=capture.content_type,
                url=capture.url,
            )
    bad_run = _run(feeds=captures)

    failures = run_assertions(con, candidate, standings, _SPEC, bad_run)

    assert "A6" in _ids(failures)


def _body_with_override(section: str, view: str, team_id: int, source: str, value: object) -> bytes:
    from tests.test_whoscored_parse import _body

    return _body(  # type: ignore[arg-type]
        section,
        view,
        _TEAMS,
        overrides={team_id: {source: value}},
    )


def test_a7_ranking_range_blocks_but_duplicate_only_warns(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    out_of_range = _replace_measure(candidate, 0, "ranking_summary_overall", 0)

    failures = run_assertions(con, out_of_range, standings, _SPEC, run)
    assert "A7" in _ids(failures)
    assert all(
        failure.action is not Action.WARN for failure in failures if failure.assertion_id == "A7"
    )

    duplicate = _replace_measure(candidate, 1, "ranking_summary_overall", 1)
    failures = run_assertions(con, duplicate, standings, _SPEC, run)
    assert "A7U" in _ids(failures)
    assert all(
        failure.action is Action.WARN for failure in failures if failure.assertion_id == "A7U"
    )


def test_a8_non_finite_or_out_of_range_measure_blocks(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    poisoned = _replace_measure(candidate, 0, "rating_overall", 11.0)

    failures = run_assertions(con, poisoned, standings, _SPEC, run)
    assert "A8" in _ids(failures)

    nan_candidate = _replace_measure(candidate, 0, "summary_overall_possession", float("nan"))
    failures = run_assertions(con, nan_candidate, standings, _SPEC, run)
    assert "A8" in _ids(failures)


def test_a9_null_identity_blocks(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    row = candidate.rows[0]
    poisoned = Candidate(
        candidate.whoscored_tournament_id,
        candidate.is_opta,
        (TeamRow(row.whoscored_team_id, None, row.measures), *candidate.rows[1:]),  # type: ignore[arg-type]
    )

    failures = run_assertions(con, poisoned, standings, _SPEC, run)

    assert "A9" in _ids(failures)


def test_a10_apps_may_not_decrease(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    _seed_previous_snapshot(con, apps=99)

    failures = run_assertions(con, candidate, standings, _SPEC, run)
    assert "A10" in _ids(failures)

    failures = run_assertions(con, candidate, standings, _SPEC, run, allow_apps_decrease=True)
    assert "A10" not in _ids(failures)


def _seed_previous_snapshot(con: duckdb.DuckDBPyConnection, *, apps: int) -> None:
    con.execute(
        """
        INSERT INTO competition_snapshot (
            snapshot_id, parent_snapshot_id, whoscored_tournament_id,
            whoscored_season_id, whoscored_stage_id, season_key,
            content_fingerprint, canonical_version, observed_at, accepted_at,
            capture_span_seconds, is_opta, whoscored_page_url, run_id
        ) VALUES ('snap_prev', 'genesis', ?, ?, ?, '2026/27', 'fp_prev', 1,
                  ?, ?, 0, true, ?, 'run_prev')
        """,
        [
            _SPEC.whoscored_tournament_id,
            _SPEC.whoscored_season_id,
            _SPEC.whoscored_stage_id,
            _NOW - timedelta(days=1),
            _NOW - timedelta(days=1),
            _PAGE_URL,
        ],
    )
    con.execute(
        """
        INSERT INTO fact_team_snapshot (
            snapshot_id, whoscored_team_id, whoscored_team_name,
            apps_overall, apps_home, apps_away
        ) VALUES ('snap_prev', 100, 'Team 100', ?, ?, ?)
        """,
        [apps, apps // 2, apps - apps // 2],
    )


def test_a11_feed_url_must_name_the_stage(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    captures = list(run.feeds)
    first = captures[0]
    captures[0] = Capture(
        section=first.section,
        view=first.view,
        body=first.body,
        captured_at=first.captured_at,
        content_type=first.content_type,
        url="https://www.whoscored.com/feed?section=summary&view=overall",
    )
    bad_run = _run(feeds=captures)

    failures = run_assertions(con, candidate, standings, _SPEC, bad_run)

    assert "A11" in _ids(failures)


def test_a12_page_url_must_name_season_and_stage(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, _ = _clean()
    bad_run = _run(page=_page(url="https://www.whoscored.com/example"))

    failures = run_assertions(con, candidate, standings, _SPEC, bad_run)

    assert "A12" in _ids(failures)


def test_a13_feed_metadata_must_match_the_stage(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    captures = list(run.feeds)
    first = captures[0]
    captures[0] = Capture(
        section=first.section,
        view=first.view,
        body=_body_with_override("summary", "overall", 100, "tournamentId", 3),
        captured_at=first.captured_at,
        content_type=first.content_type,
        url=first.url,
    )
    bad_run = _run(feeds=captures)

    failures = run_assertions(con, candidate, standings, _SPEC, bad_run)

    assert "A13" in _ids(failures)


def test_a14_slow_capture_span_retries(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    captures = list(run.feeds)
    first = captures[0]
    captures[0] = Capture(
        section=first.section,
        view=first.view,
        body=first.body,
        captured_at=first.captured_at + timedelta(seconds=181),
        content_type=first.content_type,
        url=first.url,
    )
    slow_run = _run(feeds=captures)

    failures = run_assertions(con, candidate, standings, _SPEC, slow_run)

    assert "A14" in _ids(failures)
    assert (
        next(failure for failure in failures if failure.assertion_id == "A14").action
        is Action.RETRY
    )


def test_a15_schema_drift_blocks(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    captures = list(run.feeds)
    first = captures[0]
    captures[0] = Capture(
        section=first.section,
        view=first.view,
        body=b'{"teamTableStats": [], "statColumns": ["apps"]}',
        captured_at=first.captured_at,
        content_type=first.content_type,
        url=first.url,
    )
    bad_run = _run(feeds=captures)

    failures = run_assertions(con, candidate, standings, _SPEC, bad_run)

    assert "A15" in _ids(failures)


def test_a16_schema_rejects_orphans_before_the_assertion(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    with pytest.raises(duckdb.ConstraintException):
        con.execute(
            """
            INSERT INTO fact_team_snapshot (
                snapshot_id, whoscored_team_id, whoscored_team_name
            ) VALUES ('missing_header', 999, 'Orphan')
            """
        )

    failures = run_assertions(con, candidate, standings, _SPEC, run)

    assert "A16" not in _ids(failures)


def test_a17_missing_standings_views_retry(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, _ = _clean()
    bad_run = _run(page=_page(standings={}))

    failures = run_assertions(con, candidate, standings, _SPEC, bad_run)

    assert "A17" in _ids(failures)


def test_a17_ignores_a_table_when_the_stage_has_none(
    con: duckdb.DuckDBPyConnection,
) -> None:
    spec = _SPEC.model_copy(update={"has_league_table": False})
    candidate, _standings, run = _clean()
    assert parse_views(run.page, spec).rows == ()
    clean = StandingsCandidate(rows=())

    failures = run_assertions(con, candidate, clean, spec, run)

    assert "A17" not in _ids(failures)


def test_provenance_assertions_are_skipped_without_a_run(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, _ = _clean()

    failures = run_assertions(con, candidate, standings, _SPEC)

    assert not (_ids(failures) & {"A3", "A4", "A11", "A12", "A15", "A17"})


def test_a18_feed_and_standings_team_sets_must_match(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    short_standings = StandingsCandidate(rows=standings.rows[:-1])

    failures = run_assertions(con, candidate, short_standings, _SPEC, run)

    assert "A18" in _ids(failures)


def _replace_standings_measure(
    standings: StandingsCandidate, team_index: int, column: str, value: object
) -> StandingsCandidate:
    rows = list(standings.rows)
    row = rows[team_index]
    measures = dict(row.measures)
    measures[column] = value
    rows[team_index] = row.__class__(
        row.whoscored_team_id,
        row.whoscored_team_name,
        measures,
    )
    return StandingsCandidate(tuple(rows))


def test_a19_standings_arithmetic_blocks(con: duckdb.DuckDBPyConnection) -> None:
    candidate, standings, run = _clean()
    poisoned = _replace_standings_measure(standings, 0, "points_overall", 999)

    failures = run_assertions(con, candidate, poisoned, _SPEC, run)

    assert "A19" in _ids(failures)


def test_a_points_deduction_is_not_blocked(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    row = standings.rows[0]
    points = int(row.measures["points_overall"])  # type: ignore[arg-type]
    deducted = _replace_standings_measure(standings, 0, "points_overall", points - 4)

    failures = run_assertions(con, candidate, deducted, _SPEC, run)

    assert "A19" not in _ids(failures)
    assert "A20" not in _ids(failures)


def test_a22_reports_a_points_deduction_as_a_warning(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    row = standings.rows[0]
    points = int(row.measures["points_overall"])  # type: ignore[arg-type]
    deducted = _replace_standings_measure(standings, 0, "points_overall", points - 4)

    failures = run_assertions(con, candidate, deducted, _SPEC, run)

    [warning] = [failure for failure in failures if failure.assertion_id == "A22"]
    assert warning.action is Action.WARN
    assert warning.rows == (
        (row.whoscored_team_id, row.whoscored_team_name, points - 4, points, -4),
    )
    assert blocking_failures(failures) == []


def test_a22_is_absent_when_every_total_matches_won_and_drawn(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()

    failures = run_assertions(con, candidate, standings, _SPEC, run)

    assert "A22" not in _ids(failures)


def test_a22_checks_only_the_overall_table(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    row = standings.rows[0]
    points = int(row.measures["points_home"])  # type: ignore[arg-type]
    deducted = _replace_standings_measure(standings, 0, "points_home", points - 4)

    failures = run_assertions(con, candidate, deducted, _SPEC, run)

    assert "A22" not in _ids(failures)
    assert "A20" not in _ids(failures)


def test_a22_does_not_soften_an_impossible_total(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    poisoned = _replace_standings_measure(standings, 0, "points_overall", 999)

    failures = run_assertions(con, candidate, poisoned, _SPEC, run)

    assert "A19" in _ids(failures)
    assert "A22" not in _ids(failures)
    assert [failure.assertion_id for failure in blocking_failures(failures)] == ["A19"]


def test_a22_reports_each_deducted_team_with_its_own_gap(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    deducted = _replace_standings_measure(standings, 0, "points_overall", 16)
    deducted = _replace_standings_measure(deducted, 1, "points_overall", 19)

    failures = run_assertions(con, candidate, deducted, _SPEC, run)

    [warning] = [failure for failure in failures if failure.assertion_id == "A22"]
    assert warning.rows == (
        (
            deducted.rows[0].whoscored_team_id,
            deducted.rows[0].whoscored_team_name,
            16,
            20,
            -4,
        ),
        (
            deducted.rows[1].whoscored_team_id,
            deducted.rows[1].whoscored_team_name,
            19,
            20,
            -1,
        ),
    )


def test_a20_home_away_standings_must_add_up(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    poisoned = _replace_standings_measure(standings, 0, "played_home", 99)

    failures = run_assertions(con, candidate, poisoned, _SPEC, run)

    assert "A20" in _ids(failures)


def test_a21_standings_rank_permutation_blocks(
    con: duckdb.DuckDBPyConnection,
) -> None:
    candidate, standings, run = _clean()
    poisoned = _replace_standings_measure(standings, 0, "rank_overall", 2)

    failures = run_assertions(con, candidate, poisoned, _SPEC, run)

    assert "A21" in _ids(failures)
