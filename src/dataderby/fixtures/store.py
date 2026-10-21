"""SQLite storage for the fixture calendar."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dataderby.fixtures.competitions import Competition
from dataderby.fixtures.parse import Fixture

SCHEMA = """
CREATE TABLE IF NOT EXISTS competitions (
    competition_key TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    country         TEXT NOT NULL,
    season          TEXT NOT NULL,
    fixturedownload_slug     TEXT NOT NULL UNIQUE,
    fixturedownload_url      TEXT NOT NULL,
    fixture_count   INTEGER NOT NULL CHECK (fixture_count >= 0),
    played_count    INTEGER NOT NULL CHECK (played_count >= 0),
    fetched_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fixtures (
    fixture_key     TEXT PRIMARY KEY,
    competition_key TEXT NOT NULL REFERENCES competitions (competition_key),
    season          TEXT NOT NULL,
    match_number    INTEGER NOT NULL CHECK (match_number > 0),
    round_number    INTEGER NOT NULL CHECK (round_number > 0),
    kickoff_utc     TEXT NOT NULL,
    kickoff_ist     TEXT NOT NULL,
    timezone        TEXT NOT NULL,
    venue           TEXT NOT NULL,
    home_team       TEXT NOT NULL,
    away_team       TEXT NOT NULL,
    home_score      INTEGER CHECK (home_score IS NULL OR home_score >= 0),
    away_score      INTEGER CHECK (away_score IS NULL OR away_score >= 0),
    status          TEXT NOT NULL CHECK (status IN ('scheduled', 'played')),
    result_raw      TEXT NOT NULL,
    row_hash     TEXT NOT NULL,
    first_seen_at   TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL,
    UNIQUE (competition_key, season, round_number, home_team, away_team),
    CHECK ((status = 'played') = (home_score IS NOT NULL AND away_score IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS fixtures_by_kickoff ON fixtures (kickoff_utc);
CREATE INDEX IF NOT EXISTS fixtures_by_competition ON fixtures (competition_key, kickoff_utc);

CREATE VIEW IF NOT EXISTS v_upcoming_fixtures AS
SELECT
    f.competition_key,
    f.season,
    f.round_number,
    f.kickoff_utc,
    f.kickoff_ist,
    f.home_team,
    f.away_team,
    f.venue,
    f.status
FROM fixtures AS f
WHERE f.kickoff_utc >= strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
ORDER BY f.kickoff_utc;
"""

_LEGACY_COLUMN_RENAMES = (
    ("competitions", "source_slug", "fixturedownload_slug"),
    ("competitions", "source_url", "fixturedownload_url"),
    ("fixtures", "source_hash", "row_hash"),
)


@dataclass(frozen=True, slots=True)
class UpsertResult:
    """How many rows were inserted, changed, or already current.

    Attributes:
        inserted: Rows that did not exist before.
        updated: Rows whose source hash changed.
        unchanged: Rows whose source hash matched.
    """

    inserted: int
    updated: int
    unchanged: int


def connect(path: Path) -> sqlite3.Connection:
    """Open the fixture database, creating the parent directory if needed.

    Args:
        path: SQLite file path.

    Returns:
        A connection with foreign keys enabled and WAL journaling.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def initialise(connection: sqlite3.Connection) -> None:
    """Create tables, indexes and views if they do not exist.

    Renames the pre-rule ``source_*`` columns on an existing database before the
    schema script runs.

    Args:
        connection: An open fixture database connection.
    """
    _rename_legacy_columns(connection)
    connection.executescript(SCHEMA)
    connection.commit()


def _rename_legacy_columns(connection: sqlite3.Connection) -> None:
    """Rename source-prefixed columns left by earlier schema versions.

    Args:
        connection: An open fixture database connection.
    """
    for table, old, new in _LEGACY_COLUMN_RENAMES:
        columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        if old in columns and new not in columns:
            connection.execute(f"ALTER TABLE {table} RENAME COLUMN {old} TO {new}")


def upsert_competition(
    connection: sqlite3.Connection,
    competition: Competition,
    *,
    fixture_count: int,
    played_count: int,
    fixturedownload_url: str,
    fetched_at: str,
) -> None:
    """Insert or update one competition row.

    Args:
        connection: An open fixture database connection.
        competition: The competition being refreshed.
        fixture_count: Rows parsed from the export.
        played_count: Rows with a result.
        fixturedownload_url: URL the export came from.
        fetched_at: ISO-8601 UTC timestamp of the fetch.
    """
    connection.execute(
        """
        INSERT INTO competitions (
            competition_key, name, country, season, fixturedownload_slug, fixturedownload_url,
            fixture_count, played_count, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (competition_key) DO UPDATE SET
            name = excluded.name,
            country = excluded.country,
            season = excluded.season,
            fixturedownload_slug = excluded.fixturedownload_slug,
            fixturedownload_url = excluded.fixturedownload_url,
            fixture_count = excluded.fixture_count,
            played_count = excluded.played_count,
            fetched_at = excluded.fetched_at
        """,
        (
            competition.key,
            competition.name,
            competition.country,
            competition.season,
            competition.slug,
            fixturedownload_url,
            fixture_count,
            played_count,
            fetched_at,
        ),
    )


def upsert_fixtures(
    connection: sqlite3.Connection,
    fixtures: list[Fixture],
    *,
    seen_at: str,
) -> UpsertResult:
    """Insert or update fixtures idempotently.

    ``first_seen_at`` is preserved across runs; ``last_seen_at`` always advances.

    Args:
        connection: An open fixture database connection.
        fixtures: Parsed fixtures for one competition.
        seen_at: ISO-8601 UTC timestamp of this observation.

    Returns:
        Counts of inserted, changed and unchanged rows.
    """
    if not fixtures:
        return UpsertResult(inserted=0, updated=0, unchanged=0)

    keys = [fixture.fixture_key for fixture in fixtures]
    placeholders = ", ".join("?" for _ in keys)
    existing = {
        row["fixture_key"]: row["row_hash"]
        for row in connection.execute(
            f"SELECT fixture_key, row_hash FROM fixtures WHERE fixture_key IN ({placeholders})",
            keys,
        )
    }

    inserted = sum(1 for fixture in fixtures if fixture.fixture_key not in existing)
    updated = sum(
        1
        for fixture in fixtures
        if existing.get(fixture.fixture_key) not in (None, fixture.row_hash)
    )
    unchanged = len(fixtures) - inserted - updated

    connection.executemany(
        """
        INSERT INTO fixtures (
            fixture_key, competition_key, season, match_number, round_number,
            kickoff_utc, kickoff_ist, timezone, venue, home_team, away_team,
            home_score, away_score, status, result_raw, row_hash,
            first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (fixture_key) DO UPDATE SET
            match_number = excluded.match_number,
            kickoff_utc = excluded.kickoff_utc,
            kickoff_ist = excluded.kickoff_ist,
            venue = excluded.venue,
            home_team = excluded.home_team,
            away_team = excluded.away_team,
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            status = excluded.status,
            result_raw = excluded.result_raw,
            row_hash = excluded.row_hash,
            last_seen_at = excluded.last_seen_at
        """,
        [
            (
                fixture.fixture_key,
                fixture.competition_key,
                fixture.season,
                fixture.match_number,
                fixture.round_number,
                _iso_utc(fixture.kickoff_utc),
                fixture.kickoff_ist.isoformat(timespec="seconds"),
                "Asia/Kolkata",
                fixture.venue,
                fixture.home_team,
                fixture.away_team,
                fixture.home_score,
                fixture.away_score,
                fixture.status,
                fixture.result_raw,
                fixture.row_hash,
                seen_at,
                seen_at,
            )
            for fixture in fixtures
        ],
    )
    return UpsertResult(inserted=inserted, updated=updated, unchanged=unchanged)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
