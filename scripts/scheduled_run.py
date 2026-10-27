"""Run the pipeline on a timer, ping a monitor on success, alert on failure.

This is the command a Task Scheduler task or a cron line calls. It runs
``dataderby run``, then uses :mod:`dataderby.schedule`:

- exit 0: ping the dead-man's-switch monitor (``--heartbeat-url`` or
  ``DATADERBY_HEARTBEAT_URL``). The monitor alerts when no ping arrives,
  which catches the scheduler itself dying. Skipped when no URL is set.
- any other exit: print an alert line and POST it to ``--alert-url`` or
  ``DATADERBY_ALERT_URL`` when set. Exit 5 (locked) alerts like any other
  failure: a held lock means the previous run overran.

Standard library only. The run's exit code is returned unchanged.

Usage::

    uv run python scripts/scheduled_run.py --config config/stages.toml
    uv run python scripts/scheduled_run.py --config config/stages.toml --stage epl-2026-2027
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


def _post(url: str, payload: bytes, timeout_seconds: float) -> bool:
    """POST bytes to a URL; ``True`` on HTTP 2xx, ``False`` otherwise."""
    try:
        request = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return 200 <= int(response.status) < 300
    except Exception as exc:
        print(f"scheduled_run: alert delivery failed: {exc}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/stages.toml"))
    parser.add_argument("--stage", default=None, help="stage key; default is every stage")
    parser.add_argument(
        "--heartbeat-url",
        default=os.environ.get("DATADERBY_HEARTBEAT_URL"),
        help="dead-man's-switch ping URL (or set DATADERBY_HEARTBEAT_URL)",
    )
    parser.add_argument(
        "--alert-url",
        default=os.environ.get("DATADERBY_ALERT_URL"),
        help="webhook for failure alerts (or set DATADERBY_ALERT_URL)",
    )
    parser.add_argument("--timeout", type=float, default=600.0, help="run timeout in seconds")
    args = parser.parse_args()

    command = [sys.executable, "-m", "dataderby", "run", "--config", str(args.config)]
    if args.stage:
        command += ["--stage", args.stage]
    try:
        completed = subprocess.run(command, timeout=args.timeout, check=False)
        code = completed.returncode
    except subprocess.TimeoutExpired:
        code = 6
        print("scheduled_run: run timed out", file=sys.stderr)

    if code == 0:
        if args.heartbeat_url:
            from dataderby.schedule import ping_heartbeat

            ok = ping_heartbeat(args.heartbeat_url)
            print(f"scheduled_run: heartbeat {'sent' if ok else 'FAILED'}")
        else:
            print("scheduled_run: ok (no heartbeat URL set, skipping ping)")
        return 0

    message = f"dataderby scheduled run failed with exit {code}".encode()
    print(f"scheduled_run: ALERT {message.decode()}", file=sys.stderr)
    if args.alert_url:
        _post(args.alert_url, message, timeout_seconds=10.0)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
