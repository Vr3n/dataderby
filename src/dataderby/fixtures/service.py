"""Refresh the fixture calendar: download, parse, and store."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dataderby.fixtures.competitions import COMPETITIONS, Competition
from dataderby.fixtures.download import fetch_csv, write_cache
from dataderby.fixtures.parse import Fixture, FixtureParseError, parse_csv
from dataderby.fixtures.store import (
    connect,
    initialise,
    upsert_competition,
    upsert_fixtures,
)

Fetcher = Callable[[str], bytes]


@dataclass(frozen=True, slots=True)
class CompetitionRefresh:
    """Per-competition outcome of a refresh.

    Attributes:
        competition_key: Our competition identifier.
        fixtures: Rows parsed.
        played: Rows with a result.
        inserted: Rows that did not exist before.
        updated: Rows whose source hash changed.
        unchanged: Rows whose source hash matched.
        csv_path: Cached export the rows came from.
    """

    competition_key: str
    fixtures: int
    played: int
    inserted: int
    updated: int
    unchanged: int
    csv_path: Path


@dataclass(frozen=True, slots=True)
class RefreshResult:
    """Outcome of one refresh across all competitions.

    Attributes:
        fetched_at: When the refresh started, in UTC.
        competitions: Per-competition outcomes for the ones that succeeded.
        failures: Human-readable failures for the ones that did not.
        fingerprint: SHA-256 over every fixture's source hash, for change detection.
    """

    fetched_at: datetime
    competitions: tuple[CompetitionRefresh, ...]
    failures: tuple[str, ...]
    fingerprint: str

    @property
    def fixture_count(self) -> int:
        """Total fixtures stored across successful competitions."""
        return sum(item.fixtures for item in self.competitions)


class RefreshError(RuntimeError):
    """Raised when at least one competition failed, after committing the rest."""

    def __init__(self, result: RefreshResult) -> None:
        self.result = result
        detail = "; ".join(result.failures)
        super().__init__(f"{len(result.failures)} competition(s) failed: {detail}")


def download_all(
    raw_root: Path,
    competitions: tuple[Competition, ...] = COMPETITIONS,
    *,
    fetched_at: datetime | None = None,
    fetcher: Fetcher = fetch_csv,
) -> dict[str, Path]:
    """Download every competition's CSV export into the cache.

    Args:
        raw_root: Data root, normally ``data``.
        competitions: Competitions to fetch.
        fetched_at: Timestamp to use in cache filenames. Defaults to now in UTC.
        fetcher: Injected for tests; defaults to the HTTP downloader.

    Returns:
        Mapping of competition slug to cached path.

    Raises:
        DownloadError: If an export cannot be retrieved.
    """
    stamp = fetched_at or datetime.now(UTC)
    paths: dict[str, Path] = {}
    for competition in competitions:
        body = fetcher(competition.slug)
        paths[competition.slug] = write_cache(raw_root, competition.slug, body, stamp)
    return paths


def load_from_cache(
    db_path: Path,
    paths: dict[str, Path],
    competitions: tuple[Competition, ...] = COMPETITIONS,
    *,
    seen_at: datetime | None = None,
) -> RefreshResult:
    """Parse cached exports and upsert them into SQLite.

    Each competition commits independently so a later parse failure does not discard
    earlier work. Failures are collected and raised together at the end.

    Args:
        db_path: SQLite file path.
        paths: Mapping of competition slug to cached CSV path.
        competitions: Competitions to load.
        seen_at: Observation timestamp. Defaults to now in UTC.

    Returns:
        The refresh outcome.

    Raises:
        RefreshError: If any competition failed.
    """
    stamp = seen_at or datetime.now(UTC)
    stamp_iso = stamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    outcomes: list[CompetitionRefresh] = []
    failures: list[str] = []
    hashes: list[str] = []

    connection = connect(db_path)
    try:
        initialise(connection)
        for competition in competitions:
            path = paths.get(competition.slug)
            if path is None:
                failures.append(f"{competition.slug}: no cached export")
                continue
            try:
                fixtures = parse_csv(competition, path.read_bytes())
            except FixtureParseError as exc:
                failures.append(str(exc))
                continue
            except OSError as exc:
                failures.append(f"{competition.slug}: cannot read {path}: {exc}")
                continue

            upsert_competition(
                connection,
                competition,
                fixture_count=len(fixtures),
                played_count=_played_count(fixtures),
                fixturedownload_url=f"https://fixturedownload.com/download/{competition.slug}-UTC.csv",
                fetched_at=stamp_iso,
            )
            result = upsert_fixtures(connection, fixtures, seen_at=stamp_iso)
            connection.commit()
            hashes.extend(f"{fixture.fixture_key}:{fixture.row_hash}" for fixture in fixtures)
            outcomes.append(
                CompetitionRefresh(
                    competition_key=competition.key,
                    fixtures=len(fixtures),
                    played=_played_count(fixtures),
                    inserted=result.inserted,
                    updated=result.updated,
                    unchanged=result.unchanged,
                    csv_path=path,
                )
            )
    finally:
        connection.close()

    fingerprint = hashlib.sha256("|".join(sorted(hashes)).encode("utf-8")).hexdigest()
    refresh_result = RefreshResult(
        fetched_at=stamp,
        competitions=tuple(outcomes),
        failures=tuple(failures),
        fingerprint=fingerprint,
    )
    if failures:
        raise RefreshError(refresh_result)
    return refresh_result


def refresh(
    db_path: Path,
    raw_root: Path,
    competitions: tuple[Competition, ...] = COMPETITIONS,
    *,
    fetched_at: datetime | None = None,
    fetcher: Fetcher = fetch_csv,
) -> RefreshResult:
    """Download and store the fixture calendar.

    Args:
        db_path: SQLite file path.
        raw_root: Data root, normally ``data``.
        competitions: Competitions to refresh.
        fetched_at: Observation timestamp. Defaults to now in UTC.
        fetcher: Injected for tests.

    Returns:
        The refresh outcome.

    Raises:
        DownloadError: If an export cannot be retrieved.
        RefreshError: If a cached export cannot be parsed or stored.
    """
    stamp = fetched_at or datetime.now(UTC)
    paths = download_all(raw_root, competitions, fetched_at=stamp, fetcher=fetcher)
    return load_from_cache(db_path, paths, competitions, seen_at=stamp)


def _played_count(fixtures: list[Fixture]) -> int:
    return sum(1 for fixture in fixtures if fixture.status == "played")
