"""Example: La Liga 2026/2027 team season statistics.

Run:  uv run python examples/team_season_stats.py
"""

import json
import logging
import time
from pathlib import Path

from dataderby.client import WhoscoredError, get_team_statistics, session

# La Liga 2026/2027
STAGE_ID = 25662
TOURNAMENT_ID = 4

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("whoscored")

OUT = Path("samples/team_summaryteam_all.json")


def main() -> None:
    log.info("La Liga 2026/2027 team stats (stageId=%d)", STAGE_ID)

    log.info("opening session (Chrome TLS impersonation)")
    t0 = time.monotonic()
    s = session()

    log.info("GET getteamstatistics  category=summaryteam subcategory=all")
    try:
        data = get_team_statistics(s, STAGE_ID, "summaryteam", "all")
    except WhoscoredError as e:
        log.error("failed: %s", e)
        raise SystemExit(1)
    log.info("parsed JSON in %.2fs total", time.monotonic() - t0)

    rows = data["teamTableStats"]
    log.info("got %d teams, %d columns", len(rows), len(rows[0]))

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    log.info("saved raw response -> %s", OUT)

    cols = ["ranking", "name", "apps", "goal", "shotsPerGame", "possession",
            "passSuccess", "rating"]
    cols = [c for c in cols if c in rows[0]]
    header = {"ranking": "#", "name": "team", "apps": "pl", "goal": "GF",
              "shotsPerGame": "shots/g", "possession": "poss%",
              "passSuccess": "pass%", "rating": "rating"}
    print()
    print("  ".join(f"{header[c]:>9}" for c in cols))
    for r in rows:
        out = []
        for c in cols:
            v = r.get(c, "")
            if c in ("possession", "passSuccess") and isinstance(v, float):
                v = f"{v * 100:.1f}"
            elif isinstance(v, float):
                v = f"{v:.2f}"
            out.append(f"{str(v):>9}")
        print("  ".join(out))


if __name__ == "__main__":
    main()
