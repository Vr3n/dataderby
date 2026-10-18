"""Team-statistics scraper for WhoScored.

The statistics feed is fronted by a fingerprint gate that blocks every client
_tailored_ request (curl_cffi even with browser cookies, and *any* hand-built
``fetch()`` from inside the page). The only requests that pass are the ones the
site's own JS makes while you drive its UI. So we drive the real page with
Patchright's stealth Chromium and harvest the feed JSON from the network layer:

  patchright headless chromium + --disable-blink-features=AutomationControlled
  + explicit Chrome user agent + locale en-US  -> passes Cloudflare (retry on
  block, the doc-level challenge is intermittent).

For each of the three sections (summary/defensive/offensive) we click the tab,
then each view (Overall/Home/Away) scoped to that section's own filter panel.
Each click makes the app issue ``/statisticsfeed/1/getteamstatistics`` with the
section carried in ``subcategory`` (``all``/``defensive``/``offensive``) and the
view in ``field``; we read the network responses and keep the JSON ones.

Deliberate simplifications:

- One season at a time; the caller passes the full teamstatistics stage URL
  (ids are parsed from it, matching the plan's ``(tournament_id, season_key)``
  composite key).
- Output is one JSON document per season of wide rows, one row per team, with
  per-view columns prefixed ``<section>_<view>_<field>`` (lower-cased section
  and view), decimals rounded to two places, and the Whoscored ids carried as
  ``whoscored_*`` provenance plus a top-level ``source``.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

from patchright.sync_api import sync_playwright

log = logging.getLogger("dataderby.scraper")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

# section -> the subcategory the feed uses for it
SECTIONS: dict[str, str] = {
    "summary": "all",
    "defensive": "defensive",
    "offensive": "offensive",
}
VIEWS = ["Home", "Away", "Overall"]  # end on Overall so it always refires
MAX_ATTEMPTS = 4

_STAGE_URL_RE = re.compile(
    r"/regions/(\d+)/tournaments/(\d+)/seasons/(\d+)/stages/(\d+)/(?:[^/?#]+/)?([^/?#]+)$"
)


class ScraperError(RuntimeError):
    pass


def parse_stage_url(url: str) -> dict:
    """Extract the identifiers a stage teamstatistics URL encodes.

    Returns region_id, tournament_id, season_id, stage_id, slug, season_key.
    The season_key is ``<start>-<end>`` pulled from the slug tail (the canonical
    key fixed by ADR 0003); it falls back to the slug when the tail isn't two
    4-digit years.
    """
    m = _STAGE_URL_RE.search(url)
    if not m:
        raise ScraperError(f"not a stage teamstatistics URL: {url}")
    region_id, tournament_id, season_id, stage_id, slug = m.groups()
    parts = slug.split("-")
    if len(parts) >= 2 and all(len(p) == 4 and p.isdigit() for p in parts[-2:]):
        season_key = f"{parts[-2]}-{parts[-1]}"
    else:
        season_key = slug
    return {
        "whoscored_region_id": int(region_id),
        "whoscored_tournament_id": int(tournament_id),
        "whoscored_season_id": int(season_id),
        "whoscored_stage_id": int(stage_id),
        "slug": slug,
        "season_key": season_key,
    }


def _open_valid_page(pw, url: str, *, wait_after_load: float = 5.0):
    """Launch a stealth context and open the page, retrying past a Cloudflare
    doc-level block (title "Attention Required!").
    """
    for _ in range(MAX_ATTEMPTS):
        browser = pw.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        ctx = browser.new_context(user_agent=USER_AGENT, locale="en-US")
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(int(wait_after_load * 1000))
        if "Attention Required" not in page.title():
            return browser, ctx, page
        browser.close()
    raise ScraperError("Cloudflare block not passed after retries")


def capture_feed(page, *, delay: float = 1.8):
    """Drive the UI through every (section, view) and return the matching JSON
    feed payloads: a list of dicts {subcategory, field, statColumns, rows}.
    """
    got: list[dict] = []

    def on_response(response) -> None:  # noqa: ANN001
        if "statisticsfeed" not in response.url:
            return
        raw = response.body().lstrip(b"\xef\xbb\xbf").lstrip()
        if raw[:1] not in (b"{", b"["):
            return  # the oddschecker gate page, not JSON
        payload = json.loads(raw)
        qs = response.url.split("?", 1)[1]
        params = dict(p.split("=", 1) for p in qs.split("&") if "=" in p)
        got.append(
            {
                "subcategory": params.get("subcategory"),
                "field": params.get("field"),
                "statColumns": payload.get("statColumns", []),
                "rows": payload.get("teamTableStats") or [],
            }
        )

    page.context.on("response", on_response)

    for section, _sub in SECTIONS.items():
        if section != "summary":
            tab = page.locator(f"a[href='#stage-team-stats-{section}']")
            if tab.count():
                tab.first.evaluate("el => el.click()")
                page.wait_for_timeout(2500)  # let the section panel render
        panel = f"#stage-team-stats-{section}"
        for view in VIEWS:
            opt = page.locator(f"{panel} dl#field a[data-value='{view}']")
            if opt.count():
                opt.first.evaluate("el => el.click()")
                page.wait_for_timeout(int(delay * 1000))

    page.context.remove_listener("response", on_response)
    return got


def _round(value):  # noqa: ANN001, ANN202
    """Round decimals to two places; leave ints/bools/None untouched."""
    return round(value, 2) if isinstance(value, float) else value


def wide_rows(captures: list[dict]) -> list[dict]:
    """Fold captured feed rows into one wide row per team.

    Identity (team_id/team_name/rating) is carried from the first row a team
    appears in; every section-view field becomes ``<section>_<view>_<field>``
    (lower-cased section and view), rounded to two decimals, trusting each
    response's own ``statColumns`` (ADR 0001).
    """
    by_team: dict[int, dict] = {}
    for c in captures:
        section = next(s for s, sub in SECTIONS.items() if sub == c["subcategory"])
        view = c["field"].lower()
        fields = c["statColumns"]
        for r in c["rows"]:
            row = by_team.setdefault(
                r["teamId"],
                {
                    "team_id": r["teamId"],
                    "team_name": r["teamName"],
                    "rating": _round(r["rating"]),
                },
            )
            for f in fields:
                row[f"{section}_{view}_{f}"] = _round(r[f])
    return [by_team[t] for t in sorted(by_team)]


def _assert_complete(captures: list[dict]) -> None:
    have = {(c["subcategory"], c["field"]) for c in captures}
    want = {(sub, view) for sub in SECTIONS.values() for view in VIEWS}
    missing = want - have
    if missing:
        raise ScraperError(f"missing feed combos after sweep: {sorted(missing)}")


def scrape_team_statistics(stage_url: str, *, out_dir="data") -> Path:
    """Scrape one season's team statistics and write the wide rows to JSON."""
    meta = parse_stage_url(stage_url)
    with sync_playwright() as pw:
        browser, ctx, page = _open_valid_page(pw, stage_url)
        try:
            captures = capture_feed(page)
        finally:
            browser.close()
    _assert_complete(captures)
    doc = {"source": "whoscored", **meta, "rows": wide_rows(captures)}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{meta['whoscored_tournament_id']}_{meta['season_key']}.json"
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    log.info("wrote %s (%d teams)", path, len(doc["rows"]))
    return path


def _selfcheck() -> None:
    """Offline check of the pure logic against captured samples (no browser)."""
    caps_dir = Path("recon") / "caps"
    if not caps_dir.exists():
        return
    captures = []
    for f in caps_dir.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        captures.append(
            {
                "subcategory": f.stem.split("__")[0],
                "field": f.stem.split("__")[1],
                "statColumns": d.get("statColumns", []),
                "rows": d.get("teamTableStats") or [],
            }
        )
    rows = wide_rows(captures)
    assert rows, "selfcheck: no rows"
    leader = next(r for r in rows if r["team_id"] == 65)
    assert leader["summary_overall_goal"] == 31.0, leader.get("summary_overall_goal")
    assert "defensive_away_shotsConcededPerGame" in leader
    assert "ranking" not in leader
    print(f"selfcheck ok: {len(rows)} teams, {len(rows[0]) - 3} stat columns")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _selfcheck()