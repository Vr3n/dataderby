"""Operator command line: run, probe, replay, verify, freshness, stages.

The CLI is the only place that composes the pipeline. Every step it calls is a
tested module; this file owns the order, the lock, the exit codes, and the
operator-facing output.

Exit codes are fixed by ``plans/v1-build-plan.md`` §11:

===== ==========================================================
0     ok, or ``no_change``
2     a feed could not be fetched
3     publish or parse was blocked
4     configuration or usage
5     another process holds the pipeline lock
6     internal failure, or a verification mismatch
===== ==========================================================
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any, NoReturn, TextIO
from uuid import uuid4

import duckdb

from dataderby.canonical import fingerprint
from dataderby.config import Settings, StageSpec, load_settings
from dataderby.contract import SECTIONS, VIEWS, View
from dataderby.db import MigrationError, connect, migrate
from dataderby.fetch import Capture, FetchBlocked, FetchError, RequestBudget, SchemaDrift
from dataderby.landing import LandingResult, land_stage
from dataderby.lock import LockHeld, exclusive_lock
from dataderby.observe import log as log_event
from dataderby.page import PageCapture, StageCapture, capture_stage
from dataderby.parse import (
    IncompleteCohort,
    OwnershipMismatch,
    SourceParseError,
    build_candidate,
    parse_capture,
)
from dataderby.parse_standings import check_team_sets, parse_views
from dataderby.publish import Outcome, publish, reconcile
from dataderby.schedule import STALE_AFTER_HOURS, evaluate_freshness
from dataderby.standings import RawStandingsRow, StandingsParseError, decode_view
from dataderby.validate import (
    AssertionFailure,
    PublishBlocked,
    blocking_failures,
    run_assertions,
)

_DEFAULT_CONFIG = Path("config/stages.toml")
_PAGE_SECTION = "page"
_PAGE_VIEW = "show"
_STANDINGS_SECTION = "standings"


class Exit(IntEnum):
    """Process exit codes; see the module docstring."""

    OK = 0
    FETCH_FAILED = 2
    BLOCKED = 3
    CONFIG = 4
    LOCKED = 5
    INTERNAL = 6


class ConfigError(ValueError):
    """Raised for a bad path, bad stage key, or invalid configuration."""


@dataclass(slots=True)
class Runtime:
    """The browser effect the CLI cannot own: one page plus its feeds."""

    sweep: Callable[..., StageCapture] = capture_stage


class _Parser(argparse.ArgumentParser):
    """Turn usage errors into exit code 4 instead of argparse's default 2."""

    def error(self, message: str) -> NoReturn:
        raise ConfigError(message)


def _load(path: Path) -> Settings:
    try:
        return load_settings(path)
    except (OSError, ValueError) as exc:
        raise ConfigError(str(exc)) from exc


def _lock_path(settings: Settings) -> Path:
    return settings.db_path.parent / "pipeline.lock"


def _keys(settings: Settings, key: str | None) -> list[str]:
    if key is None:
        return sorted(settings.stages)
    if key not in settings.stages:
        available = ", ".join(sorted(settings.stages))
        raise ConfigError(f"unknown stage {key!r}; configured: {available}")
    return [key]


def _say(out: TextIO, message: str = "") -> None:
    print(message, file=out)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="dataderby", description="WhoScored pipeline operations.")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    def with_config(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", type=Path, default=_DEFAULT_CONFIG)

    run = sub.add_parser("run", help="capture, parse, validate, and publish one or more stages")
    with_config(run)
    run.add_argument("--stage", help="stage key; default is every configured stage")
    run.add_argument("--allow-apps-decrease", action="store_true", help="explicit A10 override")
    run.add_argument("--dry-run", action="store_true", help="capture and validate without writing")

    probe = sub.add_parser("probe", help="capture the page and one summary feed; no writes")
    with_config(probe)
    probe.add_argument("--stage", help="stage key; default is every configured stage")

    replay = sub.add_parser("replay", help="rebuild a candidate from a raw bundle")
    with_config(replay)
    source = replay.add_mutually_exclusive_group(required=True)
    source.add_argument("--run-id", help="replay the raw bundle recorded by this run")
    source.add_argument("--raw-dir", type=Path, help="replay an explicit raw bundle")
    replay.add_argument(
        "--check", action="store_true", help="compare with the published fingerprint"
    )

    verify = sub.add_parser("verify", help="check headers, facts, edges, and addresses")
    with_config(verify)
    verify.add_argument("--snapshot", help="limit the per-snapshot checks to one snapshot id")
    verify.add_argument(
        "--address",
        nargs=2,
        metavar=("STAGE", "OBSERVED_AT"),
        help="limit the per-snapshot checks to one stage address",
    )

    freshness = sub.add_parser("freshness", help="read v_pipeline_freshness")
    with_config(freshness)
    freshness.add_argument("--json", action="store_true", help="machine-readable output")
    freshness.add_argument(
        "--check",
        action="store_true",
        help="exit 6 when any stage is stale; see --max-age-hours",
    )
    freshness.add_argument(
        "--max-age-hours",
        type=float,
        default=STALE_AFTER_HOURS,
        help=(
            "staleness ceiling in hours for --check "
            f"(default {STALE_AFTER_HOURS}, provisional until E5 measures the lag)"
        ),
    )

    stages = sub.add_parser("stages", help="inspect the stage registry")
    with_config(stages)
    stages.add_argument("action", choices=["list"])

    return parser


def _stages_list(settings: Settings, out: TextIO) -> Exit:
    header = (
        f"{'KEY':24} {'COMPETITION':22} {'SEASON':10} {'STAGE':12} {'TEAMS':>5} {'STAGE_ID':>8}"
    )
    _say(out, header)
    for key in sorted(settings.stages):
        spec = settings.stages[key]
        _say(
            out,
            f"{spec.key:24} {spec.competition:22} {spec.season_key:10} "
            f"{spec.stage:12} {spec.expected_teams:5} {spec.whoscored_stage_id:8}",
        )
    return Exit.OK


def _freshness(
    settings: Settings,
    as_json: bool,
    out: TextIO,
    *,
    check: bool = False,
    max_age_hours: float = STALE_AFTER_HOURS,
) -> Exit:
    if not settings.db_path.exists():
        raise ConfigError(f"database does not exist: {settings.db_path}")
    if check and max_age_hours <= 0:
        raise ConfigError(f"--max-age-hours must be positive, got {max_age_hours}")

    con = connect(settings.db_path, read_only=True)
    try:
        rows = con.execute(
            """
            SELECT
                whoscored_tournament_id,
                whoscored_season_id,
                whoscored_stage_id,
                last_success_at,
                age_seconds,
                last_outcome,
                attempt_count,
                accepted_snapshots
            FROM v_pipeline_freshness
            ORDER BY whoscored_tournament_id, whoscored_season_id, whoscored_stage_id
            """
        ).fetchall()
    finally:
        con.close()

    evaluated = evaluate_freshness(rows, max_age_seconds=max_age_hours * 3600) if check else ()
    by_stage = {
        (e.whoscored_tournament_id, e.whoscored_season_id, e.whoscored_stage_id): e
        for e in evaluated
    }

    if as_json:
        payload = [
            {
                "whoscored_tournament_id": row[0],
                "whoscored_season_id": row[1],
                "whoscored_stage_id": row[2],
                "last_success_at": row[3].isoformat() if row[3] else None,
                "age_seconds": row[4],
                "last_outcome": row[5],
                "attempt_count": row[6],
                "accepted_snapshots": row[7],
                **(
                    {
                        "stale": by_stage[(row[0], row[1], row[2])].stale,
                        "max_age_seconds": max_age_hours * 3600,
                    }
                    if check
                    else {}
                ),
            }
            for row in rows
        ]
        _say(out, json.dumps(payload, indent=2))
        if check and any(entry["stale"] for entry in payload):
            return Exit.INTERNAL
        return Exit.OK

    if not rows:
        _say(out, "no accepted snapshots")
        return Exit.INTERNAL if check else Exit.OK

    if check:
        header = (
            f"{'TOURNAMENT':>10} {'SEASON':>7} {'STAGE':>6} "
            f"{'AGE_S':>8} {'OUTCOME':12} {'SNAPSHOTS':>9} {'STATUS':6}"
        )
        _say(out, header)
        for row in rows:
            age = "-" if row[4] is None else str(row[4])
            outcome = row[5] or "-"
            status = "STALE" if by_stage[(row[0], row[1], row[2])].stale else "fresh"
            _say(
                out,
                f"{row[0]:10} {row[1]:7} {row[2]:6} {age:>8} {outcome:12} {row[7]:9} {status:6}",
            )
        stale = sum(1 for entry in evaluated if entry.stale)
        _say(out, f"{stale} of {len(evaluated)} stages stale (older than {max_age_hours:g} h)")
        return Exit.INTERNAL if stale else Exit.OK

    header = (
        f"{'TOURNAMENT':>10} {'SEASON':>7} {'STAGE':>6} "
        f"{'AGE_S':>8} {'OUTCOME':12} {'SNAPSHOTS':>9}"
    )
    _say(out, header)
    for row in rows:
        age = "-" if row[4] is None else str(row[4])
        outcome = row[5] or "-"
        _say(out, f"{row[0]:10} {row[1]:7} {row[2]:6} {age:>8} {outcome:12} {row[7]:9}")
    return Exit.OK


def _scope(
    snapshot: str | None, address: tuple[str, str] | None, settings: Settings
) -> tuple[str, list[Any]]:
    if snapshot:
        return "s.snapshot_id = ?", [snapshot]
    if address:
        key, observed = address
        spec = settings.stages.get(key)
        if spec is None:
            raise ConfigError(f"unknown stage {key!r}")
        try:
            when = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ConfigError(f"invalid OBSERVED_AT: {observed!r}") from exc
        return (
            "s.whoscored_tournament_id = ? AND s.whoscored_season_id = ? "
            "AND s.whoscored_stage_id = ? AND s.observed_at = ?",
            [
                spec.whoscored_tournament_id,
                spec.whoscored_season_id,
                spec.whoscored_stage_id,
                when,
            ],
        )
    return "1 = 1", []


def _verify(
    settings: Settings, snapshot: str | None, address: tuple[str, str] | None, out: TextIO
) -> Exit:
    if not settings.db_path.exists():
        raise ConfigError(f"database does not exist: {settings.db_path}")

    where, params = _scope(snapshot, address, settings)
    con = connect(settings.db_path, read_only=True)
    checks: list[tuple[str, int]] = []
    try:
        checks.append(
            (
                "headers without team facts",
                _scalar(
                    con,
                    f"""
                    SELECT count(*) FROM competition_snapshot s
                    WHERE {where}
                      AND NOT EXISTS (
                          SELECT 1 FROM fact_team_snapshot f
                          WHERE f.snapshot_id = s.snapshot_id
                      )
                    """,
                    params,
                ),
            )
        )
        checks.append(
            (
                "team facts without a header",
                _scalar(
                    con,
                    """
                    SELECT count(*) FROM fact_team_snapshot f
                    LEFT JOIN competition_snapshot s ON s.snapshot_id = f.snapshot_id
                    WHERE s.snapshot_id IS NULL
                    """,
                ),
            )
        )
        checks.append(
            (
                "standings facts without a header",
                _scalar(
                    con,
                    """
                    SELECT count(*) FROM fact_standings_snapshot f
                    LEFT JOIN competition_snapshot s ON s.snapshot_id = f.snapshot_id
                    WHERE s.snapshot_id IS NULL
                    """,
                ),
            )
        )
        checks.append(
            (
                "duplicate parent + fingerprint edges",
                _scalar(
                    con,
                    """
                    SELECT count(*) FROM (
                        SELECT parent_snapshot_id, content_fingerprint
                        FROM competition_snapshot
                        GROUP BY parent_snapshot_id, content_fingerprint
                        HAVING count(*) > 1
                    )
                    """,
                ),
            )
        )
        checks.append(
            (
                "duplicate stage addresses",
                _scalar(
                    con,
                    """
                    SELECT count(*) FROM (
                        SELECT whoscored_tournament_id, whoscored_season_id,
                               whoscored_stage_id, observed_at
                        FROM competition_snapshot
                        GROUP BY 1, 2, 3, 4
                        HAVING count(*) > 1
                    )
                    """,
                ),
            )
        )

        counts = con.execute(
            f"""
            SELECT s.snapshot_id, s.whoscored_stage_id, count(f.whoscored_team_id)
            FROM competition_snapshot s
            JOIN fact_team_snapshot f ON f.snapshot_id = s.snapshot_id
            WHERE {where}
            GROUP BY 1, 2
            """,
            params,
        ).fetchall()
    finally:
        con.close()

    by_stage = {spec.whoscored_stage_id: spec.expected_teams for spec in settings.stages.values()}
    wrong = [
        (snapshot_id, teams, by_stage[stage_id])
        for snapshot_id, stage_id, teams in counts
        if stage_id in by_stage and teams != by_stage[stage_id]
    ]
    checks.append(("snapshots with an unexpected team count", len(wrong)))

    failed = False
    for name, count in checks:
        status = "OK" if count == 0 else "FAIL"
        failed = failed or count != 0
        _say(out, f"{status:4} {name:38} {count}")

    for snapshot_id, teams, expected in wrong:
        _say(out, f"     {snapshot_id}: {teams} teams, expected {expected}")

    return Exit.INTERNAL if failed else Exit.OK


def _meta(path: Path) -> dict[str, Any]:
    meta_path = path.with_name(f"{path.name}.meta.json")
    try:
        payload: Any = json.loads(meta_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"raw file has no sidecar: {meta_path}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"raw sidecar is not an object: {meta_path}")
    return {str(key): value for key, value in payload.items()}


def _scalar(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> int:
    row = con.execute(sql, params or []).fetchone()
    return 0 if row is None else int(row[0])


def _read_bundle(directory: Path, spec: StageSpec) -> tuple[PageCapture, tuple[Capture, ...]]:
    page_path = directory / f"{_PAGE_SECTION}__{_PAGE_VIEW}.html"
    if not page_path.exists():
        raise ConfigError(f"raw bundle has no page payload: {page_path}")
    page_meta = _meta(page_path)

    standings: dict[View, tuple[RawStandingsRow, ...]] = {}
    for view in VIEWS:
        path = directory / f"{_STANDINGS_SECTION}__{view}.json"
        if path.exists():
            standings[view] = decode_view(path.read_bytes())

    page = PageCapture(
        html=page_path.read_text(encoding="utf-8"),
        token="",
        stages=(),
        standings=standings,
        captured_at=datetime.fromisoformat(page_meta["captured_at"]),
        url=str(page_meta["url"]),
    )

    feeds: list[Capture] = []
    for section in SECTIONS:
        for view in VIEWS:
            path = directory / f"{section}__{view}.json"
            if not path.exists():
                raise ConfigError(f"raw bundle is missing {section}/{view}: {path}")
            meta = _meta(path)
            feeds.append(
                Capture(
                    section=section,
                    view=view,
                    body=path.read_bytes(),
                    captured_at=datetime.fromisoformat(meta["captured_at"]),
                    content_type=meta.get("content_type"),
                    url=str(meta["url"]),
                    status=int(meta.get("status", 200)),
                    attempt=int(meta.get("attempt", 1)),
                )
            )
    return page, tuple(feeds)


def _spec_for_directory(directory: Path, settings: Settings) -> StageSpec:
    try:
        stage_id = int(directory.parent.name)
        season_id = int(directory.parent.parent.name)
        tournament_id = int(directory.parent.parent.parent.name)
    except ValueError as exc:
        raise ConfigError(f"not a raw bundle path: {directory}") from exc

    for spec in settings.stages.values():
        if (
            spec.whoscored_tournament_id == tournament_id
            and spec.whoscored_season_id == season_id
            and spec.whoscored_stage_id == stage_id
        ):
            return spec
    raise ConfigError(
        f"raw bundle address is not configured: tournament {tournament_id}, "
        f"season {season_id}, stage {stage_id}"
    )


def _resolve_run_dir(settings: Settings, run_id: str) -> Path:
    if not settings.db_path.exists():
        raise ConfigError(f"database does not exist: {settings.db_path}")
    con = connect(settings.db_path, read_only=True)
    try:
        rows = con.execute(
            "SELECT DISTINCT path FROM raw_capture WHERE run_id = ? ORDER BY path",
            [run_id],
        ).fetchall()
    finally:
        con.close()

    if not rows:
        raise ConfigError(f"no raw captures recorded for run {run_id}")

    parents = {Path(row[0]).parent for row in rows}
    if len(parents) != 1:
        raise ConfigError(f"run {run_id} spans more than one raw bundle")
    return parents.pop()


def _replay(
    settings: Settings,
    run_id: str | None,
    raw_dir: Path | None,
    check_only: bool,
    out: TextIO,
) -> Exit:
    directory = _resolve_run_dir(settings, run_id) if run_id else raw_dir
    if directory is None:
        raise ConfigError("one of --run-id or --raw-dir is required")

    spec = _spec_for_directory(directory, settings)
    page, feeds = _read_bundle(directory, spec)
    observed_at = min([page.captured_at, *(capture.captured_at for capture in feeds)])
    run = LandingResult(
        run_id=f"replay_{uuid4().hex}",
        observed_at=observed_at,
        page=page,
        feeds=feeds,
        raw_files=(),
    )
    candidate = build_candidate(list(feeds), spec)
    standings = parse_views(page, spec)
    check_team_sets(candidate, standings)
    replayed = fingerprint(candidate, standings)

    if check_only:
        if not settings.db_path.exists():
            raise ConfigError(f"database does not exist: {settings.db_path}")
        con = connect(settings.db_path, read_only=True)
        try:
            row = con.execute(
                """
                SELECT content_fingerprint
                FROM competition_snapshot
                WHERE whoscored_tournament_id = ?
                  AND whoscored_season_id = ?
                  AND whoscored_stage_id = ?
                  AND observed_at = ?
                ORDER BY accepted_at DESC
                LIMIT 1
                """,
                [
                    spec.whoscored_tournament_id,
                    spec.whoscored_season_id,
                    spec.whoscored_stage_id,
                    observed_at,
                ],
            ).fetchone()
        finally:
            con.close()

        if row is None:
            _say(out, f"MISMATCH no published snapshot at {observed_at.isoformat()}")
            return Exit.INTERNAL
        if row[0] != replayed:
            _say(out, f"MISMATCH published {row[0][:16]} replayed {replayed[:16]}")
            return Exit.INTERNAL
        _say(out, f"MATCH {replayed}")
        return Exit.OK

    with tempfile.TemporaryDirectory(prefix="dataderby-replay-") as tmp:
        con = connect(Path(tmp) / "replay.duckdb")
        try:
            migrate(con)
            outcome = publish(con, candidate, standings, spec, run)
            stored = con.execute("SELECT content_fingerprint FROM competition_snapshot").fetchone()
        finally:
            con.close()

    if outcome is not Outcome.ACCEPTED or stored is None or stored[0] != replayed:
        _say(out, f"MISMATCH scratch publish produced {stored!r}, expected {replayed}")
        return Exit.INTERNAL

    _say(out, f"REPLAYED {spec.key} {outcome.value} {replayed}")
    return Exit.OK


def _warning_lines(failure: AssertionFailure) -> list[str]:
    """Render one assertion failure for an operator.

    A points deduction is the common warning, so it gets a readable line with
    the reported total, the arithmetic expectation, and the gap. Every other
    failure keeps the generic assertion message.

    Args:
        failure: A failed assertion, including its offending rows.

    Returns:
        One or more lines, each already prefixed for the console.
    """
    if failure.assertion_id != "A22":
        return [f"  {failure.action.value} {failure.assertion_id}: {failure.message}"]

    lines: list[str] = []
    for team_id, name, reported, expected, adjustment in failure.rows:
        if not isinstance(adjustment, int):
            lines.append(f"  WARN A22: {failure.message}")
            continue
        lines.append(
            f"  WARN A22: {name} (team {team_id}) reports {reported} points, "
            f"expected {expected}, adjustment {adjustment:+d}"
        )
    return lines


def _warning_handler(
    settings: Settings,
    run: LandingResult,
    out: TextIO,
) -> Callable[[AssertionFailure], None]:
    """Build the publish warning sink: one durable log line and console lines."""

    def handle(failure: AssertionFailure) -> None:
        log_event(
            "publish.warning",
            log_dir=settings.log_dir,
            run_id=run.run_id,
            assertion_id=failure.assertion_id,
            action=failure.action.value,
            rows=[list(row) for row in failure.rows],
        )
        for line in _warning_lines(failure):
            _say(out, line)

    return handle


def _dry_run_one(
    spec: StageSpec,
    settings: Settings,
    runtime: Runtime,
    out: TextIO,
    budget: RequestBudget,
) -> Exit:
    stage = runtime.sweep(spec.whoscored_page_url, spec, budget=budget)
    page = stage.page
    feeds = stage.feeds
    observed_at = min([page.captured_at, *(capture.captured_at for capture in feeds)])
    run = LandingResult(
        run_id=f"dryrun_{uuid4().hex}",
        observed_at=observed_at,
        page=page,
        feeds=feeds,
        raw_files=(),
    )
    candidate = build_candidate(list(feeds), spec)
    standings = parse_views(page, spec)
    check_team_sets(candidate, standings)

    memory = duckdb.connect(":memory:")
    try:
        memory.execute("SET TimeZone='UTC'")
        migrate(memory)
        failures = run_assertions(memory, candidate, standings, spec, run)
    finally:
        memory.close()

    digest = fingerprint(candidate, standings)
    _say(
        out,
        f"{spec.key}: would publish {len(candidate.rows)} teams, "
        f"{len(standings.rows)} standings rows, fingerprint {digest[:16]}",
    )
    for failure in failures:
        for line in _warning_lines(failure):
            _say(out, line)
    if blocking_failures(failures):
        return Exit.BLOCKED
    return Exit.OK


def _run(
    settings: Settings,
    key: str | None,
    *,
    allow_apps_decrease: bool,
    dry_run: bool,
    runtime: Runtime,
    out: TextIO,
) -> Exit:
    keys = _keys(settings, key)
    budget = RequestBudget(limit=max(20, 9 * len(keys) * 2))

    if dry_run:
        for stage_key in keys:
            code = _dry_run_one(settings.stages[stage_key], settings, runtime, out, budget)
            if code is not Exit.OK:
                return code
        return Exit.OK

    with exclusive_lock(_lock_path(settings)):
        con = connect(settings.db_path)
        try:
            migrate(con)
            reconcile(con)
            for stage_key in keys:
                spec = settings.stages[stage_key]
                before = budget.used
                stage = runtime.sweep(spec.whoscored_page_url, spec, budget=budget)
                landed = land_stage(
                    con,
                    spec,
                    settings.raw_dir,
                    stage.page,
                    feeds=stage.feeds,
                    requests=budget.used - before,
                    log_dir=settings.log_dir,
                )
                candidate = build_candidate(list(landed.feeds), spec)
                standings = parse_views(landed.page, spec)
                check_team_sets(candidate, standings)
                outcome = publish(
                    con,
                    candidate,
                    standings,
                    spec,
                    landed,
                    allow_apps_decrease=allow_apps_decrease,
                    on_warning=_warning_handler(settings, landed, out),
                )
                _say(
                    out,
                    f"{spec.key}: {outcome.value} "
                    f"({len(candidate.rows)} teams, run {landed.run_id})",
                )
        finally:
            con.close()
    return Exit.OK


def _probe(
    settings: Settings,
    key: str | None,
    runtime: Runtime,
    out: TextIO,
) -> Exit:
    for stage_key in _keys(settings, key):
        spec = settings.stages[stage_key]
        stage = runtime.sweep(
            spec.whoscored_page_url,
            spec,
            only=(("summary", "overall"),),
            budget=RequestBudget(limit=3),
        )
        if not stage.feeds:
            raise FetchError(f"{spec.key}: probe returned no feed")
        capture = stage.feeds[0]
        digest = hashlib.sha256(capture.body).hexdigest()
        rows = _probe_rows(capture)
        _say(
            out,
            f"{spec.key}: {rows} teams, {len(capture.body)} bytes, sha256 {digest[:16]}",
        )
    return Exit.OK


def _probe_rows(capture: Capture) -> int:
    """Count team rows without building the full candidate."""
    return len(parse_capture(capture.section, capture.view, capture.body))


def dispatch(args: argparse.Namespace, runtime: Runtime, out: TextIO) -> Exit:
    """Run one parsed command and return its exit code."""
    settings = _load(args.config)
    if args.command == "stages":
        return _stages_list(settings, out)
    if args.command == "freshness":
        return _freshness(
            settings, args.json, out, check=args.check, max_age_hours=args.max_age_hours
        )
    if args.command == "verify":
        return _verify(settings, args.snapshot, args.address, out)
    if args.command == "replay":
        return _replay(settings, args.run_id, args.raw_dir, args.check, out)
    if args.command == "run":
        return _run(
            settings,
            args.stage,
            allow_apps_decrease=args.allow_apps_decrease,
            dry_run=args.dry_run,
            runtime=runtime,
            out=out,
        )
    if args.command == "probe":
        return _probe(settings, args.stage, runtime, out)
    raise ConfigError(f"unknown command: {args.command}")


def main(
    argv: Sequence[str] | None = None,
    *,
    runtime: Runtime | None = None,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Run the command line interface.

    Args:
        argv: Argument list. Defaults to ``sys.argv[1:]``.
        runtime: Injectable page and feed effects for tests.
        out: Standard output stream. Defaults to ``sys.stdout`` at call time.
        err: Standard error stream. Defaults to ``sys.stderr`` at call time.

    Returns:
        The process exit code.
    """
    stdout = out if out is not None else sys.stdout
    stderr = err if err is not None else sys.stderr
    parser = _build_parser()

    try:
        args = parser.parse_args(argv)
    except ConfigError as exc:
        parser.print_usage(stderr)
        print(f"error: {exc}", file=stderr)
        return int(Exit.CONFIG)
    except SystemExit as exc:
        return int(exc.code or 0)

    try:
        return int(dispatch(args, runtime or Runtime(), stdout))
    except LockHeld as exc:
        print(f"locked: {exc}", file=stderr)
        return int(Exit.LOCKED)
    except FetchBlocked as exc:
        print(f"blocked: {exc}", file=stderr)
        return int(Exit.BLOCKED)
    except SchemaDrift as exc:
        print(f"blocked: source schema drifted: {exc}", file=stderr)
        return int(Exit.BLOCKED)
    except FetchError as exc:
        print(f"fetch failed: {exc}", file=stderr)
        return int(Exit.FETCH_FAILED)
    except PublishBlocked as exc:
        print(str(exc), file=stderr)
        return int(Exit.BLOCKED)
    except ConfigError as exc:
        print(f"error: {exc}", file=stderr)
        return int(Exit.CONFIG)
    except (IncompleteCohort, OwnershipMismatch, SourceParseError, StandingsParseError) as exc:
        print(f"blocked: {exc}", file=stderr)
        return int(Exit.BLOCKED)
    except MigrationError as exc:
        print(f"migration error: {exc}", file=stderr)
        return int(Exit.INTERNAL)
    except (duckdb.Error, OSError, RuntimeError) as exc:
        print(f"internal error: {exc}", file=stderr)
        return int(Exit.INTERNAL)
