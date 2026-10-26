"""Capture one live WhoScored stage into a redacted fixture directory.

This is an operator tool, not part of the pipeline. It exists because the feed
endpoint is bound to the browser's verified session: a plain HTTP request returns
the site's 404 shell. The tool opens one headed browser, reads the stage page
(standings and token), then calls the statistics feed from the site's own
``/statistics`` page, where the session is valid.

Usage::

    uv run python scripts/capture_live_stage.py --stage epl-2026-2027 \
        --out tests/fixtures/whoscored/epl-25544

The output contains the three standings views and the nine feed payloads, plus a
manifest with a SHA-256 per file. No token, cookie, or header is written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from patchright.sync_api import sync_playwright

from dataderby.config import StageSpec, load_settings
from dataderby.contract import EXPECTED_STAT_COLUMNS, SECTIONS, VIEWS
from dataderby.fetch import parse_envelope
from dataderby.page import (
    _STANDINGS_JS,
    _TOKEN_RE,
    _rows_from_js,
)
from dataderby.standings import encode_view

_STATISTICS_URL = "https://www.whoscored.com/statistics"
_FEED_URL = "https://www.whoscored.com/statisticsfeed/1/getteamstatistics"
_SUBCATEGORY = {"summary": "all", "defensive": "defensive", "offensive": "offensive"}
_FIELD = {"overall": "Overall", "home": "Home", "away": "Away"}
_FORBIDDEN = ("model-last-mode", "gSiteHeaderValue", "cf_clearance", "set-cookie", "cookie:")


def _feed_url(spec: StageSpec, section: str, view: str) -> str:
    params = {
        "category": "summaryteam",
        "subcategory": _SUBCATEGORY[section],
        "statsAccumulationType": "0",
        "field": _FIELD[view],
        "tournamentOptions": str(spec.whoscored_tournament_id),
        "timeOfTheGameStart": "",
        "timeOfTheGameEnd": "",
        "teamIds": "",
        "stageId": str(spec.whoscored_stage_id),
        "sortBy": "Rating",
        "sortAscending": "",
        "page": "",
        "numberOfTeamsToPick": str(spec.expected_teams),
        "isCurrent": "true",
        "formation": "",
        "incPens": "",
        "against": "",
    }
    return f"{_FEED_URL}?{urlencode(params)}"


def _read_standings(page: Any) -> dict[str, tuple[Any, ...]]:
    standings: dict[str, tuple[Any, ...]] = {}
    for view in VIEWS:
        toggle = page.locator(f'a.option[data-source="{view}"]')
        if toggle.count():
            toggle.first.click()
            page.wait_for_timeout(400)
        items = page.evaluate(_STANDINGS_JS)
        standings[view] = _rows_from_js(items)
    return standings


def _fetch_feeds(page: Any, spec: StageSpec, token: str) -> dict[str, bytes]:
    urls = {
        f"{section}/{view}": _feed_url(spec, section, view)
        for section in SECTIONS
        for view in VIEWS
    }
    result = page.evaluate(
        """async (args) => {
            const out = {};
            for (const [key, url] of Object.entries(args.urls)) {
                const response = await fetch(url, {
                    headers: {
                        'Model-last-Mode': args.token,
                        'Accept': 'application/json, text/javascript, */*; q=0.01',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    credentials: 'include'
                });
                out[key] = {status: response.status, body: await response.text()};
            }
            return out;
        }""",
        {"urls": urls, "token": token},
    )

    bodies: dict[str, bytes] = {}
    for section in SECTIONS:
        for view in VIEWS:
            key = f"{section}/{view}"
            status = int(result[key]["status"])
            body = str(result[key]["body"])
            if status != 200:
                raise SystemExit(f"{key}: HTTP {status}")
            raw = body.encode("utf-8")
            parse_envelope(raw, section, view)
            want = len(EXPECTED_STAT_COLUMNS[(section, view)])
            got = len(json.loads(raw)["statColumns"])
            if got != want:
                raise SystemExit(f"{key}: {got} statColumns, expected {want}")
            bodies[key] = raw
    return bodies


def _write(path: Path, body: bytes) -> str:
    path.write_bytes(body)
    return hashlib.sha256(body).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, help="stage key from config/stages.toml")
    parser.add_argument("--config", type=Path, default=Path("config/stages.toml"))
    parser.add_argument("--out", type=Path, required=True, help="fixture directory")
    parser.add_argument("--force", action="store_true", help="overwrite an existing fixture")
    args = parser.parse_args()

    spec = load_settings(args.config).stages[args.stage]
    if args.out.exists() and not args.force:
        raise SystemExit(f"fixture already exists: {args.out} (use --force)")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()
        try:
            page.goto(spec.whoscored_page_url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_selector("table[id^='standings-']", timeout=45_000)
            page.wait_for_timeout(1_000)
            standings = _read_standings(page)

            page.goto(_STATISTICS_URL, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(6_000)
            stats_html = page.content()
            match = _TOKEN_RE.search(stats_html)
            if match is None:
                raise SystemExit("statistics page did not expose gSiteHeaderValue")
            feeds = _fetch_feeds(page, spec, match.group(1))
        finally:
            browser.close()

    args.out.mkdir(parents=True, exist_ok=True)
    captured_at = datetime.now(UTC).isoformat()
    manifest: dict[str, Any] = {
        "stage": spec.key,
        "whoscored_tournament_id": spec.whoscored_tournament_id,
        "whoscored_season_id": spec.whoscored_season_id,
        "whoscored_stage_id": spec.whoscored_stage_id,
        "expected_teams": spec.expected_teams,
        "captured_at": captured_at,
        "files": {},
    }

    for section in SECTIONS:
        for view in VIEWS:
            body = feeds[f"{section}/{view}"]
            manifest["files"][f"{section}__{view}.json"] = _write(
                args.out / f"{section}__{view}.json", body
            )

    for view, rows in standings.items():
        manifest["files"][f"standings__{view}.json"] = _write(
            args.out / f"standings__{view}.json", encode_view(view, rows)
        )

    for name in manifest["files"]:
        text = (args.out / name).read_text(encoding="utf-8").lower()
        for marker in _FORBIDDEN:
            if marker.lower() in text:
                raise SystemExit(f"{name} contains a forbidden marker: {marker}")

    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"stage: {spec.key} ({spec.whoscored_stage_id})")
    print(f"standings: {', '.join(f'{view}={len(rows)}' for view, rows in standings.items())}")
    print(f"feeds: {len(feeds)} files")
    print(f"fixture: {args.out}")
    print(
        f"teams in summary/overall: {len(json.loads(feeds['summary/overall'])['teamTableStats'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
