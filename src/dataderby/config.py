"""Validated configuration for the WhoScored team-statistics pipeline."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

StageCode = Literal["league", "group", "qualification", "knockout", "playoff", "final"]

_WHOSCORED_PREFIX = "https://www.whoscored.com/"


class StageSpec(BaseModel):
    """One configured WhoScored stage.

    Attributes:
        key: Stable local key used by the CLI and logs.
        whoscored_tournament_id: WhoScored tournament id.
        whoscored_season_id: WhoScored season id.
        whoscored_stage_id: WhoScored stage id; the feed's identity.
        season_key: Human-readable season label.
        competition: Human-readable competition name.
        stage: Curated domain stage code.
        expected_stages: Stage codes the season is expected to publish.
        expected_teams: Number of teams the feed must return for this stage.
        whoscored_page_url: The show page used to mint the feed token.
        has_league_table: Whether the stage has a standings table.
        active: Whether scheduled runs include this stage. Archived seasons set
            this to false so polling skips them while explicit runs still work.
        whoscored_stage_name: Verbatim source label, when one was observed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    whoscored_tournament_id: int = Field(gt=0)
    whoscored_season_id: int = Field(gt=0)
    whoscored_stage_id: int = Field(gt=0)
    season_key: str = Field(pattern=r"^\d{4}-\d{4}$")
    competition: str = Field(min_length=1)
    stage: StageCode
    expected_stages: tuple[StageCode, ...] = Field(min_length=1)
    expected_teams: int = Field(gt=0)
    whoscored_page_url: str
    has_league_table: bool
    active: bool = True
    whoscored_stage_name: str | None = None

    @field_validator("whoscored_page_url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        """Require a WhoScored show URL rather than an arbitrary URL."""
        if not value.startswith(_WHOSCORED_PREFIX):
            raise ValueError(f"whoscored_page_url must start with {_WHOSCORED_PREFIX}")
        return value

    @model_validator(mode="after")
    def _stage_is_expected(self) -> Self:
        """Require the configured stage code to be in the season's expected list."""
        if self.stage not in self.expected_stages:
            raise ValueError(f"stage {self.stage!r} is not listed in expected_stages")
        return self


class Settings(BaseModel):
    """Runtime paths and the loaded stage registry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    db_path: Path = Path("data/dataderby.duckdb")
    raw_dir: Path = Path("data/raw")
    log_dir: Path = Path("data/logs")
    stages: dict[str, StageSpec] = Field(default_factory=dict)


def _parse_stages(data: dict[str, Any]) -> dict[str, StageSpec]:
    """Validate the ``[[stage]]`` entries and reject ambiguous addresses."""
    raw_stages = data.get("stage", [])
    if not isinstance(raw_stages, list):
        raise ValueError("'stage' must be an array of tables")

    stages = [StageSpec.model_validate(item) for item in raw_stages]
    by_key: dict[str, StageSpec] = {}
    seen_ids: set[int] = set()
    addresses: set[tuple[int, int, int]] = set()
    expected_by_season: dict[tuple[int, int], tuple[StageCode, ...]] = {}

    for spec in stages:
        if spec.key in by_key:
            raise ValueError(f"duplicate stage key: {spec.key}")
        if spec.whoscored_stage_id in seen_ids:
            raise ValueError(f"duplicate whoscored_stage_id: {spec.whoscored_stage_id}")

        address = (
            spec.whoscored_tournament_id,
            spec.whoscored_season_id,
            spec.whoscored_stage_id,
        )
        if address in addresses:
            raise ValueError(f"duplicate stage address: {address}")

        season = (spec.whoscored_tournament_id, spec.whoscored_season_id)
        expected = expected_by_season.setdefault(season, spec.expected_stages)
        if expected != spec.expected_stages:
            raise ValueError(f"expected_stages disagree for season {season}")

        by_key[spec.key] = spec
        seen_ids.add(spec.whoscored_stage_id)
        addresses.add(address)

    return by_key


def load_stages(path: Path) -> dict[str, StageSpec]:
    """Load and validate the stage registry.

    Args:
        path: TOML file containing one or more ``[[stage]]`` entries.

    Returns:
        Stage specifications keyed by their local ``key``.

    Raises:
        ValueError: If an address, key, stage id, or expected-stage list is
            duplicated or inconsistent.
        pydantic.ValidationError: If a field is missing, unknown, or invalid.
    """
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return _parse_stages(data)


def load_settings(path: Path) -> Settings:
    """Load runtime paths and the stage registry from one TOML file.

    Args:
        path: TOML file containing optional ``[settings]`` and required
            ``[[stage]]`` entries.

    Returns:
        Validated settings with stages keyed by their local ``key``.

    Raises:
        ValueError: If the registry is ambiguous or the settings table has the
            wrong shape.
        pydantic.ValidationError: If a settings or stage field is invalid.
    """
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    raw_settings = data.get("settings", {})
    if not isinstance(raw_settings, dict):
        raise ValueError("'settings' must be a table")

    stages = _parse_stages(data)
    return Settings.model_validate({**raw_settings, "stages": stages})
