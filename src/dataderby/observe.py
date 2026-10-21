"""Append-only JSON-lines logging for pipeline runs."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_DEFAULT_LOG_DIR = Path("data/logs")


def log(
    event: str,
    /,
    *,
    log_dir: Path = _DEFAULT_LOG_DIR,
    verbose: bool = False,
    **fields: object,
) -> None:
    """Write one JSON object to the daily log and optionally to stderr.

    Args:
        event: Short event name, for example ``run.start``.
        log_dir: Directory for ``<UTC date>.jsonl`` files.
        verbose: Also print the same JSON line to stderr.
        **fields: Additional JSON-serializable event fields.
    """
    now = datetime.now(UTC)
    record = {"ts": now.isoformat(), "event": event, **fields}
    line = json.dumps(record, sort_keys=True, default=str)

    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{now:%Y-%m-%d}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")

    if verbose:
        print(line, file=sys.stderr)
