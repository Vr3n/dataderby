"""Canonical bytes and the content fingerprint for one candidate."""

from __future__ import annotations

import hashlib
import json

from dataderby.contract import MEASURE_COLUMNS, STANDINGS_MEASURES
from dataderby.parse import Candidate, IncompleteCohort, TeamRow
from dataderby.parse_standings import StandingsCandidate, StandingsTeamRow


def _standings_by_id(standings: StandingsCandidate) -> dict[int, StandingsTeamRow]:
    return {row.whoscored_team_id: row for row in standings.rows}


def _team_object(
    candidate_row: TeamRow,
    standings_row: StandingsTeamRow | None,
) -> dict[str, object]:
    missing = [column for column in MEASURE_COLUMNS if column not in candidate_row.measures]
    if missing:
        raise ValueError(f"candidate row is missing measures: {missing}")

    measures = {column: candidate_row.measures[column] for column in MEASURE_COLUMNS}
    if standings_row is None:
        standings: dict[str, object] = {}
    else:
        missing_standings = [
            measure for measure in STANDINGS_MEASURES if measure not in standings_row.measures
        ]
        if missing_standings:
            raise ValueError(f"standings row is missing measures: {missing_standings}")
        standings = {measure: standings_row.measures[measure] for measure in STANDINGS_MEASURES}

    return {
        "whoscored_team_id": candidate_row.whoscored_team_id,
        "measures": measures,
        "standings": standings,
    }


def canonical_bytes(
    candidate: Candidate,
    standings: StandingsCandidate,
    version: int = 1,
) -> bytes:
    """Serialize a candidate and its standings companion deterministically.

    Rows are ordered by ``whoscored_team_id``; every object is key-sorted; a
    missing measure is ``null``. Names, paging, presentation order, and the
    source's zero ``seasonId`` are excluded.

    Args:
        candidate: Parsed feed candidate.
        standings: Parsed standings candidate.
        version: Canonical format version, stored on the header.

    Returns:
        UTF-8 JSON bytes.

    Raises:
        ValueError: If a row is missing a contract measure or a value is not
            finite JSON.
        IncompleteCohort: If a standings row exists for a team outside the feed
            set, or a team is missing a standings row when standings exist.
    """
    if version < 1:
        raise ValueError("canonical version must be positive")

    standings_map = _standings_by_id(standings)
    feed_ids = {row.whoscored_team_id for row in candidate.rows}
    if standings_map and set(standings_map) != feed_ids:
        raise IncompleteCohort(
            "standings and feed team sets differ: "
            f"feed_only={sorted(feed_ids - set(standings_map))}, "
            f"standings_only={sorted(set(standings_map) - feed_ids)}"
        )

    teams = [
        _team_object(
            row,
            standings_map.get(row.whoscored_team_id) if standings_map else None,
        )
        for row in sorted(candidate.rows, key=lambda item: item.whoscored_team_id)
    ]
    payload = {
        "canonical_version": version,
        "is_opta": candidate.is_opta,
        "whoscored_tournament_id": candidate.whoscored_tournament_id,
        "teams": teams,
    }
    text = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return text.encode("utf-8")


def fingerprint(
    candidate: Candidate,
    standings: StandingsCandidate,
    version: int = 1,
) -> str:
    """Return the SHA-256 hex digest of :func:`canonical_bytes`."""
    return hashlib.sha256(canonical_bytes(candidate, standings, version)).hexdigest()
