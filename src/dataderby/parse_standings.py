"""Canonical standings views and their feed-team check."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from dataderby.config import StageSpec
from dataderby.contract import STANDINGS_MEASURES, VIEWS, View
from dataderby.page import PageCapture
from dataderby.parse import Candidate, IncompleteCohort
from dataderby.standings import StandingsParseError, StandingsRow, parse_standings

StandingValue = int | str | None


@dataclass(frozen=True, slots=True)
class StandingsTeamRow:
    """One team's 30 standings measures across three splits."""

    whoscored_team_id: int
    whoscored_team_name: str
    measures: dict[str, StandingValue]


@dataclass(frozen=True, slots=True)
class StandingsCandidate:
    """The standings companion to one candidate; empty for no-table stages."""

    rows: tuple[StandingsTeamRow, ...]


def parse_views(page: PageCapture, spec: StageSpec | None = None) -> StandingsCandidate:
    """Build one standings row per team from the captured page.

    Args:
        page: Captured page with zero or three standings views.
        spec: Optional stage config. A stage declared without a league table
            always produces zero rows, even if a table leaked onto the page.

    Returns:
        Standings rows sorted by ``whoscored_team_id``. An empty tuple means the
        stage has no league table.

    Raises:
        StandingsParseError: If a view is malformed, a team repeats, or the
            three views disagree about team identity.
        IncompleteCohort: If the stage declares a table but none was captured.
    """
    if spec is not None and not spec.has_league_table:
        return StandingsCandidate(rows=())

    parsed = parse_standings(page)
    if not parsed:
        if spec is not None and spec.has_league_table:
            raise IncompleteCohort("stage declares a league table but none was captured")
        return StandingsCandidate(rows=())

    by_team: dict[int, dict[View, StandingsRow]] = {}
    names: dict[int, str] = {}
    for view in VIEWS:
        for row in parsed[view]:
            if row.whoscored_team_id in by_team and view in by_team[row.whoscored_team_id]:
                raise StandingsParseError(
                    f"duplicate standings row: {row.whoscored_team_id}/{view}"
                )
            by_team.setdefault(row.whoscored_team_id, {})[view] = row
            existing_name = names.setdefault(row.whoscored_team_id, row.whoscored_team_name)
            if existing_name != row.whoscored_team_name:
                raise StandingsParseError(
                    f"team name differs across splits: {row.whoscored_team_id}"
                )

    if any(set(views) != set(VIEWS) for views in by_team.values()):
        raise StandingsParseError("each standings team must appear in all three splits")

    rows: list[StandingsTeamRow] = []
    for team_id in sorted(by_team):
        views = by_team[team_id]
        measures: dict[str, StandingValue] = {}
        for measure in STANDINGS_MEASURES:
            field, _, view_suffix = measure.rpartition("_")
            measure_view = cast(View, view_suffix)
            row = views[measure_view]
            value = getattr(row, field)
            measures[measure] = value
        rows.append(
            StandingsTeamRow(
                whoscored_team_id=team_id,
                whoscored_team_name=names[team_id],
                measures=measures,
            )
        )
    return StandingsCandidate(rows=tuple(rows))


def check_team_sets(candidate: Candidate, standings: StandingsCandidate) -> None:
    """Require the standings team set to equal the feed team set.

    Args:
        candidate: Parsed feed candidate.
        standings: Parsed standings candidate.

    Raises:
        IncompleteCohort: If either side is empty or the sets differ.
    """
    feed_ids = {row.whoscored_team_id for row in candidate.rows}
    standing_ids = {row.whoscored_team_id for row in standings.rows}
    if not standing_ids:
        raise IncompleteCohort("no standings rows to compare with the feed")
    if feed_ids != standing_ids:
        raise IncompleteCohort(
            f"standings team set differs from feed: "
            f"feed_only={sorted(feed_ids - standing_ids)}, "
            f"standings_only={sorted(standing_ids - feed_ids)}"
        )
