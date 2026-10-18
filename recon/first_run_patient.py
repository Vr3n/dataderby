"""One-season first run, patient about the fingerprint gate.

Same work as first_run.py but retries the feed past the Oddschecker gate at a
gentle cadence until the payload arrives or the deadline passes.
"""

from __future__ import annotations

import html
import json
import random
import re
import time
from pathlib import Path
from urllib.parse import unquote

from curl_cffi import requests

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
DEADLINE_S = 1500.0  # total budget for the 9 feed requests
GATE_PAUSE_S = 45.0


def get(s: requests.Session, url: str, *, params: dict | None = None) -> bytes:
    r = s.get(url, params=params, timeout=25)
    r.raise_for_status()
    return r.content


def is_json(body: bytes) -> bool:
    return body.lstrip(b"\xef\xbb\xbf").lstrip()[:1] in (b"{", b"[")


def catalogue(s: requests.Session) -> dict[int, tuple[int, str]]:
    return {
        int(tid): (int(rid), slug)
        for rid, tid, slug in LINK.findall(get(s, f"{BASE}/").decode("utf-8"))
        if slug != "seasons"
    }


def selects(s: requests.Session, url: str, select_id: str) -> list[tuple[str, str]]:
    body = html.unescape(get(s, url).decode("utf-8", "replace"))
    match = re.search(
        f'<select[^>]*id="{select_id}"[^>]*>(.*?)</select>', body, re.S
    )
    if not match:
        raise RuntimeError(f"no select#{select_id} at {url}")
    return [
        (unquote(value), text.strip())
        for value, text in OPTION.findall(match.group(1))
    ]


def stage_id(s: requests.Session, url: str) -> int:
    match = re.search(r"stageId:\s*(\d+)", get(s, url).decode("utf-8"))
    if not match:
        raise RuntimeError(f"no stageId at {url}")
    return int(match.group(1))


def feed(s: requests.Session, params: dict, deadline: float) -> dict | None:
    """Fetch the feed, retrying past the gate until deadline. None on failure."""
    while time.monotonic() < deadline:
        body = get(s, f"{BASE}/statisticsfeed/1/getteamstatistics", params=params)
        if is_json(body):
            return json.loads(body.lstrip(b"\xef\xbb\xbf").decode("utf-8"))
        print(f"  gate ({len(body)}B), next attempt in {GATE_PAUSE_S}s")
        time.sleep(GATE_PAUSE_S)
    return None


def main() -> None:
    s = requests.Session(impersonate="chrome")
    s.headers.update(
        {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": (
                f"{BASE}/regions/206/tournaments/4/seasons/11213"
                "/stages/25662/teamstatistics/spain-laliga-2026-2027"
            ),
        }
    )

    tournaments = catalogue(s)
    region_id, slug = tournaments[4]
    tournament_url = f"{BASE}/regions/{region_id}/tournaments/4/{slug}"
    seasons = selects(s, tournament_url, "seasons")
    season_path, season_label = seasons[0]
    season_key = season_label.replace("/", "-")
    stage = stage_id(s, f"{BASE}{season_path}")
    print(
        f"stage_id={stage} season_key={season_key} season_path={season_path} "
        f"start={time.strftime('%H:%M:%S')}"
    )

    deadline = time.monotonic() + DEADLINE_S
    teams: dict[int, dict] = {}
    columns: dict[str, list[str]] = {}
    ok = 0
    for section, (subcategory, sort_by) in SECTIONS.items():
        for view in VIEWS:
            params = {
                "stageId": stage,
                "category": "summaryteam",
                "subcategory": subcategory,
                "statsAccumulationType": "0",
                "field": view,
                "sortBy": sort_by,
                "sortAscending": "false",
                "isCurrent": "true",
                "against": "",
                "teamIds": "",
                "formation": "",
                "incPens": "",
            }
            payload = feed(s, params, deadline)
            if payload is None:
                print(f"FAILED (gate never cleared): {section}/{view}; nothing written")
                return
            rows = payload.get("teamTableStats") or []
            stat_columns = payload.get("statColumns") or []
            columns[f"{section}_{view}"] = stat_columns
            print(f"OK {section}/{view}: {len(rows)} teams {stat_columns}")
            for row in rows:
                wide = teams.setdefault(
                    row["teamId"],
                    {
                        "team_id": row["teamId"],
                        "team_name": row["teamName"],
                        "ranking": row["ranking"],
                        "region_name": row["teamRegionName"],
                    },
                )
                for field in stat_columns:
                    wide[f"{section}_{view}_{field}"] = row.get(field)
                wide[f"{section}_rating"] = row.get("rating")
            ok += 1
            time.sleep(random.uniform(3.0, 5.0))

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
    print(f"wrote {target}: {ok}/9 requests, {len(teams)} teams")


if __name__ == "__main__":
    main()