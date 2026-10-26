"""Stage registry tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from dataderby.config import load_settings, load_stages

_STAGE = """[[stage]]
key = "epl-2026-2027"
whoscored_tournament_id = 2
whoscored_season_id = 11141
whoscored_stage_id = 25544
season_key = "2026-2027"
competition = "Premier League"
stage = "league"
expected_stages = ["league"]
expected_teams = 20
whoscored_page_url = "https://www.whoscored.com/regions/252/tournaments/2/seasons/11141/stages/25544/show/england-premier-league-2026-2027"
has_league_table = true
"""

_URL = (
    "https://www.whoscored.com/regions/252/tournaments/2/seasons/11141/"
    "stages/25544/show/england-premier-league-2026-2027"
)


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "stages.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_loads_a_valid_stage(tmp_path: Path) -> None:
    stages = load_stages(_write(tmp_path, _STAGE))

    assert list(stages) == ["epl-2026-2027"]
    assert stages["epl-2026-2027"].expected_teams == 20


def test_missing_field_names_the_field(tmp_path: Path) -> None:
    body = _STAGE.replace("expected_teams = 20\n", "")

    with pytest.raises(ValidationError, match="expected_teams"):
        load_stages(_write(tmp_path, body))


def test_unknown_stage_field_is_rejected(tmp_path: Path) -> None:
    body = _STAGE.replace("has_league_table = true", "bogus = 1\nhas_league_table = true")

    with pytest.raises(ValidationError, match="bogus"):
        load_stages(_write(tmp_path, body))


def test_duplicate_stage_id_is_rejected(tmp_path: Path) -> None:
    second = _STAGE.replace('key = "epl-2026-2027"', 'key = "epl-copy-2026-2027"')

    with pytest.raises(ValueError, match="duplicate whoscored_stage_id"):
        load_stages(_write(tmp_path, _STAGE + second))


def test_duplicate_key_is_rejected(tmp_path: Path) -> None:
    second = _STAGE.replace("whoscored_stage_id = 25544", "whoscored_stage_id = 99999")

    with pytest.raises(ValueError, match="duplicate stage key"):
        load_stages(_write(tmp_path, _STAGE + second))


def test_expected_stages_must_agree_within_a_season(tmp_path: Path) -> None:
    second = (
        _STAGE.replace('key = "epl-2026-2027"', 'key = "epl-knockout-2026-2027"')
        .replace("whoscored_stage_id = 25544", "whoscored_stage_id = 99999")
        .replace('stage = "league"', 'stage = "knockout"')
        .replace('expected_stages = ["league"]', 'expected_stages = ["league", "knockout"]')
    )

    with pytest.raises(ValueError, match="expected_stages disagree"):
        load_stages(_write(tmp_path, _STAGE + second))


def test_stage_must_be_in_expected_stages(tmp_path: Path) -> None:
    body = _STAGE.replace('stage = "league"', 'stage = "playoff"')

    with pytest.raises(ValidationError, match="not listed in expected_stages"):
        load_stages(_write(tmp_path, body))


def test_url_must_be_a_whoscored_page(tmp_path: Path) -> None:
    body = _STAGE.replace(_URL, "https://example.com/not-whoscored")

    with pytest.raises(ValidationError, match="whoscored_page_url"):
        load_stages(_write(tmp_path, body))


def test_settings_paths_are_loaded(tmp_path: Path) -> None:
    body = f"""[settings]
db_path = "var/test.duckdb"
raw_dir = "var/raw"
log_dir = "var/logs"

{_STAGE}"""

    settings = load_settings(_write(tmp_path, body))

    assert settings.db_path == Path("var/test.duckdb")
    assert settings.raw_dir == Path("var/raw")
    assert settings.log_dir == Path("var/logs")
    assert set(settings.stages) == {"epl-2026-2027"}


def test_repository_stage_registry_loads() -> None:
    settings = load_settings(Path("config/stages.toml"))

    assert len(settings.stages) == 12
    assert settings.stages["la-liga-2026-2027"].expected_teams == 20
    # Live page on 2026-10-26 shows 36 teams; the feed is empty (see
    # docs/reports/all-league-capture.md).
    assert settings.stages["conference-league-2026-2027"].expected_teams == 36
    assert all(spec.stage in spec.expected_stages for spec in settings.stages.values())
    assert len({spec.whoscored_stage_id for spec in settings.stages.values()}) == 12
