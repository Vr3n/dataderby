"""Standings parsing tests; no browser and no network."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dataderby.contract import View
from dataderby.page import PageCapture
from dataderby.standings import (
    RawStandingsRow,
    StandingsParseError,
    decode_view,
    encode_view,
    parse_standings,
    parse_view,
)


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
