"""Canonical team and stage identity and their per-source mappings.

One row per club lives in ``dim_team``; one row per stage lives in
``dim_stage``. One row per (source, source id) lives in the two key tables.
Facts and headers keep every ``whoscored_*`` column for lineage, so the raw
archive still rebuilds the warehouse. Consumers join the canonical ids, which
publish writes on every new row and the backfill fills on old rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import duckdb

#: Source label for rows derived from the WhoScored feeds.
WHOSCORED_SOURCE = "whoscored"


@dataclass(frozen=True, slots=True)
class TeamBackfill:
    """Counts from one :func:`backfill_team_dims` run; reruns add zero."""

    teams: int
    mappings: int


@dataclass(frozen=True, slots=True)
class StageBackfill:
    """Counts from one :func:`backfill_stage_dims` run; reruns add zero."""

    stages: int
    mappings: int


@dataclass(frozen=True, slots=True)
class CanonicalFill:
    """Canonical ids written onto existing headers and facts."""

    headers: int
    team_facts: int
    standings_facts: int


def mint_team_id() -> str:
    """Return a fresh canonical team id.

    Returns:
        ``dtm_`` plus 12 hex characters. Random on purpose: two writers never
        collide, and the mapping table (not the id) is what joins a source team.
    """
    return f"dtm_{uuid4().hex[:12]}"


def mint_stage_id() -> str:
    """Return a fresh canonical stage id.

    Returns:
        ``dst_`` plus 12 hex characters, minted for the same reason as teams.
    """
    return f"dst_{uuid4().hex[:12]}"


def ensure_team_mapping(
    con: duckdb.DuckDBPyConnection,
    team_id: int,
    team_name: str,
    *,
    seen_at: datetime | None = None,
) -> str:
    """Return the canonical id for a WhoScored team, creating rows if needed.

    Curation owns identity: this is the one function that mints. Publish never
    calls it; publish resolves and blocks on a miss instead.

    Args:
        con: Open writable DuckDB connection with the schema applied.
        team_id: WhoScored team id.
        team_name: Canonical name for a new row; ignored when mapped.
        seen_at: First-seen instant for a new row; defaults to now.

    Returns:
        The canonical ``dataderby_team_id`` for the team.
    """
    row = con.execute(
        """
        SELECT dataderby_team_id FROM team_source_key
        WHERE source = ? AND source_team_id = ?
        """,
        [WHOSCORED_SOURCE, str(team_id)],
    ).fetchone()
    if row is not None:
        return str(row[0])
    moment = seen_at or datetime.now(UTC)
    canonical_id = mint_team_id()
    con.execute(
        """
        INSERT INTO dim_team (dataderby_team_id, canonical_name, first_seen_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT DO NOTHING
        """,
        [canonical_id, team_name, moment, moment],
    )
    con.execute(
        """
        INSERT INTO team_source_key (dataderby_team_id, source, source_team_id)
        VALUES (?, ?, ?)
        ON CONFLICT DO NOTHING
        """,
        [canonical_id, WHOSCORED_SOURCE, str(team_id)],
    )
    return canonical_id


def ensure_stage_mapping(
    con: duckdb.DuckDBPyConnection,
    *,
    tournament_id: int,
    season_id: int,
    stage_id: int,
    tournament_name: str,
    season_key: str,
    stage_code: str,
    canonical_name: str,
    seen_at: datetime | None = None,
) -> str:
    """Return the canonical id for a WhoScored stage, creating rows if needed.

    Args:
        con: Open writable DuckDB connection with the schema applied.
        tournament_id: WhoScored tournament id.
        season_id: WhoScored season id.
        stage_id: WhoScored stage id.
        tournament_name: Human competition name for a new row.
        season_key: Human season label (``YYYY-YYYY``) for a new row.
        stage_code: Curated domain stage code for a new row.
        canonical_name: Display name for a new row.
        seen_at: First-seen instant for a new row; defaults to now.

    Returns:
        The canonical ``dataderby_stage_id`` for the stage.
    """
    row = con.execute(
        """
        SELECT dataderby_stage_id FROM stage_source_key
        WHERE source = ?
          AND source_tournament_id = ?
          AND source_season_id = ?
          AND source_stage_id = ?
        """,
        [WHOSCORED_SOURCE, str(tournament_id), str(season_id), str(stage_id)],
    ).fetchone()
    if row is not None:
        return str(row[0])
    moment = seen_at or datetime.now(UTC)
    canonical_id = mint_stage_id()
    con.execute(
        """
        INSERT INTO dim_stage (
            dataderby_stage_id, tournament_name, season_key, stage_code,
            canonical_name, first_seen_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT DO NOTHING
        """,
        [canonical_id, tournament_name, season_key, stage_code, canonical_name, moment, moment],
    )
    con.execute(
        """
        INSERT INTO stage_source_key (
            dataderby_stage_id, source, source_tournament_id,
            source_season_id, source_stage_id
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT DO NOTHING
        """,
        [canonical_id, WHOSCORED_SOURCE, str(tournament_id), str(season_id), str(stage_id)],
    )
    return canonical_id


def unmapped_stages(con: duckdb.DuckDBPyConnection) -> list[tuple[int, int, int]]:
    """Return stage addresses with no WhoScored mapping row.

    Args:
        con: Open DuckDB connection with the schema applied.

    Returns:
        Distinct ``(tournament, season, stage)`` triples from headers that
        cannot resolve, ordered by address. Empty means coverage is 100%.
    """
    return [
        (int(tournament), int(season), int(stage))
        for tournament, season, stage in con.execute(
            """
            SELECT DISTINCT
                s.whoscored_tournament_id,
                s.whoscored_season_id,
                s.whoscored_stage_id
            FROM competition_snapshot s
            LEFT JOIN stage_source_key k
              ON k.source = ?
             AND k.source_tournament_id = CAST(s.whoscored_tournament_id AS VARCHAR)
             AND k.source_season_id = CAST(s.whoscored_season_id AS VARCHAR)
             AND k.source_stage_id = CAST(s.whoscored_stage_id AS VARCHAR)
            WHERE k.source IS NULL
            ORDER BY 1, 2, 3
            """,
            [WHOSCORED_SOURCE],
        ).fetchall()
    ]


def backfill_stage_dims(con: duckdb.DuckDBPyConnection) -> StageBackfill:
    """Insert canonical stage rows and mappings for every unmapped header.

    Args:
        con: Open writable DuckDB connection with the schema applied.

    Returns:
        How many stage and mapping rows this call added.
    """
    added_stages = 0
    added_mappings = 0
    for tournament_id, season_id, stage_id in unmapped_stages(con):
        header = con.execute(
            """
            SELECT season_key, min(accepted_at)
            FROM competition_snapshot
            WHERE whoscored_tournament_id = ?
              AND whoscored_season_id = ?
              AND whoscored_stage_id = ?
            GROUP BY season_key
            """,
            [tournament_id, season_id, stage_id],
        ).fetchone()
        season_key = str(header[0]) if header else "0000-0000"
        seen_at = header[1] if header and header[1] is not None else datetime.now(UTC)
        # Registry-absent stages only: the stage_code embeds the stage id so
        # two unconfigured stages of one season can never share a name.
        # Configured stages are ensured with real names by `dims backfill`.
        ensure_stage_mapping(
            con,
            tournament_id=tournament_id,
            season_id=season_id,
            stage_id=stage_id,
            tournament_name=f"tournament_{tournament_id}",
            season_key=season_key,
            stage_code=f"unmapped-{stage_id}",
            canonical_name=f"unmapped tournament_{tournament_id} {season_key} stage {stage_id}",
            seen_at=seen_at,
        )
        added_stages += 1
        added_mappings += 1
    return StageBackfill(stages=added_stages, mappings=added_mappings)


def _filled_count(con: duckdb.DuckDBPyConnection, table: str, column: str) -> int:
    """Return rows of a table whose canonical id column is set."""
    row = con.execute(f"SELECT count(*) FROM {table} WHERE {column} IS NOT NULL").fetchone()
    return int(row[0]) if row else 0


def fill_canonical_ids(con: duckdb.DuckDBPyConnection) -> CanonicalFill:
    """Write canonical ids onto existing headers and facts from the mappings.

    Only rows with a NULL canonical id change, so reruns are no-ops.

    Args:
        con: Open writable DuckDB connection with the schema applied.

    Returns:
        How many headers, team facts, and standings facts carry an id now.
    """
    con.execute(
        """
        UPDATE competition_snapshot s
        SET dataderby_stage_id = k.dataderby_stage_id
        FROM stage_source_key k
        WHERE s.dataderby_stage_id IS NULL
          AND k.source = ?
          AND k.source_tournament_id = CAST(s.whoscored_tournament_id AS VARCHAR)
          AND k.source_season_id = CAST(s.whoscored_season_id AS VARCHAR)
          AND k.source_stage_id = CAST(s.whoscored_stage_id AS VARCHAR)
        """,
        [WHOSCORED_SOURCE],
    )
    con.execute(
        """
        UPDATE fact_team_snapshot f
        SET dataderby_team_id = k.dataderby_team_id
        FROM team_source_key k
        WHERE f.dataderby_team_id IS NULL
          AND k.source = ?
          AND k.source_team_id = CAST(f.whoscored_team_id AS VARCHAR)
        """,
        [WHOSCORED_SOURCE],
    )
    con.execute(
        """
        UPDATE fact_standings_snapshot f
        SET dataderby_team_id = k.dataderby_team_id
        FROM team_source_key k
        WHERE f.dataderby_team_id IS NULL
          AND k.source = ?
          AND k.source_team_id = CAST(f.whoscored_team_id AS VARCHAR)
        """,
        [WHOSCORED_SOURCE],
    )
    return CanonicalFill(
        headers=_filled_count(con, "competition_snapshot", "dataderby_stage_id"),
        team_facts=_filled_count(con, "fact_team_snapshot", "dataderby_team_id"),
        standings_facts=_filled_count(con, "fact_standings_snapshot", "dataderby_team_id"),
    )


def unmapped_teams(con: duckdb.DuckDBPyConnection) -> list[tuple[int, str]]:
    """Return ``(whoscored_team_id, name)`` pairs with no mapping row.

    Args:
        con: Open DuckDB connection with the schema applied.

    Returns:
        Distinct fact teams missing a ``team_source_key`` row for the
        WhoScored source, ordered by team id. Empty means coverage is 100%.
    """
    return [
        (int(team_id), str(name))
        for team_id, name in con.execute(
            """
            SELECT DISTINCT f.whoscored_team_id, f.whoscored_team_name
            FROM fact_team_snapshot f
            LEFT JOIN team_source_key k
              ON k.source = ?
             AND k.source_team_id = CAST(f.whoscored_team_id AS VARCHAR)
            WHERE k.source IS NULL
            ORDER BY f.whoscored_team_id
            """,
            [WHOSCORED_SOURCE],
        ).fetchall()
    ]


def backfill_team_dims(con: duckdb.DuckDBPyConnection) -> TeamBackfill:
    """Insert canonical rows for every unmapped fact team.

    Each new club gets one ``dim_team`` row (named from its fact rows, first
    seen from its earliest accepted snapshot) and one ``team_source_key`` row.
    Reruns insert nothing.

    Args:
        con: Open writable DuckDB connection with the schema applied.

    Returns:
        How many team and mapping rows this call added.
    """
    now = datetime.now(UTC)
    added_teams = 0
    added_mappings = 0
    for team_id, name in unmapped_teams(con):
        first_seen = con.execute(
            """
            SELECT min(s.accepted_at)
            FROM fact_team_snapshot f
            JOIN competition_snapshot s USING (snapshot_id)
            WHERE f.whoscored_team_id = ?
            """,
            [team_id],
        ).fetchone()
        seen_at = first_seen[0] if first_seen and first_seen[0] is not None else now
        ensure_team_mapping(con, team_id, name, seen_at=seen_at)
        added_teams += 1
        added_mappings += 1
    return TeamBackfill(teams=added_teams, mappings=added_mappings)
