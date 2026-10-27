"""Canonical team identity and its per-source mappings.

One row per club lives in ``dim_team``; one row per (source, source team) lives
in ``team_source_key``. Facts and headers keep every ``whoscored_*`` column for
lineage, so the raw archive still rebuilds the warehouse. Consumers join the
canonical id once P2 wires it into the views.
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


def mint_team_id() -> str:
    """Return a fresh canonical team id.

    Returns:
        ``dtm_`` plus 12 hex characters. Random on purpose: two writers never
        collide, and the mapping table (not the id) is what joins a source team.
    """
    return f"dtm_{uuid4().hex[:12]}"


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
        canonical_id = mint_team_id()
        con.execute(
            """
            INSERT INTO dim_team (dataderby_team_id, canonical_name, first_seen_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            [canonical_id, name, seen_at, now],
        )
        added_teams += 1
        con.execute(
            """
            INSERT INTO team_source_key (dataderby_team_id, source, source_team_id)
            VALUES (?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            [canonical_id, WHOSCORED_SOURCE, str(team_id)],
        )
        added_mappings += 1
    return TeamBackfill(teams=added_teams, mappings=added_mappings)
