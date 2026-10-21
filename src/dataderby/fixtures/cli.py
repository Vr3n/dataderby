"""Command line entry point for the fixture calendar."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dataderby.fixtures.competitions import COMPETITIONS, get_competition
from dataderby.fixtures.download import DownloadError
from dataderby.fixtures.service import RefreshError, RefreshResult, refresh
from dataderby.fixtures.store import connect

DEFAULT_DB = Path("data/fixtures.sqlite3")
DEFAULT_RAW = Path("data")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dataderby-fixtures",
        description="Download and inspect the football fixture calendar.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    refresh_parser = subparsers.add_parser("refresh", help="download and store all fixtures")
    refresh_parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    refresh_parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW)
    refresh_parser.set_defaults(handler=_refresh)

    show_parser = subparsers.add_parser("show", help="show one competition's fixtures")
    show_parser.add_argument("competition", help="competition key, for example epl")
    show_parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    show_parser.add_argument("--limit", type=int, default=20)
    show_parser.set_defaults(handler=_show)

    next_parser = subparsers.add_parser("next", help="show upcoming fixtures")
    next_parser.add_argument("--days", type=int, default=7)
    next_parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    next_parser.set_defaults(handler=_next)

    competitions_parser = subparsers.add_parser("competitions", help="list stored competitions")
    competitions_parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    competitions_parser.set_defaults(handler=_competitions)

    return parser


def _summary(result: RefreshResult) -> None:
    print(f"refreshed {len(result.competitions)} competitions, {result.fixture_count} fixtures")
    for item in result.competitions:
        print(
            f"  {item.competition_key:<18} {item.fixtures:>4} fixtures "
            f"({item.played:>3} played)  "
            f"{item.inserted:>3} new  {item.updated:>3} changed"
        )


def _refresh(args: argparse.Namespace) -> int:
    try:
        result = refresh(args.db, args.raw_root)
    except DownloadError as exc:
        print(f"download failed: {exc}", file=sys.stderr)
        return 2
    except RefreshError as exc:
        for failure in exc.result.failures:
            print(f"failed: {failure}", file=sys.stderr)
        _summary(exc.result)
        return 2
    _summary(result)
    return 0


def _show(args: argparse.Namespace) -> int:
    try:
        competition = get_competition(args.competition)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    connection = connect(args.db)
    try:
        rows = connection.execute(
            """
            SELECT round_number, kickoff_ist, home_team, away_team, venue,
                   status, home_score, away_score
            FROM fixtures
            WHERE competition_key = ?
            ORDER BY kickoff_utc
            LIMIT ?
            """,
            (competition.key, args.limit),
        ).fetchall()
    finally:
        connection.close()

    print(f"{competition.name} — {competition.season}")
    _fixture_rows(rows, show_competition=False)
    return 0


def _next(args: argparse.Namespace) -> int:
    now = datetime.now(UTC)
    cutoff = now + timedelta(days=args.days)
    connection = connect(args.db)
    try:
        rows = connection.execute(
            """
            SELECT competition_key, kickoff_ist, home_team, away_team, venue,
                   status, home_score, away_score
            FROM fixtures
            WHERE kickoff_utc >= ? AND kickoff_utc <= ?
            ORDER BY kickoff_utc
            """,
            (_iso(now), _iso(cutoff)),
        ).fetchall()
    finally:
        connection.close()

    print(f"next {args.days} day(s), Asia/Kolkata")
    _fixture_rows(rows, show_competition=True)
    return 0


def _competitions(args: argparse.Namespace) -> int:
    connection = connect(args.db)
    try:
        rows = connection.execute(
            """
            SELECT c.competition_key, c.name, c.country, c.season,
                   c.fixture_count, c.played_count, c.fetched_at
            FROM competitions AS c
            ORDER BY c.competition_key
            """
        ).fetchall()
    finally:
        connection.close()

    print(f"{'key':<18} {'competition':<26} {'season':<8} {'rows':>5} {'played':>7}  fetched")
    for row in rows:
        print(
            f"{row['competition_key']:<18} {row['name']:<26} {row['season']:<8} "
            f"{row['fixture_count']:>5} {row['played_count']:>7}  {row['fetched_at']}"
        )
    print(f"\n{len(rows)} of {len(COMPETITIONS)} configured competitions stored")
    return 0


def _fixture_rows(rows: Sequence[sqlite3.Row], *, show_competition: bool) -> None:
    if not rows:
        print("  (none)")
        return
    for row in rows:
        kickoff = str(row["kickoff_ist"])[:16].replace("T", " ")
        score = (
            f"{row['home_score']}-{row['away_score']}" if row["home_score"] is not None else "vs"
        )
        competition = f"{row['competition_key']:<10} " if show_competition else ""
        print(
            f"  {kickoff}  {competition}{row['home_team']:<24} {score:>3} "
            f"{row['away_team']:<24} {row['venue']}"
        )


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the fixture CLI.

    Args:
        argv: Argument list. Defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code.
    """
    args = _parser().parse_args(argv)
    handler = args.handler
    exit_code: int = handler(args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
