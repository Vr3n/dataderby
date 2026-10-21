"""The source and warehouse contract for WhoScored team statistics.

This module is the single place where the 60 fact columns, the 30 standings
measures, and the source's expected ``statColumns`` order are declared. The
schema and parser must import these names rather than repeating them.
"""

from __future__ import annotations

from typing import Literal

Section = Literal["summary", "defensive", "offensive"]
View = Literal["overall", "home", "away"]

SECTIONS: tuple[Section, ...] = ("summary", "defensive", "offensive")
VIEWS: tuple[View, ...] = ("overall", "home", "away")

# WhoScored calls the summary section "all" in the feed.
SECTION_SUBCATEGORY: dict[Section, str] = {
    "summary": "all",
    "defensive": "defensive",
    "offensive": "offensive",
}

_SUMMARY_STAT_COLUMNS: tuple[str, ...] = (
    "apps",
    "goal",
    "shotsPerGame",
    "yellowCard",
    "redCard",
    "possession",
    "passSuccess",
    "aerialWonPerGame",
)
_DEFENSIVE_STAT_COLUMNS: tuple[str, ...] = (
    "apps",
    "shotsConcededPerGame",
    "tacklePerGame",
    "interceptionPerGame",
    "foulsPerGame",
    "offsideGivenPerGame",
)
_OFFENSIVE_STAT_COLUMNS: tuple[str, ...] = (
    "apps",
    "shotsPerGame",
    "shotOnTargetPerGame",
    "dribbleWonPerGame",
    "foulGivenPerGame",
)

_STAT_COLUMNS: dict[Section, tuple[str, ...]] = {
    "summary": _SUMMARY_STAT_COLUMNS,
    "defensive": _DEFENSIVE_STAT_COLUMNS,
    "offensive": _OFFENSIVE_STAT_COLUMNS,
}

# Measured on all twelve 2026/27 stages: the list is the same for every split.
EXPECTED_STAT_COLUMNS: dict[tuple[Section, View], tuple[str, ...]] = {
    (section, view): _STAT_COLUMNS[section] for section in SECTIONS for view in VIEWS
}

# Source field names to warehouse base names. The view and section prefixes are
# applied by _measure_columns().
WHOSCORED_TO_WAREHOUSE: dict[str, str] = {
    "apps": "apps",
    "rating": "rating",
    "ranking": "ranking",
    "goal": "goal",
    "yellowCard": "yellow_card",
    "redCard": "red_card",
    "shotsPerGame": "shots_per_game",
    "possession": "possession",
    "passSuccess": "pass_success",
    "aerialWonPerGame": "aerial_won_per_game",
    "shotsConcededPerGame": "shots_conceded",
    "tacklePerGame": "tackles",
    "interceptionPerGame": "interceptions",
    "foulsPerGame": "fouls",
    "offsideGivenPerGame": "offsides",
    "shotOnTargetPerGame": "shots_on_target",
    "dribbleWonPerGame": "dribbles_won",
    "foulGivenPerGame": "fouls_given",
}

# These three source values repeat across sections. One section supplies each;
# the parser reads it once and writes one column per view.
OWNERSHIP: dict[str, str] = {
    "apps": "summary",
    "shots_per_game": "summary",
    "rating": "summary",
}

_SUMMARY_FIELDS: tuple[str, ...] = (
    "goal",
    "yellow_card",
    "red_card",
    "possession",
    "pass_success",
    "aerial_won_per_game",
)
_DEFENSIVE_FIELDS: tuple[str, ...] = (
    "shots_conceded",
    "tackles",
    "interceptions",
    "fouls",
    "offsides",
)
_OFFENSIVE_FIELDS: tuple[str, ...] = (
    "shots_on_target",
    "dribbles_won",
    "fouls_given",
)


def _measure_columns() -> tuple[str, ...]:
    """Build the 60 warehouse columns in schema order."""
    columns: list[str] = []
    for view in VIEWS:
        columns.append(f"apps_{view}")
        columns.append(f"rating_{view}")
        columns.append(f"shots_per_game_{view}")
        columns.extend(f"summary_{view}_{field}" for field in _SUMMARY_FIELDS)
        columns.extend(f"defensive_{view}_{field}" for field in _DEFENSIVE_FIELDS)
        columns.extend(f"offensive_{view}_{field}" for field in _OFFENSIVE_FIELDS)
    for section in SECTIONS:
        columns.extend(f"ranking_{section}_{view}" for view in VIEWS)
    return tuple(columns)


MEASURE_COLUMNS: tuple[str, ...] = _measure_columns()
_MEASURE_COLUMN_SET = frozenset(MEASURE_COLUMNS)

_STANDINGS_FIELDS: tuple[str, ...] = (
    "rank",
    "played",
    "won",
    "drawn",
    "lost",
    "goals_for",
    "goals_against",
    "goal_difference",
    "points",
    "form",
)

STANDINGS_MEASURES: tuple[str, ...] = tuple(
    f"{field}_{view}" for view in VIEWS for field in _STANDINGS_FIELDS
)


def measure_owner(column: str) -> str:
    """Return the section or shared block that owns one fact column.

    Args:
        column: A warehouse measure column such as ``summary_overall_goal``.

    Returns:
        ``summary``, ``defensive``, ``offensive``, ``ranking``, or ``shared``.

    Raises:
        KeyError: If ``column`` is not one of :data:`MEASURE_COLUMNS`.
    """
    if column not in _MEASURE_COLUMN_SET:
        raise KeyError(f"unknown measure column: {column}")

    if column in OWNERSHIP or any(column.startswith(f"{base}_") for base in OWNERSHIP):
        return "shared"

    return column.partition("_")[0]
