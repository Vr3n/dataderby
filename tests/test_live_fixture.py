"""The committed live fixture satisfies the contract end to end."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from dataderby.canonical import fingerprint
from dataderby.config import StageSpec, load_settings
from dataderby.contract import SECTIONS, VIEWS
from dataderby.db import connect, migrate
from dataderby.fetch import Capture, feed_url
from dataderby.landing import LandingResult
from dataderby.page import PageCapture
from dataderby.parse import build_candidate
from dataderby.parse_standings import check_team_sets, parse_views
from dataderby.publish import Outcome, publish
from dataderby.standings import decode_view

_FIXTURE = Path("tests/fixtures/whoscored/epl-2026-2027-25544")
_SPEC = load_settings(Path("config/stages.toml")).stages["epl-2026-2027"]


def _manifest() -> dict[str, object]:
    return json.loads((_FIXTURE / "manifest.json").read_text(encoding="utf-8"))


def _captured_at() -> datetime:
    return datetime.fromisoformat(str(_manifest()["captured_at"]))


def _load(spec: StageSpec) -> tuple[PageCapture, tuple[Capture, ...]]:
    moment = _captured_at()
    standings = {
        view: decode_view((_FIXTURE / f"standings__{view}.json").read_bytes()) for view in VIEWS
    }
    page = PageCapture(
        html="",
        token="",
        stages=(),
        standings=standings,
        captured_at=moment,
        url=spec.whoscored_page_url,
    )
    feeds = tuple(
        Capture(
            section=section,
            view=view,
            body=(_FIXTURE / f"{section}__{view}.json").read_bytes(),
            captured_at=moment,
            content_type="application/json",
            url=feed_url(spec, section, view),
            status=200,
            attempt=1,
        )
        for section in SECTIONS
        for view in VIEWS
    )
    return page, feeds


def test_every_fixture_file_matches_its_manifest_checksum() -> None:
    manifest = _manifest()
    files = manifest["files"]
    assert isinstance(files, dict)

    for name, digest in files.items():
        body = (_FIXTURE / str(name)).read_bytes()
        assert hashlib.sha256(body).hexdigest() == digest, name


def test_the_fixture_contains_no_credentials_or_headers() -> None:
    forbidden = ("model-last-mode", "gsiteheadervalue", "cf_clearance", "set-cookie")

    for path in _FIXTURE.glob("*.json"):
        text = path.read_text(encoding="utf-8").lower()
        for marker in forbidden:
            assert marker not in text, f"{path.name} contains {marker}"


def test_the_live_capture_forms_a_complete_twenty_team_candidate() -> None:
    page, feeds = _load(_SPEC)

    candidate = build_candidate(list(feeds), _SPEC)
    standings = parse_views(page, _SPEC)
    check_team_sets(candidate, standings)

    assert len(candidate.rows) == 20
    assert len(standings.rows) == 20
    assert "Manchester City" in {row.whoscored_team_name for row in candidate.rows}
    assert all(len(row.measures) == 60 for row in candidate.rows)


def test_the_live_capture_publishes_and_records_its_fingerprint(tmp_path: Path) -> None:
    page, feeds = _load(_SPEC)
    candidate = build_candidate(list(feeds), _SPEC)
    standings = parse_views(page, _SPEC)
    moment = _captured_at()
    run = LandingResult(
        run_id="run_live_fixture",
        observed_at=moment,
        page=page,
        feeds=feeds,
        raw_files=(),
    )

    con = connect(tmp_path / "live.duckdb")
    try:
        migrate(con)
        outcome = publish(con, candidate, standings, _SPEC, run)
        stored = con.execute("SELECT content_fingerprint FROM competition_snapshot").fetchone()
        teams = con.execute("SELECT count(*) FROM fact_team_snapshot").fetchone()
    finally:
        con.close()

    assert outcome is Outcome.ACCEPTED
    assert stored is not None
    assert stored[0] == fingerprint(candidate, standings)
    assert teams == (20,)


def test_the_committed_fixture_is_pinned() -> None:
    page, feeds = _load(_SPEC)
    candidate = build_candidate(list(feeds), _SPEC)
    standings = parse_views(page, _SPEC)

    assert fingerprint(candidate, standings) == (
        "ddd500267e1134f8df4506cb13d7efe8b5d02cbeaac082bd78ffdb3448cec5ea"
    )
