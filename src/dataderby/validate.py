"""Execute the v1 publish assertions and map findings to actions."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import duckdb

from dataderby.config import StageSpec
from dataderby.contract import MEASURE_COLUMNS, STANDINGS_MEASURES
from dataderby.landing import LandingResult
from dataderby.parse import Candidate, parse_capture
from dataderby.parse_standings import StandingsCandidate

_SQL_PATH = Path(__file__).resolve().parents[2] / "sql" / "002_assertions.sql"
_MARKER = re.compile(r"^--\s*@@(?P<assertion_id>[A-Z0-9_]+)\|(?P<action>BLOCK|RETRY|WARN)\s*$")
_PROVENANCE_ASSERTIONS = frozenset({"A3", "A4", "A11", "A12", "A15", "A17"})


class Action(StrEnum):
    """What the caller may do after an assertion fails."""

    BLOCK = "BLOCK"
    RETRY = "RETRY"
    WARN = "WARN"


@dataclass(frozen=True, slots=True)
class AssertionDefinition:
    """One SQL assertion loaded from the contract file."""

    assertion_id: str
    action: Action
    sql: str


@dataclass(frozen=True, slots=True)
class AssertionFailure:
    """One failed assertion and the rows that caused it."""

    assertion_id: str
    action: Action
    message: str
    rows: tuple[tuple[object, ...], ...]


class PublishBlocked(RuntimeError):
    """Raised by publish when validation finds a blocking assertion."""

    def __init__(self, failures: list[AssertionFailure]) -> None:
        self.failures = failures
        ids = ", ".join(failure.assertion_id for failure in failures)
        super().__init__(f"publish blocked by: {ids}")


def load_assertions(path: Path = _SQL_PATH) -> tuple[AssertionDefinition, ...]:
    """Load marker-delimited SQL assertions from ``002_assertions.sql``.

    The file is comment-only so ``migrate()`` can execute it safely. Markers
    have the form ``-- @@A1|BLOCK`` followed by ``--``-prefixed SQL lines.
    """
    definitions: list[AssertionDefinition] = []
    current_id: str | None = None
    current_action: Action | None = None
    sql_lines: list[str] = []

    def finish() -> None:
        if current_id is None or current_action is None:
            return
        sql = "\n".join(sql_lines).strip()
        if not sql:
            raise ValueError(f"assertion {current_id} has no SQL")
        definitions.append(
            AssertionDefinition(
                assertion_id=current_id,
                action=current_action,
                sql=sql,
            )
        )

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        marker = _MARKER.match(raw_line.strip())
        if marker:
            finish()
            current_id = marker.group("assertion_id")
            current_action = Action(marker.group("action"))
            sql_lines = []
            continue
        if current_id is None:
            continue
        if raw_line.startswith("-- "):
            sql_lines.append(raw_line[3:])
        elif raw_line.strip() == "--":
            sql_lines.append("")
    finish()

    ids = [definition.assertion_id for definition in definitions]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate assertion id in 002_assertions.sql")
    return tuple(definitions)


def _drop_staging(con: duckdb.DuckDBPyConnection) -> None:
    for name in (
        "_assert_team",
        "_assert_standings",
        "_assert_run",
        "_assert_capture",
        "_assert_feed_team",
        "_assert_shared",
        "_assert_feed_error",
        "_assert_measure",
        "_assert_rank",
        "_assert_standings_long",
    ):
        con.execute(f"DROP TABLE IF EXISTS {name}")


def _staging_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "CAST('NaN' AS DOUBLE)"
        if math.isinf(value):
            return "CAST('Infinity' AS DOUBLE)" if value > 0 else "CAST('-Infinity' AS DOUBLE)"
        return repr(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise TypeError(f"unsupported staging literal: {type(value).__name__}")


def _insert_literals(
    con: duckdb.DuckDBPyConnection,
    table: str,
    columns: tuple[str, ...],
    params: list[list[object]],
) -> None:
    if not params:
        return
    values = ", ".join(
        "(" + ", ".join(_staging_literal(value) for value in row) + ")" for row in params
    )
    con.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES {values}")


def _stage_rows(
    con: duckdb.DuckDBPyConnection,
    candidate: Candidate,
    standings: StandingsCandidate,
    spec: StageSpec,
    run: LandingResult | None,
) -> None:
    con.execute("CREATE TEMP TABLE _assert_team AS SELECT * FROM fact_team_snapshot LIMIT 0")
    con.execute(
        "CREATE TEMP TABLE _assert_standings AS SELECT * FROM fact_standings_snapshot LIMIT 0"
    )
    con.execute(
        """
        CREATE TEMP TABLE _assert_run (
            run_id VARCHAR,
            observed_at TIMESTAMP,
            capture_span_seconds DOUBLE,
            whoscored_page_url VARCHAR,
            whoscored_tournament_id INTEGER,
            whoscored_season_id INTEGER,
            whoscored_stage_id INTEGER,
            is_opta BOOLEAN,
            expected_teams INTEGER,
            has_league_table BOOLEAN,
            provenance_available BOOLEAN
        )
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE _assert_capture (
            section VARCHAR,
            view VARCHAR,
            url VARCHAR,
            captured_at TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE _assert_feed_team (
            section VARCHAR,
            view VARCHAR,
            whoscored_team_id INTEGER,
            whoscored_tournament_id INTEGER,
            is_opta BOOLEAN
        )
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE _assert_shared (
            section VARCHAR,
            view VARCHAR,
            whoscored_team_id INTEGER,
            column_name VARCHAR,
            value DOUBLE
        )
        """
    )
    con.execute("CREATE TEMP TABLE _assert_feed_error (detail VARCHAR)")
    con.execute(
        """
        CREATE TEMP TABLE _assert_measure (
            whoscored_team_id INTEGER,
            column_name VARCHAR,
            value DOUBLE
        )
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE _assert_rank (
            section VARCHAR,
            view VARCHAR,
            whoscored_team_id INTEGER,
            ranking INTEGER
        )
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE _assert_standings_long (
            whoscored_team_id INTEGER,
            view VARCHAR,
            rank INTEGER,
            played INTEGER,
            won INTEGER,
            drawn INTEGER,
            lost INTEGER,
            goals_for INTEGER,
            goals_against INTEGER,
            goal_difference INTEGER,
            points INTEGER,
            form VARCHAR
        )
        """
    )

    team_columns = ("snapshot_id", "whoscored_team_id", "whoscored_team_name", *MEASURE_COLUMNS)
    team_sql = (
        f"INSERT INTO _assert_team ({', '.join(team_columns)}) "
        f"VALUES ({', '.join('?' for _ in team_columns)})"
    )
    team_params = [
        (
            "candidate",
            row.whoscored_team_id,
            row.whoscored_team_name,
            *(row.measures.get(column) for column in MEASURE_COLUMNS),
        )
        for row in candidate.rows
    ]
    if team_params:
        con.executemany(team_sql, team_params)

    standings_columns = (
        "snapshot_id",
        "whoscored_team_id",
        "whoscored_team_name",
        *STANDINGS_MEASURES,
    )
    standings_sql = (
        f"INSERT INTO _assert_standings ({', '.join(standings_columns)}) "
        f"VALUES ({', '.join('?' for _ in standings_columns)})"
    )
    standings_params = [
        (
            "candidate",
            row.whoscored_team_id,
            row.whoscored_team_name,
            *(row.measures.get(column) for column in STANDINGS_MEASURES),
        )
        for row in standings.rows
    ]
    if standings_params:
        con.executemany(standings_sql, standings_params)

    now = run.observed_at if run is not None else datetime.now(UTC)
    capture_times = []
    if run is not None:
        capture_times = [
            run.page.captured_at,
            *(capture.captured_at for capture in run.feeds),
        ]
    span = 0.0
    if capture_times:
        span = (max(capture_times) - min(capture_times)).total_seconds()
    page_url = run.page.url if run is not None else ""
    run_id = run.run_id if run is not None else ""
    con.execute(
        """
        INSERT INTO _assert_run VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            now,
            span,
            page_url,
            spec.whoscored_tournament_id,
            spec.whoscored_season_id,
            spec.whoscored_stage_id,
            candidate.is_opta,
            spec.expected_teams,
            spec.has_league_table,
            run is not None,
        ],
    )

    if run is not None:
        capture_params: list[list[object]] = [
            ["page", "show", run.page.url, run.page.captured_at],
        ]
        capture_params.extend(
            ["standings", view, run.page.url, run.page.captured_at] for view in run.page.standings
        )
        feed_team_params: list[list[object]] = []
        shared_params: list[list[object]] = []
        error_params: list[list[object]] = []
        shared_columns = _shared_column_names()
        for capture in run.feeds:
            capture_params.append([capture.section, capture.view, capture.url, capture.captured_at])
            try:
                source_rows = parse_capture(capture.section, capture.view, capture.body)
            except Exception as exc:
                error_params.append([f"{capture.section}/{capture.view}: {exc}"])
                continue
            for source_row in source_rows:
                feed_team_params.append(
                    [
                        source_row.section,
                        source_row.view,
                        source_row.whoscored_team_id,
                        source_row.whoscored_tournament_id,
                        source_row.is_opta,
                    ]
                )
                shared_params.extend(
                    [
                        source_row.section,
                        source_row.view,
                        source_row.whoscored_team_id,
                        column_name,
                        float(value),
                    ]
                    for column_name, value in source_row.measures.items()
                    if column_name in shared_columns and value is not None
                )

        con.executemany(
            "INSERT INTO _assert_capture VALUES (?, ?, ?, ?)",
            capture_params,
        )
        _insert_literals(
            con,
            "_assert_feed_team",
            (
                "section",
                "view",
                "whoscored_team_id",
                "whoscored_tournament_id",
                "is_opta",
            ),
            feed_team_params,
        )
        _insert_literals(
            con,
            "_assert_shared",
            (
                "section",
                "view",
                "whoscored_team_id",
                "column_name",
                "value",
            ),
            shared_params,
        )
        if error_params:
            con.executemany(
                "INSERT INTO _assert_feed_error VALUES (?)",
                error_params,
            )

    rank_params: list[list[object]] = []
    measure_params: list[list[object]] = [
        [
            row.whoscored_team_id,
            column,
            None if (value := row.measures.get(column)) is None else float(value),
        ]
        for row in candidate.rows
        for column in MEASURE_COLUMNS
    ]
    for row in candidate.rows:
        for column in MEASURE_COLUMNS:
            if not column.startswith("ranking_"):
                continue
            _, section_name, section_view = column.split("_", 2)
            rank_params.append(
                [
                    section_name,
                    section_view,
                    row.whoscored_team_id,
                    row.measures.get(column),
                ]
            )

    fields = (
        "rank",
        "played",
        "won",
        "drawn",
        "lost",
        "goals_for",
        "goals_against",
        "goal_difference",
        "points",
        "form",
    )
    standings_long_params: list[list[object]] = [
        [
            standings_row.whoscored_team_id,
            standings_view,
            *(standings_row.measures.get(f"{field}_{standings_view}") for field in fields),
        ]
        for standings_row in standings.rows
        for standings_view in ("overall", "home", "away")
    ]

    _insert_literals(
        con,
        "_assert_measure",
        ("whoscored_team_id", "column_name", "value"),
        measure_params,
    )
    _insert_literals(
        con,
        "_assert_rank",
        ("section", "view", "whoscored_team_id", "ranking"),
        rank_params,
    )
    _insert_literals(
        con,
        "_assert_standings_long",
        (
            "whoscored_team_id",
            "view",
            "rank",
            "played",
            "won",
            "drawn",
            "lost",
            "goals_for",
            "goals_against",
            "goal_difference",
            "points",
            "form",
        ),
        standings_long_params,
    )


def _shared_column_names() -> frozenset[str]:
    return frozenset(
        f"{base}_{view}"
        for base in ("apps", "rating", "shots_per_game")
        for view in ("overall", "home", "away")
    )


def run_assertions(
    con: duckdb.DuckDBPyConnection,
    candidate: Candidate,
    standings: StandingsCandidate,
    spec: StageSpec,
    run: LandingResult | None = None,
    *,
    allow_apps_decrease: bool = False,
    assertions_path: Path = _SQL_PATH,
) -> list[AssertionFailure]:
    """Execute A1-A21 against a staged candidate.

    The candidate and standings are loaded into temporary tables; source-level
    assertions read the supplied landing result. When ``run`` is omitted, the
    provenance-dependent assertions are skipped, which is useful for isolated
    candidate tests but never acceptable for a real publish.

    Args:
        con: Open DuckDB connection with the schema applied.
        candidate: Feed candidate to validate.
        standings: Standings companion.
        spec: Configured stage.
        run: The landing result that owns the raw captures.
        allow_apps_decrease: Explicit revocation override for A10.
        assertions_path: Contract file, normally ``sql/002_assertions.sql``.

    Returns:
        Every failed assertion in file order. A WARN is returned but does not
        block by itself.
    """
    _drop_staging(con)
    _stage_rows(con, candidate, standings, spec, run)
    failures: list[AssertionFailure] = []
    for definition in load_assertions(assertions_path):
        if definition.assertion_id in _PROVENANCE_ASSERTIONS and run is None:
            continue
        if definition.assertion_id == "A10" and allow_apps_decrease:
            continue
        rows = con.execute(definition.sql).fetchall()
        if rows:
            failures.append(
                AssertionFailure(
                    assertion_id=definition.assertion_id,
                    action=definition.action,
                    message=(
                        f"{definition.assertion_id} {definition.action}: "
                        f"{len(rows)} offending row(s)"
                    ),
                    rows=tuple(tuple(row) for row in rows),
                )
            )
    return failures


def blocking_failures(failures: list[AssertionFailure]) -> list[AssertionFailure]:
    """Return failures whose action is not ``WARN``."""
    return [failure for failure in failures if failure.action is not Action.WARN]
