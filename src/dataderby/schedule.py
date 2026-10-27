"""Scheduled-run helpers: staleness checks, heartbeat pings, failure alerts.

The pipeline runs on an OS timer, not an orchestrator: one pipeline, one
schedule, one writer. This module holds the logic the timer needs so it stays
testable without a clock, a database, or a network:

- :func:`evaluate_freshness` decides which stages are stale.
- :func:`ping_heartbeat` tells an external monitor that a run succeeded, so the
  monitor can alert when no ping arrives (the dead-man's switch).
- :func:`run_scheduled` wires one scheduled invocation: run, then ping on
  success or raise the failure alert on any non-zero exit.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.request import urlopen

#: Provisional staleness ceiling in hours. Generous on purpose: the daily
#: heartbeat runs every 24 h, so 36 h tolerates one missed run plus a slow
#: retry. Replaced by last-kickoff-plus-p95 once experiment E5 measures the
#: real publication lag (issue #8).
STALE_AFTER_HOURS = 36.0


@dataclass(frozen=True, slots=True)
class StageFreshness:
    """One row of ``v_pipeline_freshness`` with the staleness verdict."""

    whoscored_tournament_id: int
    whoscored_season_id: int
    whoscored_stage_id: int
    last_success_at: str | None
    age_seconds: float | None
    last_outcome: str | None
    attempt_count: int
    accepted_snapshots: int
    stale: bool


def evaluate_freshness(
    rows: list[tuple[Any, ...]],
    *,
    max_age_seconds: float,
) -> tuple[StageFreshness, ...]:
    """Mark each freshness row as stale or fresh.

    A stage is stale when it has never succeeded (``last_success_at`` is
    ``NULL``, so ``age_seconds`` is ``NULL``) or when its age exceeds the
    ceiling. A row exactly at the ceiling is still fresh: the ceiling is a
    grace period, not a tripwire.

    Args:
        rows: ``v_pipeline_freshness`` rows in the CLI column order:
            tournament, season, stage, ``last_success_at``, ``age_seconds``,
            ``last_outcome``, ``attempt_count``, ``accepted_snapshots``.
        max_age_seconds: Age above which a stage counts as stale.

    Returns:
        One :class:`StageFreshness` per row, in the same order.
    """
    evaluated: list[StageFreshness] = []
    for row in rows:
        age = row[4]
        stale = age is None or float(age) > max_age_seconds
        evaluated.append(
            StageFreshness(
                whoscored_tournament_id=int(row[0]),
                whoscored_season_id=int(row[1]),
                whoscored_stage_id=int(row[2]),
                last_success_at=str(row[3]) if row[3] is not None else None,
                age_seconds=None if age is None else float(age),
                last_outcome=None if row[5] is None else str(row[5]),
                attempt_count=int(row[6]),
                accepted_snapshots=int(row[7]),
                stale=stale,
            )
        )
    return tuple(evaluated)


def ping_heartbeat(
    url: str,
    *,
    timeout_seconds: float = 10.0,
    opener: Callable[..., Any] = urlopen,
) -> bool:
    """Ping a dead-man's-switch monitor after a successful run.

    The monitor alerts when no ping arrives within the expected window, which
    catches the failure a failure-alert cannot: the scheduler itself dying.
    Uses only the standard library, so the scheduled wrapper needs no new
    dependency.

    Args:
        url: Monitor ping URL, from the ``DATADERBY_HEARTBEAT_URL`` variable.
        timeout_seconds: HTTP timeout for the ping.
        opener: Injectable URL opener, for tests.

    Returns:
        ``True`` when the ping got an HTTP 2xx, ``False`` otherwise. A failed
        ping never raises: it must not mask the run's own outcome.
    """
    try:
        with opener(url, timeout=timeout_seconds) as response:
            return 200 <= int(response.status) < 300
    except Exception:
        return False


def run_scheduled(
    run: Callable[[], int],
    *,
    on_failure: Callable[[int], None],
    on_success: Callable[[], None] | None = None,
) -> int:
    """Run one scheduled invocation, then alert or ping.

    Every non-zero exit alerts, including ``5`` (locked): a lock held at the
    scheduled time means the previous run overran, which is itself a signal.
    The run's exit code is always returned unchanged; alerting never rewrites
    the outcome.

    Args:
        run: The scheduled command. Returns its process exit code.
        on_failure: Called once with a non-zero exit code.
        on_success: Called once on exit ``0``, normally the heartbeat ping.

    Returns:
        The exit code from ``run``.
    """
    code = run()
    if code == 0:
        if on_success is not None:
            on_success()
    else:
        on_failure(code)
    return code
