"""Fetch and record the source's robots.txt.

This is the one-command re-check referenced by ADR 0009. It does not enforce
anything at runtime; it records what the file said, when, and its hash, so the
policy is evidence rather than memory.

Usage::

    uv run python scripts/check_robots.py
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime

from curl_cffi import requests

DEFAULT_URL = "https://www.whoscored.com/robots.txt"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="robots.txt URL")
    args = parser.parse_args()

    response = requests.get(args.url, impersonate="chrome", timeout=30)
    body = response.content
    print(f"url:        {args.url}")
    print(f"status:    {response.status_code}")
    print(f"checked_at: {datetime.now(UTC).isoformat()}")
    print(f"sha256:    {hashlib.sha256(body).hexdigest()}")
    print(f"bytes:     {len(body)}")
    print()
    print(body.decode("utf-8", errors="replace"))
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
