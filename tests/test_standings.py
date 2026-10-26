"""Standings parsing tests; no browser and no network."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from dataderby.config import load_settings
from dataderby.contract import STANDINGS_MEASURES, View
from dataderby.page import PageCapture
from dataderby.parse import Candidate, IncompleteCohort, TeamRow
from dataderby.parse_standings import check_team_sets, parse_views
from dataderby.standings import (
    RawStandingsRow,
    StandingsParseError,
    decode_view,
    encode_view,
    parse_standings,
    parse_view,
)

_SPEC = load_settings(Path("config/stages.toml")).stages["epl-2026-2027"]


def _row(
    team_id: int,
    name: str,
    rank: int,
    *,
    played: int,
    form: str,
) -> RawStandingsRow:
    return RawStandingsRow(
        whoscored_team_id=team_id,
        whoscored_team_name=name,
        rank=str(rank),
        played=str(played),
        won=str(played),
        drawn="0",
        lost="0",
        goals_for=str(played * 2),
        goals_against="1",
        goal_difference=str(played * 2 - 1),
        points=str(played * 3),
        form=form,
    )


def _page(standings: dict[View, tuple[RawStandingsRow, ...]]) -> PageCapture:
    return PageCapture(
        html="<html></html>",
        token="token",
        stages=(),
        standings=standings,
        captured_at=datetime(2026, 10, 21, 10, 0, tzinfo=UTC),
        url="https://www.whoscored.com/example",
    )


def test_parses_three_views_and_preserves_team_ids() -> None:
    rows = (
        _row(211, "Brighton", 1, played=7, form="wwwwww"),
        _row(167, "Man City", 2, played=7, form="wdlwdl"),
    )

    parsed = parse_standings(_page({"overall": rows, "home": rows, "away": rows}))

    assert set(parsed) == {"overall", "home", "away"}
    assert {row.whoscored_team_id for row in parsed["overall"]} == {211, 167}
    assert parsed["overall"][0].points == 21
    assert parsed["overall"][0].form == "wwwwww"


def test_uppercase_form_is_normalised_to_lowercase() -> None:
    row = _row(211, "Brighton", 1, played=3, form="WWL")

    assert parse_view("overall", (row,))[0].form == "wwl"


def test_form_length_follows_played() -> None:
    short = (_row(211, "Brighton", 1, played=3, form="wdl"),)
    assert parse_view("overall", short)[0].form == "wdl"

    bad = (_row(211, "Brighton", 1, played=3, form="wwww"),)
    with pytest.raises(StandingsParseError, match="form length"):
        parse_view("overall", bad)


def test_zero_played_requires_null_form() -> None:
    zero = _row(211, "Brighton", 1, played=0, form="")
    assert parse_view("overall", (zero,))[0].form is None

    bad = _row(211, "Brighton", 1, played=0, form="w")
    with pytest.raises(StandingsParseError, match="null"):
        parse_view("overall", (bad,))


def test_no_table_gives_no_rows() -> None:
    assert parse_standings(_page({})) == {}


def test_duplicate_team_id_is_rejected() -> None:
    rows = (
        _row(211, "Brighton", 1, played=7, form="wwwwww"),
        _row(211, "Duplicate", 2, played=7, form="wwwwww"),
    )

    with pytest.raises(StandingsParseError, match="duplicate"):
        parse_view("overall", rows)


def test_rank_must_start_at_one() -> None:
    zero = _row(211, "Brighton", 0, played=7, form="wwwwww")

    with pytest.raises(StandingsParseError, match="rank out of range"):
        parse_view("overall", (zero,))


def test_encode_decode_round_trip() -> None:
    rows = (_row(211, "Brighton", 1, played=7, form="wwwwww"),)

    assert decode_view(encode_view("overall", rows)) == rows


def test_parse_views_builds_one_thirty_measure_row_per_team() -> None:
    rows = (
        _row(211, "Brighton", 1, played=7, form="wwwwww"),
        _row(167, "Man City", 2, played=7, form="wdlwdl"),
    )
    candidate = parse_views(_page({"overall": rows, "home": rows, "away": rows}))

    assert [row.whoscored_team_id for row in candidate.rows] == [167, 211]
    brighton = candidate.rows[1]
    assert set(brighton.measures) == set(STANDINGS_MEASURES)
    assert brighton.measures["rank_overall"] == 1
    assert brighton.measures["form_home"] == "wwwwww"
    assert brighton.measures["points_away"] == 21


def test_parse_views_returns_empty_for_a_stage_without_a_table() -> None:
    rows = (_row(211, "Brighton", 1, played=7, form="wwwwww"),)
    spec = _SPEC.model_copy(update={"has_league_table": False})

    candidate = parse_views(_page({"overall": rows, "home": rows, "away": rows}), spec)

    assert candidate.rows == ()


def test_parse_views_rejects_a_declared_table_that_was_not_captured() -> None:
    with pytest.raises(IncompleteCohort, match="declares a league table"):
        parse_views(_page({}), _SPEC)


def test_parse_views_rejects_a_team_missing_from_one_split() -> None:
    overall = (_row(211, "Brighton", 1, played=7, form="wwwwww"),)
    home = (_row(211, "Brighton", 1, played=7, form="wwwwww"),)
    away = (_row(167, "Man City", 1, played=7, form="wwwwww"),)

    with pytest.raises(StandingsParseError, match="all three splits"):
        parse_views(_page({"overall": overall, "home": home, "away": away}))


def test_parse_views_rejects_changed_team_names() -> None:
    rows = (_row(211, "Brighton", 1, played=7, form="wwwwww"),)
    away = (_row(211, "Brighton & Hove", 1, played=7, form="wwwwww"),)

    with pytest.raises(StandingsParseError, match="name differs"):
        parse_views(_page({"overall": rows, "home": rows, "away": away}))


def _candidate(*team_ids: int) -> Candidate:
    return Candidate(
        whoscored_tournament_id=2,
        is_opta=True,
        rows=tuple(
            TeamRow(
                whoscored_team_id=team_id,
                whoscored_team_name=f"Team {team_id}",
                measures={},
            )
            for team_id in team_ids
        ),
    )


def test_check_team_sets_accepts_equal_sets() -> None:
    rows = (
        _row(211, "Brighton", 1, played=7, form="wwwwww"),
        _row(167, "Man City", 2, played=7, form="wdlwdl"),
    )
    standings = parse_views(_page({"overall": rows, "home": rows, "away": rows}))

    check_team_sets(_candidate(211, 167), standings)


def test_check_team_sets_reports_both_differences() -> None:
    rows = (
        _row(211, "Brighton", 1, played=7, form="wwwwww"),
        _row(167, "Man City", 2, played=7, form="wdlwdl"),
    )
    standings = parse_views(_page({"overall": rows, "home": rows, "away": rows}))

    with pytest.raises(IncompleteCohort, match="feed_only=\\[999\\]"):
        check_team_sets(_candidate(211, 999), standings)


def test_check_team_sets_rejects_an_empty_standings_side() -> None:
    with pytest.raises(IncompleteCohort, match="no standings rows"):
        check_team_sets(_candidate(211), parse_views(_page({})))
