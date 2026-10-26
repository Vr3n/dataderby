"""Capture and validate every configured stage. Operator tool, not pipeline code.

For each stage it opens the stage page once, reads the token and the three
standings views, fetches the nine feeds in that page's session, validates every
envelope, parses, and publishes into a scratch database. Failures are recorded
and the sweep continues, so one bad league does not hide the others.

Raw payloads go to ``data/live-audit/<stamp>/<stage>/`` (git-ignored). The
summary goes to ``results.json`` next to them and is printed at the end.

Usage::

    uv run python scripts/audit_all_stages.py --out data/live-audit
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from patchright.sync_api import TimeoutError as PlaywrightTimeout
from patchright.sync_api import sync_playwright

from dataderby.canonical import fingerprint
from dataderby.config import StageSpec, load_settings
from dataderby.contract import SECTIONS, VIEWS
from dataderby.db import connect, migrate
from dataderby.fetch import Capture, FetchError, parse_envelope
from dataderby.landing import LandingResult
from dataderby.page import _STANDINGS_JS, _TOKEN_RE, _rows_from_js
from dataderby.parse import build_candidate
from dataderby.parse_standings import check_team_sets, parse_views
from dataderby.publish import publish
from dataderby.standings import encode_view
from dataderby.validate import PublishBlocked

_PACE_MS = 1200
_AUDIT_DB: Any = None
_FETCH_JS = """
async (args) => {
  const out = {};
  let first = true;
  for (const [key, url] of Object.entries(args.urls)) {
    if (!first) await new Promise((resolve) => setTimeout(resolve, args.pace));
    first = false;
    const started = performance.now();
    const response = await fetch(url, {
      headers: {'Model-last-Mode': args.token, 'X-Requested-With': 'XMLHttpRequest'},
      credentials: 'include'
    });
    out[key] = {
      status: response.status,
      type: response.headers.get('content-type'),
      body: await response.text(),
      ms: performance.now() - started
    };
  }
  return out;
}
"""


def _feed_url(spec: StageSpec, section: str, view: str) -> str:
    from urllib.parse import urlencode

    from dataderby.fetch import _FIELD, _SUBCATEGORY

    query = urlencode(
        {
            "stageId": spec.whoscored_stage_id,
            "category": "summaryteam",
            "subcategory": _SUBCATEGORY[section],
            "field": _FIELD[view],
            "statsAccumulationType": 0,
            "tournamentOptions": spec.whoscored_tournament_id,
            "numberOfTeamsToPick": spec.expected_teams,
            "isCurrent": "true",
            "sortBy": "Rating",
        }
    )
    return f"https://www.whoscored.com/statisticsfeed/1/getteamstatistics?{query}"


def _read_standings(page: Any) -> tuple[dict[str, tuple[Any, ...]], list[str]]:
    toggles: list[str] = []
    standings: dict[str, tuple[Any, ...]] = {}
    for view in VIEWS:
        selector = f'a.option[data-source="{view}"]'
        toggle = page.locator(selector)
        if toggle.count():
            toggles.append(view)
            toggle.first.click()
            page.wait_for_timeout(400)
        standings[view] = _rows_from_js(page.evaluate(_STANDINGS_JS))
    return standings, toggles


def _capture_stage(page: Any, spec: StageSpec, out_dir: Path) -> dict[str, Any]:
    started = time.monotonic()
    record: dict[str, Any] = {
        "stage": spec.key,
        "teams_expected": spec.expected_teams,
        "feeds": {},
        "toggles": [],
    }

    page.goto(spec.whoscored_page_url, wait_until="domcontentloaded", timeout=45_000)
    try:
        page.wait_for_selector("table[id^='standings-']", timeout=45_000)
        record["has_table"] = True
    except PlaywrightTimeout:
        record["has_table"] = False
    page.wait_for_timeout(1_000)

    html = page.content()
    token = _TOKEN_RE.search(html)
    if token is None:
        record["error"] = "no gSiteHeaderValue"
        return record

    standings, toggles = _read_standings(page)
    record["toggles"] = toggles
    record["standings_rows"] = {view: len(rows) for view, rows in standings.items()}

    urls = {
        f"{section}/{view}": _feed_url(spec, section, view)
        for section in SECTIONS
        for view in VIEWS
    }
    fetched = page.evaluate(_FETCH_JS, {"urls": urls, "token": token.group(1), "pace": _PACE_MS})

    feeds: list[Capture] = []
    for section in SECTIONS:
        for view in VIEWS:
            key = f"{section}/{view}"
            item = fetched[key]
            body = str(item["body"]).encode("utf-8")
            entry: dict[str, Any] = {
                "status": int(item["status"]),
                "type": item["type"],
                "bytes": len(body),
                "ms": round(float(item["ms"]), 1),
            }
            try:
                payload = parse_envelope(body, section, view)
                entry["cols"] = len(payload.get("statColumns", []))
                entry["teams"] = len(payload.get("teamTableStats", []))
            except FetchError as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
                record["feeds"][key] = entry
                continue
            record["feeds"][key] = entry
            feeds.append(
                Capture(
                    section=section,
                    view=view,
                    body=body,
                    captured_at=datetime.now(UTC),
                    content_type=item["type"],
                    url=urls[key],
                    status=int(item["status"]),
                    attempt=1,
                )
            )

    stage_dir = out_dir / spec.key
    stage_dir.mkdir(parents=True, exist_ok=True)
    for capture in feeds:
        (stage_dir / f"{capture.section}__{capture.view}.json").write_bytes(capture.body)
    for view, rows in standings.items():
        (stage_dir / f"standings__{view}.json").write_bytes(encode_view(view, rows))

    if len(feeds) != 9:
        record["error"] = f"only {len(feeds)} of 9 feeds parsed"
        record["duration_s"] = round(time.monotonic() - started, 1)
        return record

    try:
        candidate = build_candidate(feeds, spec)
        parsed_standings = parse_views(_page_for(spec, standings), spec)
        check_team_sets(candidate, parsed_standings)
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["duration_s"] = round(time.monotonic() - started, 1)
        return record

    record["teams_feed"] = len(candidate.rows)
    record["teams_standings"] = len(parsed_standings.rows)
    record["is_opta"] = candidate.is_opta
    record["null_measures"] = sum(
        1 for row in candidate.rows for value in row.measures.values() if value is None
    )
    record["name_mismatches"] = _name_mismatches(candidate, parsed_standings)
    record["deductions"] = _deductions(parsed_standings)
    record["fingerprint"] = fingerprint(candidate, parsed_standings)
    record["duration_s"] = round(time.monotonic() - started, 1)

    run = LandingResult(
        run_id=f"audit_{spec.key}",
        observed_at=min(capture.captured_at for capture in feeds),
        page=_page_for(spec, standings),
        feeds=tuple(feeds),
        raw_files=(),
    )
    try:
        outcome = publish(_AUDIT_DB, candidate, parsed_standings, spec, run)
        record["outcome"] = outcome.value
    except PublishBlocked as exc:
        record["outcome"] = "blocked"
        record["error"] = "; ".join(
            f"{failure.assertion_id}: {failure.message}" for failure in exc.failures
        )
    except Exception as exc:
        record["outcome"] = "error"
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def _page_for(spec: StageSpec, standings: dict[str, tuple[Any, ...]]) -> Any:
    from dataderby.page import PageCapture

    return PageCapture(
        html="",
        token="",
        stages=(),
        standings=standings,
        captured_at=datetime.now(UTC),
        url=spec.whoscored_page_url,
    )


def _deductions(standings: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for row in standings.rows:
        measures = row.measures
        points = measures.get("points_overall")
        won = measures.get("won_overall")
        drawn = measures.get("drawn_overall")
        if points is None or won is None or drawn is None:
            continue
        calculated = 3 * int(won) + int(drawn)
        if int(points) != calculated:
            found.append(
                {
                    "team_id": row.whoscored_team_id,
                    "name": row.whoscored_team_name,
                    "points": int(points),
                    "calculated": calculated,
                    "delta": int(points) - calculated,
                }
            )
    return found


def _name_mismatches(candidate: Any, standings: Any) -> list[dict[str, str]]:
    names = {row.whoscored_team_id: row.whoscored_team_name for row in standings.rows}
    return [
        {
            "team_id": str(row.whoscored_team_id),
            "feed": row.whoscored_team_name,
            "standings": names.get(row.whoscored_team_id, ""),
        }
        for row in candidate.rows
        if names.get(row.whoscored_team_id) not in (None, row.whoscored_team_name)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/stages.toml"))
    parser.add_argument("--out", type=Path, default=Path("data/live-audit"))
    parser.add_argument("--stage", action="append", help="limit to one or more keys")
    args = parser.parse_args()

    settings = load_settings(args.config)
    keys = args.stage or sorted(settings.stages)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_dir = args.out / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    global _AUDIT_DB
    _AUDIT_DB = connect(out_dir / "audit.duckdb")
    migrate(_AUDIT_DB)

    results: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()
        try:
            for key in keys:
                print(f"-> {key}", flush=True)
                try:
                    results.append(_capture_stage(page, settings.stages[key], out_dir))
                except Exception as exc:
                    results.append({"stage": key, "error": f"{type(exc).__name__}: {exc}"})
                last = results[-1]
                print(
                    f"  {last.get('outcome', 'ERROR')} "
                    f"teams={last.get('teams_feed', '?')} "
                    f"{last.get('error', '')}",
                    flush=True,
                )
        finally:
            browser.close()
            _AUDIT_DB.close()

    (out_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print()
    print(f"{'STAGE':32} {'TEAMS':>5} {'EXP':>4} {'OUTCOME':9} ERROR")
    for item in results:
        print(
            f"{item['stage']:32} {item.get('teams_feed', '?'):>5} "
            f"{item.get('teams_expected', '?'):>4} {item.get('outcome', 'error'):9} "
            f"{item.get('error', '')[:70]}"
        )
    print(f"\nresults: {out_dir / 'results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
