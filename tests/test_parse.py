"""Parser contract tests."""

from __future__ import annotations

import pytest

from dataderby.fixtures.competitions import Competition
from dataderby.fixtures.parse import (
    FixtureParseError,
    fixture_key,
    parse_csv,
    parse_kickoff,
    parse_result,
)
from tests.helpers import HEADER, ROWS, csv_bytes

COMPETITION = Competition("test", "test-2026", "Test League", "Testland")


def test_kickoff_is_converted_from_utc_to_ist() -> None:
    utc, ist = parse_kickoff("21/08/2026 19:00")

    assert utc.isoformat() == "2026-08-21T19:00:00+00:00"
    assert ist.isoformat(timespec="seconds") == "2026-08-22T00:30:00+05:30"


def test_result_parses_played_and_pending() -> None:
    assert parse_result("3 - 0") == (3, 0)
    assert parse_result("") == (None, None)
    assert parse_result("-") == (None, None)


def test_result_rejects_malformed_scores() -> None:
    with pytest.raises(FixtureParseError):
        parse_result("3-0-1")


def test_parse_csv_builds_typed_fixtures() -> None:
    fixtures = parse_csv(COMPETITION, csv_bytes())

    assert [fixture.status for fixture in fixtures] == ["played", "scheduled"]
    assert fixtures[0].home_score == 3
    assert fixtures[0].away_score == 0
    assert fixtures[1].home_score is None
    assert fixtures[0].kickoff_ist.isoformat(timespec="seconds") == ("2026-08-22T00:30:00+05:30")


def test_fixture_key_is_deterministic_and_ignores_match_number() -> None:
    first = fixture_key("epl", "2026/27", 1, "Arsenal", "Coventry")
    second = fixture_key("epl", "2026/27", 1, "Arsenal", "Coventry")

    assert first == second
    assert len(first) == 20
    assert first != fixture_key("epl", "2026/27", 1, "Coventry", "Arsenal")


def test_column_drift_is_rejected() -> None:
    body = csv_bytes(header=HEADER[:-1])

    with pytest.raises(FixtureParseError, match="unexpected columns"):
        parse_csv(COMPETITION, body)


def test_duplicate_fixture_is_rejected() -> None:
    body = csv_bytes(rows=(ROWS[0], ROWS[0]))

    with pytest.raises(FixtureParseError, match="duplicate fixture"):
        parse_csv(COMPETITION, body)


def test_unicode_team_names_survive_round_trip() -> None:
    rows = (("1", "1", "21/08/2026 19:00", "Stadion", "Fenerbahçe", "Gent", "2 - 1"),)

    fixture = parse_csv(COMPETITION, csv_bytes(rows))[0]

    assert fixture.home_team == "Fenerbahçe"
    assert fixture.away_team == "Gent"
