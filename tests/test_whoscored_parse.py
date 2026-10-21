"""Feed parsing and candidate-building tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dataderby.config import load_settings
from dataderby.contract import (
    EXPECTED_STAT_COLUMNS,
    MEASURE_COLUMNS,
    SECTIONS,
    VIEWS,
    Section,
    View,
)
from dataderby.fetch import Capture, SchemaDrift
from dataderby.parse import (
    IncompleteCohort,
    OwnershipMismatch,
    SourceParseError,
    build_candidate,
    parse_capture,
)

_SPEC = load_settings(Path("config/stages.toml")).stages["epl-2026-2027"]
_TEAMS = [100 + index for index in range(20)]
_NOW = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)


def _source_value(source: str, team_id: int) -> object:
    if source == "apps":
        return 7
    if source == "shotsPerGame":
        return 10.0 + team_id / 10.0
    if source == "goal":
        return float(team_id)
    if source == "yellowCard":
        return 1.0
    if source == "redCard":
        return 0.0
    if source == "possession":
        return 0.55
    if source == "passSuccess":
        return 0.82
    if source == "aerialWonPerGame":
        return 12.5
    if source == "shotsConcededPerGame":
        return 8.0
    if source == "tacklePerGame":
        return 4.2
    if source == "interceptionPerGame":
        return 2.0
    if source == "foulsPerGame":
        return 3.0
    if source == "offsideGivenPerGame":
        return 1.0
    if source == "shotOnTargetPerGame":
        return 5.0
    if source == "dribbleWonPerGame":
        return 3.0
    if source == "foulGivenPerGame":
        return 2.0
    raise AssertionError(f"unexpected source column: {source}")


def _body(
    section: Section,
    view: View,
    teams: list[int],
    *,
    overrides: dict[int, dict[str, object]] | None = None,
    omit: set[str] | None = None,
) -> bytes:
    rows: list[dict[str, Any]] = []
    for rank, team_id in enumerate(teams, start=1):
        name = f"Team {team_id}"
        row: dict[str, Any] = {
            "name": name,
            "teamId": team_id,
            "teamName": name,
            "tournamentId": _SPEC.whoscored_tournament_id,
            "isOpta": True,
            "rating": 6.0 + team_id / 100.0,
            "ranking": rank,
        }
        for source in EXPECTED_STAT_COLUMNS[(section, view)]:
            if omit and source in omit:
                continue
            row[source] = _source_value(source, team_id)
        if overrides and team_id in overrides:
            row.update(overrides[team_id])
        rows.append(row)

    payload = {
        "teamTableStats": rows,
        "paging": {},
        "statColumns": list(EXPECTED_STAT_COLUMNS[(section, view)]),
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _captures(
    *,
    teams: list[int] | None = None,
    overrides: dict[int, dict[str, object]] | None = None,
    omit: set[str] | None = None,
) -> list[Capture]:
    selected = _TEAMS if teams is None else teams
    return [
        Capture(
            section=section,
            view=view,
            body=_body(section, view, selected, overrides=overrides, omit=omit),
            captured_at=_NOW,
            content_type="text/html",
            url=f"https://www.whoscored.com/feed?section={section}&view={view}",
        )
        for section in SECTIONS
        for view in VIEWS
    ]


def test_parses_a_golden_twenty_team_candidate() -> None:
    candidate = build_candidate(_captures(), _SPEC)

    assert len(candidate.rows) == 20
    assert candidate.whoscored_tournament_id == _SPEC.whoscored_tournament_id
    assert candidate.is_opta is True
    assert [row.whoscored_team_id for row in candidate.rows] == _TEAMS
    assert all(set(row.measures) == set(MEASURE_COLUMNS) for row in candidate.rows)
    assert candidate.rows[0].measures["summary_overall_goal"] == 100.0
    assert candidate.rows[0].measures["apps_overall"] == 7
    assert candidate.rows[0].measures["ranking_offensive_away"] == 1


def test_missing_measure_is_none_not_zero() -> None:
    candidate = build_candidate(_captures(omit={"aerialWonPerGame"}), _SPEC)

    assert candidate.rows[0].measures["summary_overall_aerial_won_per_game"] is None


def test_changed_stat_columns_raise_schema_drift() -> None:
    body = _body("summary", "overall", _TEAMS)
    payload = json.loads(body)
    payload["statColumns"] = ["apps"]
    changed = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    with pytest.raises(SchemaDrift):
        parse_capture("summary", "overall", changed)


def test_nineteen_team_cohort_is_incomplete() -> None:
    with pytest.raises(IncompleteCohort, match="expected 20"):
        build_candidate(_captures(teams=_TEAMS[:19]), _SPEC)


def test_team_set_difference_is_incomplete() -> None:
    captures = _captures()
    captures[0] = Capture(
        section="summary",
        view="overall",
        body=_body("summary", "overall", _TEAMS[:19]),
        captured_at=_NOW,
        content_type="text/html",
        url="https://www.whoscored.com/feed",
    )

    with pytest.raises(IncompleteCohort, match="team-id set"):
        build_candidate(captures, _SPEC)


def test_shared_measure_must_agree_across_sections() -> None:
    captures = _captures()
    captures = [
        Capture(
            section=capture.section,
            view=capture.view,
            body=_body(
                capture.section,
                capture.view,
                _TEAMS,
                overrides={100: {"shotsPerGame": 99.0}},
            ),
            captured_at=capture.captured_at,
            content_type=capture.content_type,
            url=capture.url,
        )
        if (capture.section, capture.view) == ("offensive", "overall")
        else capture
        for capture in captures
    ]

    with pytest.raises(OwnershipMismatch, match="shots_per_game_overall"):
        build_candidate(captures, _SPEC)


def test_name_and_team_name_must_agree() -> None:
    captures = _captures(overrides={100: {"name": "Different"}})
    with pytest.raises(SourceParseError, match="name and teamName"):
        build_candidate(captures, _SPEC)


def test_parse_capture_preserves_source_ids() -> None:
    rows = parse_capture(
        "summary",
        "overall",
        _body("summary", "overall", _TEAMS),
    )

    assert rows[0].whoscored_team_id == 100
    assert rows[0].whoscored_team_name == "Team 100"
    assert rows[0].whoscored_tournament_id == 2
    assert rows[0].measures["apps_overall"] == 7
    assert rows[0].measures["summary_overall_possession"] == 0.55


def test_duplicate_capture_is_rejected() -> None:
    captures = _captures()
    captures[-1] = captures[0]

    with pytest.raises(IncompleteCohort, match="duplicate capture"):
        build_candidate(captures, _SPEC)
