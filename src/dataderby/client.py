"""WhoScored HTTP client.

Stock curl/requests get 403 from Cloudflare because of TLS fingerprinting.
curl_cffi impersonating Chrome gets through. Two endpoints matter:

  /statisticsfeed/1/getteamstatistics    - season team aggregates
  /statisticsfeed/1/getplayerstatistics  - season player aggregates
  /matches/<id>/live/<slug>              - full event-level match data (HTML,
                                           embedded matchCentreData JSON)

WhoScored also fronts the API with a short-lived Opta/Oddschecker fingerprint
gate (a ~778 byte HTML page, script verify-client.js). It trips on bursts of
requests; back off and retry, or replay a browser session's cookies.
"""

from __future__ import annotations

import json
import logging
import time

from curl_cffi import requests

log = logging.getLogger("whoscored")

BASE = "https://www.whoscored.com"
STATS_FEED = f"{BASE}/statisticsfeed/1"
IMPERSONATE = "chrome"
REFERER = "https://www.whoscored.com/"

# WhoScored's teamstatistics params; defaults mirror the site's own calls.
_TEAM_PARAMS = dict(
    tournamentOptions="",
    timeOfTheGameStart="",
    timeOfTheGameEnd="",
    teamIds="",
    sortBy="Rating",
    sortAscending="",
    page="",
    numberOfTeamsToPick="",
    isCurrent="true",
    formation="",
    incPens="",
    against="",
)

_PLAYER_PARAMS = dict(
    statsAccumulationType="0",
    isCurrent="true",
    playerId="",
    teamIds="",
    matchId="",
    sortBy="Rating",
    sortAscending="",
    age="",
    ageComparisonType="",
    appearances="",
    appearancesComparisonType="",
    field="Overall",
    nationality="",
    positionOptions="",
    timeOfTheGameEnd="",
    timeOfTheGameStart="",
    isMinApp="true",
    page="",
    includeZeroValues="",
    numberOfPlayersToPick="",
    incPens="",
)


class WhoscoredError(RuntimeError):
    pass


def session() -> requests.Session:
    s = requests.Session(impersonate=IMPERSONATE)
    s.headers.update(
        {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": REFERER,
        }
    )
    return s


def _is_gate(content: bytes) -> bool:
    # Both the gate page and the JSON carry a UTF-8 BOM, so strip it first.
    c = content.lstrip(b"\xef\xbb\xbf").lstrip()
    return c[:1] not in (b"{", b"[")


def get_json(
    s: requests.Session,
    url: str,
    params: dict,
    *,
    retries: int = 5,
    backoff: float = 2.0,
) -> dict:
    """GET a stats feed as JSON, retrying past the fingerprint gate.

    The gate returns HTTP 200 with a ~778-byte HTML page, so we detect it by
    the body not starting with `{`/`[` and back off. Happy path is one request.
    """
    name = params.get("category", url.rsplit("/", 1)[-1])
    for attempt in range(1, retries + 1):
        t0 = time.monotonic()
        r = s.get(url, params=params, timeout=20)
        dt = time.monotonic() - t0
        gated = _is_gate(r.content)
        log.debug(
            "attempt %d/%d %s -> HTTP %s, %d bytes, %.2fs%s",
            attempt, retries, name, r.status_code, len(r.content), dt,
            " (GATE)" if gated else "",
        )
        if r.status_code == 200 and not gated:
            log.info("%s: %d bytes in %.2fs", name, len(r.content), dt)
            return json.loads(r.text.lstrip("\ufeff"))
        if r.status_code in (403, 429) or gated:
            if attempt == retries:
                break
            wait = min(20.0, backoff * 2 ** (attempt - 1))
            log.warning(
                "%s: rate-limit gate on attempt %d/%d, retrying in %.1fs",
                name, attempt, retries, wait,
            )
            time.sleep(wait)
            continue
        raise WhoscoredError(f"HTTP {r.status_code} for {url}")
    raise WhoscoredError(f"fingerprint gate not passed after {retries} tries: {url}")


def get_team_statistics(
    s: requests.Session,
    stage_id: int,
    category: str = "summaryteam",
    subcategory: str = "all",
    *,
    field: str = "Overall",
    against: str = "",
    accumulation: str = "0",
    sort_by: str = "Rating",
) -> dict:
    params = {
        "category": category,
        "subcategory": subcategory,
        "statsAccumulationType": accumulation,
        "field": field,
        "stageId": stage_id,
        "sortBy": sort_by,
        **_TEAM_PARAMS,
    }
    params["against"] = against
    return get_json(s, f"{STATS_FEED}/getteamstatistics", params)


def get_player_statistics(
    s: requests.Session,
    stage_id: int,
    category: str = "summary",
    subcategory: str = "all",
    *,
    tournament_id: int | None = None,
    field: str = "Overall",
    accumulation: str = "0",
    page: int | None = None,
) -> dict:
    params = {
        "category": category,
        "subcategory": subcategory,
        "statsAccumulationType": accumulation,
        "stageId": stage_id,
        "tournamentOptions": "" if tournament_id is None else tournament_id,
        **_PLAYER_PARAMS,
    }
    params["field"] = field
    if page is not None:
        params["page"] = page
    return get_json(s, f"{STATS_FEED}/getplayerstatistics", params)


def _extract_match_centre_data(html: str) -> dict:
    key = "matchCentreData:"
    i = html.index(key)
    j = html.index("{", i)
    depth = 0
    in_str = False
    esc = False
    for k in range(j, len(html)):
        c = html[k]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(html[j : k + 1])
    raise WhoscoredError("matchCentreData not found")


def get_match_data(s: requests.Session, match_id: int) -> dict:
    """Full event-level data for one match (events, per-player and per-team stats)."""
    r = s.get(f"{BASE}/matches/{match_id}/live/", timeout=60)
    r.raise_for_status()
    return _extract_match_centre_data(r.text)


def _demo() -> None:
    s = session()
    team = get_team_statistics(s, 25662)
    rows = team.get("teamTableStats") or team.get("table") or []
    assert rows, f"no team rows: {list(team)[:5]}"
    assert rows[0]["name"], rows[0]
    print("team stats ok:", len(rows), "teams; first:", rows[0]["name"])

    time.sleep(4)
    player = get_player_statistics(s, 25662, tournament_id=4)
    prows = player.get("playerTableStats") or player.get("table") or []
    assert prows, f"no player rows: {list(player)[:5]}"
    print("player stats ok:", len(prows), "players; first:", prows[0].get("name"))

    time.sleep(4)
    match = get_match_data(s, 1914253)
    assert match["events"], "no match events"
    print("match ok:", match["score"], len(match["events"]), "events")


if __name__ == "__main__":
    _demo()
