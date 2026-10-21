"""Contract tests for the 60 fact columns and 30 standings measures."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import cast

import pytest

from dataderby.contract import (
    EXPECTED_STAT_COLUMNS,
    MEASURE_COLUMNS,
    OWNERSHIP,
    SECTION_SUBCATEGORY,
    SECTIONS,
    STANDINGS_MEASURES,
    VIEWS,
    WHOSCORED_TO_WAREHOUSE,
    measure_owner,
)

_GOLDEN = Path(__file__).parent / "golden" / "stat_columns.json"


def _golden_captures() -> dict[str, list[str]]:
    raw = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    return cast(dict[str, list[str]], raw["captures"])


def test_measure_columns_are_60_unique_columns() -> None:
    assert len(MEASURE_COLUMNS) == 60
    assert len(set(MEASURE_COLUMNS)) == 60


def test_expected_columns_match_nine_golden_captures() -> None:
    captures = _golden_captures()
    expected_keys = {
        f"{SECTION_SUBCATEGORY[section]}__{view.title()}" for section in SECTIONS for view in VIEWS
    }
    assert len(captures) == 9
    assert set(captures) == expected_keys

    for (section, view), columns in EXPECTED_STAT_COLUMNS.items():
        capture_key = f"{SECTION_SUBCATEGORY[section]}__{view.title()}"
        assert columns == tuple(captures[capture_key])


def test_every_measure_has_exactly_one_owner() -> None:
    owners = {column: measure_owner(column) for column in MEASURE_COLUMNS}

    assert set(owners) == set(MEASURE_COLUMNS)
    counts = Counter(owners.values())
    assert counts["summary"] == 18
    assert counts["defensive"] == 15
    assert counts["offensive"] == 9
    assert counts["ranking"] == 9
    assert counts["shared"] == 9


def test_ownership_covers_only_the_shared_measures() -> None:
    assert set(OWNERSHIP) == {"apps", "shots_per_game", "rating"}
    assert all(owner in SECTIONS for owner in OWNERSHIP.values())

    for base in OWNERSHIP:
        for view in VIEWS:
            assert measure_owner(f"{base}_{view}") == "shared"


def test_standings_measures_are_30_unique_measures() -> None:
    assert len(STANDINGS_MEASURES) == 30
    assert len(set(STANDINGS_MEASURES)) == 30
    assert STANDINGS_MEASURES[:10] == (
        "rank_overall",
        "played_overall",
        "won_overall",
        "drawn_overall",
        "lost_overall",
        "goals_for_overall",
        "goals_against_overall",
        "goal_difference_overall",
        "points_overall",
        "form_overall",
    )


def test_contract_arithmetic_counts_the_60_columns() -> None:
    stat_entries = sum(len(columns) for columns in EXPECTED_STAT_COLUMNS.values())
    assert stat_entries == 57

    # apps appears in all three sections (two duplicates per view); shotsPerGame
    # appears in summary and offensive (one duplicate per view).
    duplicate_apps = 2 * len(VIEWS)
    duplicate_shots = 1 * len(VIEWS)
    unique_stat_columns = stat_entries - duplicate_apps - duplicate_shots
    assert unique_stat_columns == 48
    assert unique_stat_columns == 42 + 3 + 3

    assert unique_stat_columns + 3 + 9 == 60
    assert len(MEASURE_COLUMNS) == 60


def test_every_source_stat_column_has_a_warehouse_name() -> None:
    for columns in EXPECTED_STAT_COLUMNS.values():
        assert set(columns) <= set(WHOSCORED_TO_WAREHOUSE)

    assert WHOSCORED_TO_WAREHOUSE["shotsConcededPerGame"] == "shots_conceded"
    assert WHOSCORED_TO_WAREHOUSE["shotOnTargetPerGame"] == "shots_on_target"
    assert WHOSCORED_TO_WAREHOUSE["dribbleWonPerGame"] == "dribbles_won"
    assert WHOSCORED_TO_WAREHOUSE["foulGivenPerGame"] == "fouls_given"


def test_unknown_measure_is_rejected() -> None:
    with pytest.raises(KeyError, match="unknown measure column"):
        measure_owner("summary_overall_not_a_measure")
