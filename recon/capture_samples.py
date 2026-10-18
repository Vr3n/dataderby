import json
import time

from dataderby.client import get_player_statistics, get_team_statistics, session

STAGE, TOUR = 25662, 4
s = session()

TEAM = [("summaryteam", "all"), ("summaryteam", "offensive"), ("summaryteam", "defensive"),
        ("xg-teamstats", "summary")]
PLAYER = [("summary", "all"), ("summary", "offensive"), ("summary", "defensive"),
          ("summary", "passing"), ("xg-stats", "summary")]

for cat, sub in TEAM:
    d = get_team_statistics(s, STAGE, cat, sub)
    rows = d.get("teamTableStats") or []
    cols = list(rows[0].keys()) if rows else []
    json.dump(d, open(f"samples/team_{cat}_{sub}.json", "w"), ensure_ascii=False, indent=1)
    print(f"team  {cat}/{sub:<10} keys={list(d.keys())} rows={len(rows)} cols={cols}")
    time.sleep(3)

for cat, sub in PLAYER:
    d = get_player_statistics(s, STAGE, cat, sub, tournament_id=TOUR)
    rows = d.get("playerTableStats") or []
    cols = list(rows[0].keys()) if rows else []
    json.dump(d, open(f"samples/player_{cat}_{sub}.json", "w"), ensure_ascii=False, indent=1)
    print(f"player {cat}/{sub:<10} keys={list(d.keys())} rows={len(rows)} cols={cols}")
    time.sleep(3)
