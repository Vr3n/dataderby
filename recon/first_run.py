"""First live run: one season, all nine (section, view) requests.

Settles the two facts the plan left to assertion rather than assumption
(the Summary `subcategory`, and the Defensive/Offensive `statColumns`).
"""

from __future__ import annotations

import html
import json
import random
import re
import time
from pathlib import Path
from urllib.parse import unquote

from src.dataderby.client import WhoscoredError, get_json, session

BASE = "https://www.whoscored.com"
SECTIONS = {
    "summary": ("all", "Rating"),
    "defensive": ("defensive", "tacklePerGame"),
    "offensive": ("offensive", "shotsPerGame"),
}
VIEWS = ("Overall", "Home", "Away")
LINK = re.compile(r"/regions/(\d+)/tournaments/(\d+)/([a-z0-9-]+)")
OPTION = re.compile(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)</option>', re.S)
OUT = Path("data")


def pause(lo: float = 2.5, hi: float = 5.0) -> None:
    time.sleep(random.uniform(lo, hi))


def get(s: object, url: str) -> str:
    resp = s.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text.lstrip("\ufeff")


def catalogue(s: object) -> dict[int, tuple[int, str]]:
    """Map tournament_id -> (region_id, slug) from the home page's nav.

    The home page carries the whole catalogue; region routes and
    ``/tournaments`` answer with the gate page's 775 bytes.
    """
    return {
        int(tid): (int(rid), slug)
        for rid, tid, slug in LINK.findall(get(s, f"{BASE}/"))
        if slug != "seasons"
    }


def selects(s: object, url: str, select_id: str) -> list[tuple[str, str]]:
    """Option (value, text) pairs from a rendered ``select``.

    Values are HTML-entity-escaped *and* percent-encoded, so unescape first.
    """
    body = html.unescape(get(s, url))
    match = re.search(f'<select[^>]*id="{select_id}"[^>]*>(.*?)</select>', body, re.S)
    if not match:
        raise WhoscoredError(f"no select#{select_id} at {url}")
    return [(unquote(value), text.strip()) for value, text in OPTION.findall(match.group(1))]


def stage_id(s: object, url: str) -> int:
    """The stageId embedded in a page's require.config args block."""
    match = re.search(r"stageId:\s*(\d+)", get(s, url))
    if not match:
        raise WhoscoredError(f"no stageId at {url}")
    return int(match.group(1))


def main() -> None:
    s = session()

    tournaments = catalogue(s)
    print(f"catalogue: {len(tournaments)} tournaments; LaLiga={tournaments[4]}")
    pause()

    region_id, slug = tournaments[4]
    tournament_url = f"{BASE}/regions/{region_id}/tournaments/4/{slug}"
    # Any one tournament page carries the region-scoped tournaments select.
    region_tournaments = selects(s, tournament_url, "tournaments")
    print(f"region {region_id} tournaments: {[t for _, t in region_tournaments]}")
    pause()

    seasons = selects(s, tournament_url, "seasons")
    print(f"seasons: {len(seasons)}; newest {seasons[0]}")

    season_path = seasons[0][0]
    season_key = seasons[0][1].replace("/", "-")
    stage = stage_id(s, f"{BASE}{season_path}")
    print(f"season_key={season_key} season_path={season_path} stage_id={stage}")

    teams: dict[int, dict] = {}
    columns: dict[str, list[str]] = {}
    for section, (subcategory, sort_by) in SECTIONS.items():
        for view in VIEWS:
            pause()
            payload = get_json(
                s,
                f"{BASE}/statisticsfeed/1/getteamstatistics",
                {
                    "stageId": stage,
                    "category": "summaryteam",
                    "subcategory": subcategory,
                    "statsAccumulationType": "0",
                    "field": view,
                    "sortBy": sort_by,
                    "sortAscending": "false",
                    "isCurrent": "true",
                    "formation": "",
                    "timeOfTheGameStart": "",
                    "timeOfTheGameEnd": "",
                    "teamIds": "",
                    "against": "",
                    "tournamentOptions": "",
                    "incPens": "",
                    "page": "",
                    "numberOfTeamsToPick": "",
                },
            )
            rows = payload.get("teamTableStats") or []
            stat_columns = payload.get("statColumns") or []
            columns[f"{section}_{view}"] = stat_columns
            print(f"\n{section}/{view}: {len(rows)} teams, statColumns={stat_columns}")
            print(f"  row fields: {sorted(rows[0]) if rows else 'EMPTY'}")
            if rows:
                print(f"  top row   : {rows[0]}")

            for row in rows:
                wide = teams.setdefault(
                    row["teamId"],
                    {
                        "team_id": row["teamId"],
                        "team_name": row["teamName"],
                        "ranking": row["ranking"],
                    },
                )
                for field in stat_columns:
                    wide[f"{section}_{view}_{field}"] = row.get(field)
                wide[f"{section}_rating"] = row.get("rating")
                wide[f"{section}_{view}_ranking"] = row.get("ranking")

    OUT.mkdir(exist_ok=True)
    target = OUT / f"4_{season_key}.json"
    target.write_text(
        json.dumps(
            {
                "region_id": region_id,
                "tournament_id": 4,
                "tournament_name": "LaLiga",
                "season_key": season_key,
                "season_path_id": int(season_path.split("/")[6]),
                "stage_id": stage,
                "stat_columns": columns,
                "teams": sorted(teams.values(), key=lambda t: t["ranking"]),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {target}: {len(teams)} teams, {len(columns)} responses")


if __name__ == "__main__":
    main()
