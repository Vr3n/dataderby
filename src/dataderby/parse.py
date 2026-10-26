"""Pure parsing of the nine WhoScored feed payloads into a candidate."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from dataderby.config import StageSpec
from dataderby.contract import (
    EXPECTED_STAT_COLUMNS,
    MEASURE_COLUMNS,
    OWNERSHIP,
    SECTIONS,
    VIEWS,
    WHOSCORED_TO_WAREHOUSE,
    Section,
    View,
)
from dataderby.fetch import Capture, parse_envelope

Measure = float | int | None


class SourceParseError(ValueError):
    """Raised when one feed row does not match the expected shape."""


class IncompleteCohort(ValueError):
    """Raised when the nine captures do not form a complete team cohort."""


class OwnershipMismatch(ValueError):
    """Raised when a shared measure disagrees across sections."""


@dataclass(frozen=True, slots=True)
class SourceRow:
    """One team row from one feed capture."""

    section: Section
    view: View
    whoscored_team_id: int
    whoscored_team_name: str
    whoscored_tournament_id: int
    is_opta: bool
    measures: dict[str, Measure]


@dataclass(frozen=True, slots=True)
class TeamRow:
    """One team's complete 60-measure candidate row."""

    whoscored_team_id: int
    whoscored_team_name: str
    measures: dict[str, Measure]


@dataclass(frozen=True, slots=True)
class Candidate:
    """A complete candidate for one stage, before publication."""

    whoscored_tournament_id: int
    is_opta: bool
    rows: tuple[TeamRow, ...]


def _as_int(value: Any, field: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise SourceParseError(f"invalid {field}: {value!r}") from exc


def _as_float(value: Any, field: str) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SourceParseError(f"invalid {field}: {value!r}") from exc
    if not math.isfinite(number):
        raise SourceParseError(f"non-finite {field}: {value!r}")
    return number


def _measure_column(section: Section, view: View, source: str) -> str:
    base = WHOSCORED_TO_WAREHOUSE[source]
    if base in OWNERSHIP:
        return f"{base}_{view}"
    return f"{section}_{view}_{base}"


def parse_capture(section: Section, view: View, body: bytes) -> list[SourceRow]:
    """Parse one accepted feed payload into source rows.

    Args:
        section: Feed section.
        view: Feed split.
        body: Raw JSON body, with or without a UTF-8 BOM.

    Returns:
        One row per ``teamTableStats`` entry. A missing measure is ``None``.

    Raises:
        SchemaDrift: If the envelope's ``statColumns`` changed.
        GatePage: If the body is not the expected envelope.
        SourceParseError: If a row lacks an identity field or has a bad value.
    """
    if section not in SECTIONS:
        raise ValueError(f"unknown section: {section}")
    if view not in VIEWS:
        raise ValueError(f"unknown view: {view}")

    payload = parse_envelope(body, section, view)
    rows: list[SourceRow] = []
    expected_sources = EXPECTED_STAT_COLUMNS[(section, view)]

    for item in payload["teamTableStats"]:
        if not isinstance(item, dict):
            raise SourceParseError("teamTableStats entry is not an object")
        if "teamId" not in item or "teamName" not in item:
            raise SourceParseError("row is missing teamId or teamName")
        if "tournamentId" not in item or "isOpta" not in item:
            raise SourceParseError("row is missing tournamentId or isOpta")

        team_id = _as_int(item["teamId"], "teamId")
        if team_id is None or team_id <= 0:
            raise SourceParseError(f"invalid teamId: {item['teamId']!r}")
        # ``name`` is the short label ("Man City"); ``teamName`` is the full
        # name ("Manchester City") and matches the standings table. The full
        # name is the warehouse key, so the short label is not compared.
        team_name = item["teamName"]
        if not isinstance(team_name, str) or not team_name.strip():
            raise SourceParseError(f"invalid teamName: {team_name!r}")
        tournament_id = _as_int(item["tournamentId"], "tournamentId")
        if tournament_id is None or tournament_id <= 0:
            raise SourceParseError(f"invalid tournamentId: {item['tournamentId']!r}")

        measures: dict[str, Measure] = {}
        for source in expected_sources:
            column = _measure_column(section, view, source)
            if source == "apps":
                measures[column] = _as_int(item.get(source), source)
            else:
                measures[column] = _as_float(item.get(source), source)

        measures[f"rating_{view}"] = _as_float(item.get("rating"), "rating")
        measures[f"ranking_{section}_{view}"] = _as_int(item.get("ranking"), "ranking")

        rows.append(
            SourceRow(
                section=section,
                view=view,
                whoscored_team_id=team_id,
                whoscored_team_name=team_name.strip(),
                whoscored_tournament_id=tournament_id,
                is_opta=bool(item["isOpta"]),
                measures=measures,
            )
        )

    return rows


def _shared_columns() -> set[str]:
    return {f"{base}_{view}" for base in OWNERSHIP for view in VIEWS}


def build_candidate(captures: list[Capture], spec: StageSpec) -> Candidate:
    """Join the nine captures into 60-measure team rows.

    Args:
        captures: Exactly nine accepted captures, one per section/view.
        spec: Stage configuration, including the expected team count.

    Returns:
        A candidate sorted by ``whoscored_team_id``.

    Raises:
        IncompleteCohort: If captures are missing/duplicate, team sets differ,
            metadata is inconsistent, or the count is not ``expected_teams``.
        OwnershipMismatch: If a shared measure differs across sections.
        SourceParseError: If a payload row is malformed.
    """
    expected_keys = {(section, view) for section in SECTIONS for view in VIEWS}
    if len(captures) != len(expected_keys):
        raise IncompleteCohort("expected exactly nine feed captures")

    by_key: dict[tuple[Section, View], Capture] = {}
    for capture in captures:
        key = (capture.section, capture.view)
        if key not in expected_keys:
            raise IncompleteCohort(f"unexpected capture: {key}")
        if key in by_key:
            raise IncompleteCohort(f"duplicate capture: {key}")
        by_key[key] = capture
    if set(by_key) != expected_keys:
        raise IncompleteCohort("missing a section/view capture")

    parsed = {key: parse_capture(key[0], key[1], capture.body) for key, capture in by_key.items()}
    team_sets = {key: {row.whoscored_team_id for row in rows} for key, rows in parsed.items()}
    first_set = team_sets[next(iter(expected_keys))]
    if any(team_set != first_set for team_set in team_sets.values()):
        raise IncompleteCohort("team-id set differs across feed captures")
    if len(first_set) != spec.expected_teams:
        raise IncompleteCohort(f"expected {spec.expected_teams} teams, found {len(first_set)}")

    by_team = {key: {row.whoscored_team_id: row for row in rows} for key, rows in parsed.items()}
    all_rows = [row for rows in parsed.values() for row in rows]
    tournament_ids = {row.whoscored_tournament_id for row in all_rows}
    optas = {row.is_opta for row in all_rows}
    if len(tournament_ids) != 1:
        raise IncompleteCohort("tournamentId differs across feed captures")
    if len(optas) != 1:
        raise IncompleteCohort("isOpta differs across feed captures")

    names: dict[int, set[str]] = {}
    for row in all_rows:
        names.setdefault(row.whoscored_team_id, set()).add(row.whoscored_team_name)
    if any(len(team_names) != 1 for team_names in names.values()):
        raise IncompleteCohort("team name differs across feed captures")

    shared = _shared_columns()
    teams: list[TeamRow] = []
    for team_id in sorted(first_set):
        measures: dict[str, Measure] = dict.fromkeys(MEASURE_COLUMNS)
        for view in VIEWS:
            summary_row = by_team[("summary", view)][team_id]
            for base in OWNERSHIP:
                column = f"{base}_{view}"
                owner_value = summary_row.measures.get(column)
                for section in SECTIONS:
                    section_row = by_team[(section, view)][team_id]
                    if column not in section_row.measures:
                        continue
                    value = section_row.measures[column]
                    if value != owner_value:
                        raise OwnershipMismatch(
                            f"{column} disagrees for team {team_id}: "
                            f"summary={owner_value!r}, {section}={value!r}"
                        )
                measures[column] = owner_value

            for section in SECTIONS:
                for column, value in by_team[(section, view)][team_id].measures.items():
                    if column not in shared:
                        measures[column] = value

        missing = [column for column in MEASURE_COLUMNS if column not in measures]
        if missing:
            raise SourceParseError(f"candidate is missing columns: {missing}")
        teams.append(
            TeamRow(
                whoscored_team_id=team_id,
                whoscored_team_name=next(iter(names[team_id])),
                measures=measures,
            )
        )

    return Candidate(
        whoscored_tournament_id=next(iter(tournament_ids)),
        is_opta=next(iter(optas)),
        rows=tuple(teams),
    )
