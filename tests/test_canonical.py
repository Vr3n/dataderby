"""Canonical-byte and fingerprint tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from dataderby.canonical import canonical_bytes, fingerprint
from dataderby.contract import MEASURE_COLUMNS, STANDINGS_MEASURES
from dataderby.parse import Candidate, IncompleteCohort, TeamRow
from dataderby.parse_standings import StandingsCandidate, StandingsTeamRow

_TEAMS = tuple(100 + index for index in range(20))
_GOLDEN = Path("tests/golden/expected.json")


def _measure_map(team_id: int, *, reverse: bool = False) -> dict[str, float | int | None]:
    values: dict[str, float | int | None] = {}
    for column in MEASURE_COLUMNS:
        if column.startswith("apps_"):
            value: float | int = 7
        elif column.startswith("ranking_"):
            value = (team_id - 100) % 20 + 1
        elif column.startswith("rating_"):
            value = 6.0 + (team_id - 100) / 10.0
        elif column.startswith("shots_per_game_"):
            value = 10.0 + (team_id - 100) / 10.0
        else:
            value = float(team_id) / 10.0 + len(column)
        values[column] = value
    if reverse:
        values = dict(reversed(list(values.items())))
    return values


def _candidate(*, reverse_keys: bool = False) -> Candidate:
    rows = tuple(
        TeamRow(
            whoscored_team_id=team_id,
            whoscored_team_name=f"Team {team_id}",
            measures=_measure_map(team_id, reverse=reverse_keys),
        )
        for team_id in _TEAMS
    )
    return Candidate(
        whoscored_tournament_id=2,
        is_opta=True,
        rows=rows,
    )


def _standings() -> StandingsCandidate:
    rows = []
    for index, team_id in enumerate(_TEAMS, start=1):
        measures: dict[str, int | str | None] = {}
        for measure in STANDINGS_MEASURES:
            if measure.startswith("form_"):
                measures[measure] = "wwwwww"
            elif measure.startswith("rank_"):
                measures[measure] = index
            else:
                measures[measure] = index
        rows.append(
            StandingsTeamRow(
                whoscored_team_id=team_id,
                whoscored_team_name=f"Team {team_id}",
                measures=measures,
            )
        )
    return StandingsCandidate(rows=tuple(rows))


def _replace_measure(candidate: Candidate, column: str, value: float | int) -> Candidate:
    first = candidate.rows[0]
    measures = dict(first.measures)
    measures[column] = value
    rows = (
        TeamRow(first.whoscored_team_id, first.whoscored_team_name, measures),
        *candidate.rows[1:],
    )
    return Candidate(
        whoscored_tournament_id=candidate.whoscored_tournament_id,
        is_opta=candidate.is_opta,
        rows=rows,
    )


def test_payload_has_contract_measures_without_names() -> None:
    candidate = _candidate()
    standings = _standings()
    payload = json.loads(canonical_bytes(candidate, standings))

    assert payload["canonical_version"] == 1
    assert payload["is_opta"] is True
    assert payload["whoscored_tournament_id"] == 2
    assert len(payload["teams"]) == 20
    assert len(payload["teams"][0]["measures"]) == len(MEASURE_COLUMNS)
    assert len(payload["teams"][0]["standings"]) == len(STANDINGS_MEASURES)
    assert "whoscored_team_name" not in payload["teams"][0]
    assert "paging" not in payload


def test_rows_are_sorted_and_keys_are_stable() -> None:
    candidate = _candidate()
    first = canonical_bytes(candidate, _standings())
    reversed_candidate = Candidate(
        whoscored_tournament_id=candidate.whoscored_tournament_id,
        is_opta=candidate.is_opta,
        rows=tuple(reversed(candidate.rows)),
    )
    reversed_keys = canonical_bytes(_candidate(reverse_keys=True), _standings())

    assert canonical_bytes(reversed_candidate, _standings()) == first
    assert reversed_keys == first


def test_none_is_null_and_floats_use_repr() -> None:
    candidate = _replace_measure(_candidate(), "summary_overall_possession", 0.1 + 0.2)
    first = candidate.rows[0]
    measures = dict(first.measures)
    measures["summary_overall_aerial_won_per_game"] = None
    candidate = Candidate(
        whoscored_tournament_id=candidate.whoscored_tournament_id,
        is_opta=candidate.is_opta,
        rows=(
            TeamRow(first.whoscored_team_id, first.whoscored_team_name, measures),
            *candidate.rows[1:],
        ),
    )

    text = canonical_bytes(candidate, _standings()).decode("utf-8")

    assert '"summary_overall_aerial_won_per_game":null' in text
    assert '"summary_overall_possession":0.30000000000000004' in text


def test_changing_a_measure_changes_the_fingerprint() -> None:
    original = fingerprint(_candidate(), _standings())
    changed = fingerprint(
        _replace_measure(_candidate(), "summary_overall_goal", 999.0),
        _standings(),
    )

    assert original != changed


def test_changing_a_rank_or_form_changes_the_fingerprint() -> None:
    standings = _standings()
    first = standings.rows[0]
    measures = dict(first.measures)
    measures["rank_overall"] = 99
    measures["form_home"] = "llllll"
    changed_standings = StandingsCandidate(
        rows=(
            StandingsTeamRow(
                first.whoscored_team_id,
                first.whoscored_team_name,
                measures,
            ),
            *standings.rows[1:],
        )
    )

    assert fingerprint(_candidate(), standings) != fingerprint(_candidate(), changed_standings)


def test_missing_measure_is_rejected() -> None:
    candidate = _candidate()
    first = candidate.rows[0]
    incomplete = Candidate(
        whoscored_tournament_id=candidate.whoscored_tournament_id,
        is_opta=candidate.is_opta,
        rows=(TeamRow(first.whoscored_team_id, first.whoscored_team_name, {"apps_overall": 7}),),
    )

    with pytest.raises(ValueError, match="missing measures"):
        canonical_bytes(incomplete, StandingsCandidate(rows=()))


def test_standings_team_set_must_match_the_feed() -> None:
    standings = _standings()
    extra = StandingsTeamRow(999, "Extra", standings.rows[0].measures)
    changed = StandingsCandidate(rows=(*standings.rows, extra))

    with pytest.raises(IncompleteCohort, match="standings and feed"):
        canonical_bytes(_candidate(), changed)


def test_empty_standings_are_serialized_as_empty_objects() -> None:
    payload = json.loads(canonical_bytes(_candidate(), StandingsCandidate(rows=())))

    assert payload["teams"][0]["standings"] == {}


@given(st.floats(allow_nan=False, allow_infinity=False, width=32))
def test_float_values_are_stable(value: float) -> None:
    candidate = _replace_measure(_candidate(), "summary_overall_possession", value)

    first = canonical_bytes(candidate, _standings())
    second = canonical_bytes(candidate, _standings())

    assert first == second
    assert json.loads(first)["teams"][0]["measures"]["summary_overall_possession"] == value


@given(st.permutations(_TEAMS))
def test_any_row_order_has_the_same_fingerprint(order: tuple[int, ...]) -> None:
    candidate = _candidate()
    by_id = {row.whoscored_team_id: row for row in candidate.rows}
    shuffled = Candidate(
        whoscored_tournament_id=candidate.whoscored_tournament_id,
        is_opta=candidate.is_opta,
        rows=tuple(by_id[team_id] for team_id in order),
    )

    assert fingerprint(shuffled, _standings()) == fingerprint(_candidate(), _standings())


@given(st.permutations(MEASURE_COLUMNS))
def test_any_measure_key_order_has_the_same_fingerprint(
    order: tuple[str, ...],
) -> None:
    candidate = _candidate()
    rows = tuple(
        TeamRow(
            whoscored_team_id=row.whoscored_team_id,
            whoscored_team_name=row.whoscored_team_name,
            measures={column: row.measures[column] for column in order},
        )
        for row in candidate.rows
    )
    shuffled = Candidate(
        whoscored_tournament_id=candidate.whoscored_tournament_id,
        is_opta=candidate.is_opta,
        rows=rows,
    )

    assert canonical_bytes(shuffled, _standings()) == canonical_bytes(_candidate(), _standings())


@given(st.integers(min_value=0, max_value=1_000_000))
def test_integer_rank_changes_are_deterministic(value: int) -> None:
    standings = _standings()
    first = standings.rows[0]
    measures = dict(first.measures)
    measures["rank_away"] = value
    changed = StandingsCandidate(
        rows=(
            StandingsTeamRow(first.whoscored_team_id, first.whoscored_team_name, measures),
            *standings.rows[1:],
        )
    )

    assert canonical_bytes(_candidate(), changed) == canonical_bytes(_candidate(), changed)


def test_committed_golden_fingerprint() -> None:
    expected = json.loads(_GOLDEN.read_text(encoding="utf-8"))

    assert expected["canonical_version"] == 1
    assert fingerprint(_candidate(), _standings()) == expected["sha256"]
