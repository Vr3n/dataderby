"""Dagster assets for the fixture calendar.

Two assets:

- ``raw_fixture_csvs`` downloads the twelve UTC exports into ``data/fixtures/raw``.
- ``fixtures_table`` parses them and upserts the SQLite calendar.

The split keeps the raw payload as the replay guarantee: the table can be rebuilt
without touching the network.
"""

from datetime import UTC, datetime
from pathlib import Path

from dagster import (
    AssetCheckResult,
    AssetExecutionContext,
    ConfigurableResource,
    DataVersion,
    MaterializeResult,
    MetadataValue,
    asset,
    asset_check,
)

from dataderby.fixtures.competitions import COMPETITIONS
from dataderby.fixtures.download import fetch_csv, write_cache
from dataderby.fixtures.service import load_from_cache
from dataderby.fixtures.store import connect


class FixtureSettings(ConfigurableResource[None]):
    """Filesystem locations used by the fixture assets.

    Attributes:
        db_path: SQLite database file.
        raw_root: Data root; CSVs land under ``<raw_root>/fixtures/raw``.
    """

    db_path: str = "data/fixtures.sqlite3"
    raw_root: str = "data"


@asset(
    group_name="fixtures",
    compute_kind="http",
    description="Download the twelve fixture CSVs in UTC and cache them on disk.",
)
def raw_fixture_csvs(
    context: AssetExecutionContext,
    settings: FixtureSettings,
) -> dict[str, str]:
    """Fetch every competition's UTC CSV export.

    Args:
        context: Dagster asset context, used for logging and metadata.
        settings: Filesystem locations.

    Returns:
        Mapping of competition slug to cached CSV path.
    """
    fetched_at = datetime.now(UTC)
    paths: dict[str, str] = {}
    for competition in COMPETITIONS:
        body = fetch_csv(competition.slug)
        path = write_cache(Path(settings.raw_root), competition.slug, body, fetched_at)
        paths[competition.slug] = str(path)
        context.log.info("cached %s (%d bytes)", competition.slug, len(body))

    context.add_output_metadata(
        {
            "fetched_at": fetched_at.isoformat(),
            "files": len(paths),
            "paths": MetadataValue.json(paths),
        }
    )
    return paths


@asset(
    group_name="fixtures",
    compute_kind="sqlite",
    description="Parse cached CSVs into the SQLite fixture calendar.",
)
def fixtures_table(
    context: AssetExecutionContext,
    raw_fixture_csvs: dict[str, str],
    settings: FixtureSettings,
) -> MaterializeResult[None]:
    """Upsert the cached exports into SQLite.

    Args:
        context: Dagster asset context.
        raw_fixture_csvs: Mapping of competition slug to cached CSV path.
        settings: Filesystem locations.

    Returns:
        Materialisation metadata, including a content fingerprint.
    """
    paths = {slug: Path(path) for slug, path in raw_fixture_csvs.items()}
    result = load_from_cache(
        Path(settings.db_path),
        paths,
        seen_at=datetime.now(UTC),
    )
    context.log.info(
        "stored %d fixtures across %d competitions",
        result.fixture_count,
        len(result.competitions),
    )
    return MaterializeResult(
        metadata={
            "competitions": len(result.competitions),
            "fixtures": result.fixture_count,
            "inserted": sum(item.inserted for item in result.competitions),
            "updated": sum(item.updated for item in result.competitions),
            "unchanged": sum(item.unchanged for item in result.competitions),
            "fingerprint": result.fingerprint,
        },
        data_version=DataVersion(result.fingerprint),
    )


def _scalar(db_path: str, sql: str) -> int:
    connection = connect(Path(db_path))
    try:
        row = connection.execute(sql).fetchone()
    finally:
        connection.close()
    return int(row[0]) if row is not None else 0


@asset_check(asset=fixtures_table, blocking=True)
def fixture_kickoffs_are_ist(settings: FixtureSettings) -> AssetCheckResult:
    """Every stored kick-off must carry a +05:30 offset."""
    offending = _scalar(
        settings.db_path,
        "SELECT count(*) FROM fixtures WHERE kickoff_ist NOT LIKE '%+05:30'",
    )
    return AssetCheckResult(
        passed=offending == 0,
        metadata={"rows_without_ist_offset": offending},
    )


@asset_check(asset=fixtures_table, blocking=True)
def fixture_counts_match_source(settings: FixtureSettings) -> AssetCheckResult:
    """Stored row counts must match the counts recorded per competition."""
    drift = _scalar(
        settings.db_path,
        """
        SELECT count(*)
        FROM competitions AS c
        WHERE c.fixture_count <> (
            SELECT count(*) FROM fixtures AS f WHERE f.competition_key = c.competition_key
        )
        """,
    )
    return AssetCheckResult(passed=drift == 0, metadata={"competitions_in_drift": drift})


@asset_check(asset=fixtures_table, blocking=True)
def fixture_match_numbers_unique(settings: FixtureSettings) -> AssetCheckResult:
    """Match numbers must be unique within a competition and season."""
    duplicates = _scalar(
        settings.db_path,
        """
        SELECT count(*) FROM (
            SELECT competition_key, season, match_number
            FROM fixtures
            GROUP BY competition_key, season, match_number
            HAVING count(*) > 1
        )
        """,
    )
    return AssetCheckResult(
        passed=duplicates == 0, metadata={"duplicate_match_numbers": duplicates}
    )


@asset_check(asset=fixtures_table, blocking=True)
def fixture_calendar_complete(settings: FixtureSettings) -> AssetCheckResult:
    """All configured competitions must be present."""
    present = _scalar(settings.db_path, "SELECT count(*) FROM competitions")
    return AssetCheckResult(
        passed=present == len(COMPETITIONS),
        metadata={"competitions_present": present, "expected": len(COMPETITIONS)},
    )
