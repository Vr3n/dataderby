"""One fetch-and-land run: page, standings, feeds, raw files, and ledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb

from dataderby.config import StageSpec
from dataderby.db import transaction
from dataderby.fetch import Capture, FeedFetcher, FetchError
from dataderby.observe import log
from dataderby.page import PageCapture
from dataderby.raw import RawFile, RawPayload, write_bundle
from dataderby.standings import encode_view


@dataclass(frozen=True, slots=True)
class LandingResult:
    """What one landed sweep produced."""

    run_id: str
    observed_at: datetime
    page: PageCapture
    feeds: tuple[Capture, ...]
    raw_files: tuple[RawFile, ...]


def _insert_run(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    spec: StageSpec,
) -> None:
    con.execute(
        """
        INSERT INTO ingestion_run (
            run_id, mode, started_at, outcome, whoscored_tournament_id,
            whoscored_season_id, whoscored_stage_id
        ) VALUES (?, 'full', ?, 'running', ?, ?, ?)
        """,
        [
            run_id,
            datetime.now(UTC),
            spec.whoscored_tournament_id,
            spec.whoscored_season_id,
            spec.whoscored_stage_id,
        ],
    )


def _update_run(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    observed_at: datetime,
    http_requests: int,
) -> None:
    con.execute(
        """
        UPDATE ingestion_run
        SET observed_at = ?, http_requests = ?
        WHERE run_id = ?
        """,
        [observed_at, http_requests, run_id],
    )


def _insert_raw_captures(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    files: tuple[RawFile, ...],
) -> None:
    for file in files:
        con.execute(
            """
            INSERT INTO raw_capture (
                run_id, section, view, attempt, captured_at, path, byte_count,
                sha256, content_type, is_gate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            [
                run_id,
                file.section,
                file.view,
                file.attempt,
                file.captured_at,
                str(file.path),
                file.byte_count,
                file.sha256,
                file.content_type,
                file.is_gate,
            ],
        )


def _fail_run(con: duckdb.DuckDBPyConnection, run_id: str, outcome: str) -> None:
    con.execute(
        """
        UPDATE ingestion_run
        SET outcome = ?, finished_at = ?
        WHERE run_id = ?
        """,
        [outcome, datetime.now(UTC), run_id],
    )


def _payloads(page: PageCapture, feeds: tuple[Capture, ...]) -> tuple[RawPayload, ...]:
    payloads = [
        RawPayload(
            section="page",
            view="show",
            body=page.html.encode("utf-8"),
            captured_at=page.captured_at,
            url=page.url,
            content_type="text/html",
        )
    ]
    for view, rows in page.standings.items():
        payloads.append(
            RawPayload(
                section="standings",
                view=view,
                body=encode_view(view, rows),
                captured_at=page.captured_at,
                url=page.url,
                content_type="application/json",
            )
        )
    payloads.extend(
        RawPayload(
            section=capture.section,
            view=capture.view,
            body=capture.body,
            captured_at=capture.captured_at,
            url=capture.url,
            content_type=capture.content_type,
            status=capture.status,
            attempt=capture.attempt,
        )
        for capture in feeds
    )
    return tuple(payloads)


def land_stage(
    con: duckdb.DuckDBPyConnection,
    spec: StageSpec,
    raw_root: Path,
    page: PageCapture,
    fetcher: FeedFetcher | None = None,
    *,
    feeds: tuple[Capture, ...] | None = None,
    run_id: str | None = None,
    requests: int | None = None,
    log_dir: Path = Path("data/logs"),
    verbose: bool = False,
) -> LandingResult:
    """Archive one sweep and record its raw ledger.

    Exactly one source of feeds is required: either a ``fetcher`` that performs
    the requests, or already-fetched ``feeds`` from the browser transport. The
    second avoids fetching twice when the page and feeds share a session.

    The run row is opened before the first feed request. The raw directory is
    written as a bundle and only then are the ledger rows committed. The run is
    intentionally left in ``running``: P6 owns the publish outcome.

    Args:
        con: DuckDB connection with the v1 schema applied.
        spec: Stage to land.
        raw_root: Raw root, normally ``data/raw``.
        page: An already-captured page for this stage.
        fetcher: Feed fetcher; injectable for tests. Ignored when ``feeds`` is set.
        feeds: Feeds already captured in the page's session.
        run_id: Optional caller-supplied run id.
        requests: Feed requests actually made, including retries. Defaults to the
            attempts recorded on the accepted captures.
        log_dir: JSON-lines log directory.
        verbose: Also log to stderr.

    Returns:
        The landed run and its archived file metadata.

    Raises:
        ValueError: If neither ``fetcher`` nor ``feeds`` is supplied.
        FetchError: If a feed cannot be accepted.
        FileExistsError: If the target raw directory already exists.
        Exception: Any other landing failure, after marking the run as failed.
    """
    actual_run_id = run_id or f"run_{uuid4().hex}"
    _insert_run(con, actual_run_id, spec)
    log(
        "run.start",
        log_dir=log_dir,
        verbose=verbose,
        run_id=actual_run_id,
        whoscored_stage_id=spec.whoscored_stage_id,
    )

    try:
        if feeds is None:
            if fetcher is None:
                raise ValueError("land_stage needs either a fetcher or feeds")
            feeds = fetcher.fetch_all(spec, page.token)
        observed_at = min([page.captured_at, *(capture.captured_at for capture in feeds)])
        payloads = _payloads(page, feeds)
        raw_files = write_bundle(raw_root, spec, observed_at, payloads)

        with transaction(con):
            _insert_raw_captures(con, actual_run_id, raw_files)
            feed_requests = (
                requests if requests is not None else sum(capture.attempt for capture in feeds)
            )
            _update_run(con, actual_run_id, observed_at, 1 + feed_requests)
    except FetchError:
        _fail_run(con, actual_run_id, "fetch_failed")
        log("run.fetch_failed", log_dir=log_dir, verbose=verbose, run_id=actual_run_id)
        raise
    except BaseException:
        _fail_run(con, actual_run_id, "crashed")
        log("run.crashed", log_dir=log_dir, verbose=verbose, run_id=actual_run_id)
        raise

    log(
        "run.landed",
        log_dir=log_dir,
        verbose=verbose,
        run_id=actual_run_id,
        files=len(raw_files),
        observed_at=observed_at.isoformat(),
    )
    return LandingResult(
        run_id=actual_run_id,
        observed_at=observed_at,
        page=page,
        feeds=feeds,
        raw_files=raw_files,
    )
