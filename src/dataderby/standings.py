"""Standings tables parsed from the captured stage page."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from dataderby.contract import VIEWS, View

if TYPE_CHECKING:
    from dataderby.page import PageCapture

_FORM_CHARS = frozenset("wdl")


class StandingsParseError(ValueError):
    """Raised when a standings view does not match the expected shape."""


@dataclass(frozen=True, slots=True)
class RawStandingsRow:
    """One ``tr[data-team-id]`` row before numeric conversion."""

    whoscored_team_id: int
    whoscored_team_name: str
    rank: str
    played: str
    won: str
    drawn: str
    lost: str
    goals_for: str
    goals_against: str
    goal_difference: str
    points: str
    form: str


@dataclass(frozen=True, slots=True)
class StandingsRow:
    """One team's standings values for one split."""

    whoscored_team_id: int
    whoscored_team_name: str
    rank: int
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    form: str | None


def _as_int(value: str, field: str) -> int:
    try:
        return int(value.strip())
    except (TypeError, ValueError) as exc:
        raise StandingsParseError(f"invalid {field}: {value!r}") from exc


def _validate_form(form: str | None, played: int) -> None:
    if played == 0:
        if form is not None:
            raise StandingsParseError("form must be null when played is zero")
        return
    if form is None:
        raise StandingsParseError("form is required when played is positive")
    if len(form) != min(played, 6):
        raise StandingsParseError(f"form length {len(form)} does not match played {played}")
    if any(char not in _FORM_CHARS for char in form):
        raise StandingsParseError(f"form contains a non-w/d/l character: {form!r}")


def parse_view(view: View, rows: tuple[RawStandingsRow, ...]) -> tuple[StandingsRow, ...]:
    """Convert one view's raw rows into validated standings rows.

    Args:
        view: ``overall``, ``home``, or ``away``.
        rows: Rows extracted from ``tr[data-team-id]``.

    Returns:
        Validated rows in the order supplied by the page.

    Raises:
        StandingsParseError: If a value is malformed or a team repeats.
    """
    if view not in VIEWS:
        raise ValueError(f"unknown standings view: {view}")

    parsed: list[StandingsRow] = []
    seen_ids: set[int] = set()

    for raw in rows:
        if raw.whoscored_team_id <= 0:
            raise StandingsParseError(f"invalid whoscored_team_id: {raw.whoscored_team_id}")
        if raw.whoscored_team_id in seen_ids:
            raise StandingsParseError(f"duplicate whoscored_team_id: {raw.whoscored_team_id}")
        if not raw.whoscored_team_name.strip():
            raise StandingsParseError("whoscored_team_name is empty")

        played = _as_int(raw.played, "played")
        form = raw.form.strip() or None
        _validate_form(form, played)

        row = StandingsRow(
            whoscored_team_id=raw.whoscored_team_id,
            whoscored_team_name=raw.whoscored_team_name.strip(),
            rank=_as_int(raw.rank, "rank"),
            played=played,
            won=_as_int(raw.won, "won"),
            drawn=_as_int(raw.drawn, "drawn"),
            lost=_as_int(raw.lost, "lost"),
            goals_for=_as_int(raw.goals_for, "goals_for"),
            goals_against=_as_int(raw.goals_against, "goals_against"),
            goal_difference=_as_int(raw.goal_difference, "goal_difference"),
            points=_as_int(raw.points, "points"),
            form=form,
        )
        if not 1 <= row.rank <= len(rows):
            raise StandingsParseError(f"rank out of range for {row.whoscored_team_id}: {row.rank}")
        parsed.append(row)
        seen_ids.add(row.whoscored_team_id)

    return tuple(parsed)


def parse_standings(page: PageCapture) -> dict[View, tuple[StandingsRow, ...]]:
    """Parse all three standings views from a captured page.

    Args:
        page: A page capture. Its ``standings`` map is empty when the stage has
            no league table.

    Returns:
        Parsed views keyed by split. An empty dict means no table was present.

    Raises:
        StandingsParseError: If a view is missing or malformed.
    """
    if not page.standings:
        return {}

    parsed: dict[View, tuple[StandingsRow, ...]] = {}
    for view in VIEWS:
        try:
            raw_rows = page.standings[view]
        except KeyError as exc:
            raise StandingsParseError(f"missing standings view: {view}") from exc
        parsed[view] = parse_view(view, raw_rows)
    return parsed


def encode_view(view: View, rows: tuple[RawStandingsRow, ...]) -> bytes:
    """Serialize one raw standings view for the raw archive."""
    payload = {"view": view, "rows": [asdict(row) for row in rows]}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def decode_view(body: bytes) -> tuple[RawStandingsRow, ...]:
    """Deserialize one raw standings view from the archive."""
    payload: Any = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        raise StandingsParseError("raw standings payload has no rows list")

    rows: list[RawStandingsRow] = []
    for item in payload["rows"]:
        if not isinstance(item, dict):
            raise StandingsParseError("raw standings row is not an object")
        rows.append(RawStandingsRow(**item))
    return tuple(rows)
