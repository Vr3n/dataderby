"""The competitions ingested in v1.

``slug`` is fixturedownload.com's identifier and appears in the download URL. ``key``
is ours: stable, lower-case, and the foreign key used by the fixtures table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class Competition:
    """One competition and its source identifier.

    Attributes:
        key: Our stable identifier, for example ``epl``.
        slug: The source's season slug, for example ``epl-2026``.
        name: Display name as published by the source.
        country: Country or region the competition belongs to.
        season: Human label for the season, for example ``2026/27``.
    """

    key: str
    slug: str
    name: str
    country: str
    season: str = "2026/27"


COMPETITIONS: Final[tuple[Competition, ...]] = (
    Competition("eredivisie", "eredivisie-2026", "Eredivisie", "Netherlands"),
    Competition("bundesliga", "bundesliga-2026", "Bundesliga", "Germany"),
    Competition("ligue-1", "ligue-1-2026", "Ligue 1", "France"),
    Competition("la-liga", "la-liga-2026", "LaLiga", "Spain"),
    Competition("serie-a", "serie-a-2026", "Serie A", "Italy"),
    Competition("champions-league", "champions-league-2026", "UEFA Champions League", "Europe"),
    Competition("conference-league", "conference-league-2026", "UEFA Conference League", "Europe"),
    Competition("europa-league", "europa-league-2026", "UEFA Europa League", "Europe"),
    Competition("epl", "epl-2026", "English Premier League", "England"),
    Competition("efl-league-two", "efl-league-two-2026", "EFL League Two", "England"),
    Competition("efl-league-one", "efl-league-one-2026", "EFL League One", "England"),
    Competition("championship", "championship-2026", "EFL Championship", "England"),
)

_BY_KEY: Final[dict[str, Competition]] = {item.key: item for item in COMPETITIONS}


def get_competition(key: str) -> Competition:
    """Return the competition with ``key``.

    Args:
        key: Our stable identifier, for example ``epl``.

    Returns:
        The matching competition.

    Raises:
        KeyError: If no competition has that key.
    """
    try:
        return _BY_KEY[key]
    except KeyError as exc:
        known = ", ".join(sorted(_BY_KEY))
        raise KeyError(f"unknown competition {key!r}; known: {known}") from exc
