"""Parse a fixturedownload.com CSV into typed fixtures.

The site publishes times in UTC when the ``-UTC.csv`` export is requested. We parse
that naive timestamp as UTC and derive the Asia/Kolkata representation ourselves.

Why not request the source's IST export? Measured on 19 Oct 2026: it is missing for
five of twelve competitions, and where it exists it is wrong for 56 of 380 EPL rows
(for example match 46, 20/09 13:00 UTC, exported as 19/09 19:30 IST). One code path
over UTC is both simpler and correct.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal
from zoneinfo import ZoneInfo

from dataderby.fixtures.competitions import Competition

IST: Final[ZoneInfo] = ZoneInfo("Asia/Kolkata")
REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "Match Number",
    "Round Number",
    "Date",
    "Location",
    "Home Team",
    "Away Team",
    "Result",
)
_DATE_FORMAT: Final[str] = "%d/%m/%Y %H:%M"
_PENDING_RESULTS: Final[frozenset[str]] = frozenset({"", "-"})

Status = Literal["scheduled", "played"]


class FixtureParseError(ValueError):
    """Raised when a fixture export does not match the expected contract."""


@dataclass(frozen=True, slots=True)
class Fixture:
    """One match in the calendar.

    Attributes:
        fixture_key: Stable key derived from competition, season, round and teams.
        competition_key: Our competition identifier.
        season: Season label, for example ``2026/27``.
        match_number: The source's per-season sequence number.
        round_number: The source's round number.
        kickoff_utc: Kick-off as an aware UTC datetime.
        kickoff_ist: Kick-off as an aware Asia/Kolkata datetime.
        venue: Stadium name as published.
        home_team: Home team name as published.
        away_team: Away team name as published.
        home_score: Home goals, or ``None`` before the match is played.
        away_score: Away goals, or ``None`` before the match is played.
        status: ``scheduled`` or ``played``.
        result_raw: The source's result string, kept for audit.
        row_hash: SHA-256 of the source row, used to detect changes.
    """

    fixture_key: str
    competition_key: str
    season: str
    match_number: int
    round_number: int
    kickoff_utc: datetime
    kickoff_ist: datetime
    venue: str
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    status: Status
    result_raw: str
    row_hash: str


def fixture_key(
    competition_key: str,
    season: str,
    round_number: int,
    home_team: str,
    away_team: str,
) -> str:
    """Build a stable key for a fixture.

    Round and teams are used rather than the source's match number: a postponed match
    can be renumbered, but it is still the same fixture between the same teams.

    Args:
        competition_key: Our competition identifier.
        season: Season label.
        round_number: The source's round number.
        home_team: Home team name.
        away_team: Away team name.

    Returns:
        A 20-character hexadecimal key.
    """
    material = "|".join((competition_key, season, str(round_number), home_team, away_team))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def parse_kickoff(raw: str) -> tuple[datetime, datetime]:
    """Parse the source's naive UTC timestamp into UTC and IST datetimes.

    Args:
        raw: Timestamp in ``DD/MM/YYYY HH:MM`` form.

    Returns:
        A ``(utc, ist)`` pair of aware datetimes.

    Raises:
        FixtureParseError: If the timestamp does not match the expected format.
    """
    try:
        naive = datetime.strptime(raw.strip(), _DATE_FORMAT)
    except ValueError as exc:
        raise FixtureParseError(f"invalid kick-off timestamp {raw!r}") from exc
    utc = naive.replace(tzinfo=UTC)
    return utc, utc.astimezone(IST)


def parse_result(raw: str) -> tuple[int | None, int | None]:
    """Parse the source's result string.

    Args:
        raw: ``"3 - 0"`` for a played match, or an empty string / ``"-"`` pending.

    Returns:
        A ``(home, away)`` pair, both ``None`` when the match is not played.

    Raises:
        FixtureParseError: If a played result cannot be parsed.
    """
    value = raw.strip()
    if value in _PENDING_RESULTS:
        return None, None
    parts = value.split("-", maxsplit=1)
    if len(parts) != 2:
        raise FixtureParseError(f"invalid result {raw!r}; expected 'home - away'")
    try:
        home, away = (int(part.strip()) for part in parts)
    except ValueError as exc:
        raise FixtureParseError(f"invalid result {raw!r}; expected integers") from exc
    if home < 0 or away < 0:
        raise FixtureParseError(f"invalid result {raw!r}; scores must be non-negative")
    return home, away


def _parse_int(raw: str, field: str) -> int:
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise FixtureParseError(f"invalid {field} {raw!r}; expected an integer") from exc


def _validate_columns(fieldnames: Sequence[str] | None, slug: str) -> None:
    actual = tuple(fieldnames or ())
    if actual != REQUIRED_COLUMNS:
        raise FixtureParseError(
            f"{slug}: unexpected columns; expected {REQUIRED_COLUMNS}, got {actual}"
        )


def _cell(row: dict[str, str], column: str, slug: str, line: int) -> str:
    value = row.get(column)
    if not isinstance(value, str):
        raise FixtureParseError(f"{slug} line {line}: missing value for {column!r}")
    return value


def parse_csv(competition: Competition, body: bytes) -> list[Fixture]:
    """Parse one competition's CSV export.

    Args:
        competition: The competition the export belongs to.
        body: Raw CSV bytes, optionally UTF-8 with a BOM.

    Returns:
        Fixtures in source order.

    Raises:
        FixtureParseError: If the export is empty, has drifted columns, or contains a
            malformed row.
    """
    text = body.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    _validate_columns(reader.fieldnames, competition.slug)

    fixtures: list[Fixture] = []
    seen: set[str] = set()
    for line_number, row in enumerate(reader, start=2):
        values = [row.get(column) for column in REQUIRED_COLUMNS]
        if all(not value or not value.strip() for value in values if isinstance(value, str)):
            continue
        try:
            home_score, away_score = parse_result(
                _cell(row, "Result", competition.slug, line_number)
            )
            kickoff_utc, kickoff_ist = parse_kickoff(
                _cell(row, "Date", competition.slug, line_number)
            )
            round_number = _parse_int(
                _cell(row, "Round Number", competition.slug, line_number), "round number"
            )
            key = fixture_key(
                competition.key,
                competition.season,
                round_number,
                _cell(row, "Home Team", competition.slug, line_number),
                _cell(row, "Away Team", competition.slug, line_number),
            )
        except FixtureParseError as exc:
            raise FixtureParseError(f"{competition.slug} line {line_number}: {exc}") from exc
        if key in seen:
            raise FixtureParseError(
                f"{competition.slug} line {line_number}: duplicate fixture {key}"
            )
        seen.add(key)
        fixtures.append(
            Fixture(
                fixture_key=key,
                competition_key=competition.key,
                season=competition.season,
                match_number=_parse_int(
                    _cell(row, "Match Number", competition.slug, line_number), "match number"
                ),
                round_number=round_number,
                kickoff_utc=kickoff_utc,
                kickoff_ist=kickoff_ist,
                venue=_cell(row, "Location", competition.slug, line_number).strip(),
                home_team=_cell(row, "Home Team", competition.slug, line_number).strip(),
                away_team=_cell(row, "Away Team", competition.slug, line_number).strip(),
                home_score=home_score,
                away_score=away_score,
                status="played" if home_score is not None else "scheduled",
                result_raw=_cell(row, "Result", competition.slug, line_number),
                row_hash=hashlib.sha256(
                    json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
                ).hexdigest(),
            )
        )

    if not fixtures:
        raise FixtureParseError(f"{competition.slug}: export contained no fixtures")
    return fixtures
