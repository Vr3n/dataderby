"""Approach B: generated ULID + a unique constraint on (parent, content).

Dedupe is the database edge constraint, not the id. A sentinel parent ('genesis') is
required: SQL treats NULLs as distinct, so a NULL parent would let the first observation
be inserted twice.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

import common

NAME = "B-ulid"
SCHEME = "ULID + UNIQUE(parent_snapshot_id, content_fingerprint)"

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def ulid() -> str:
    """Crockford base32 ULID: 48-bit ms timestamp + 80 random bits."""
    millis = int(time.time() * 1000)
    randomness = int.from_bytes(os.urandom(10), "big")
    value = (millis << 80) | randomness
    return "".join(_CROCKFORD[(value >> (5 * i)) & 0x1F] for i in range(25, -1, -1))


def create_schema(con: Any) -> None:
    common.create_schema(con, unique_edge=True, parent_nullable=False)


def new_id(parent: str, stage: str, content_fp: str) -> str:
    return ulid()


def insert_snapshot(
    con: Any,
    sid: str,
    parent: str,
    stage: str,
    fp: str,
    observed_at: datetime,
    accepted_at: datetime,
) -> tuple[str, bool]:
    inserted = con.execute(
        "INSERT INTO competition_snapshot "
        "(snapshot_id, parent_snapshot_id, stage_id, content_fingerprint, "
        " observed_at, accepted_at) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (parent_snapshot_id, content_fingerprint) DO NOTHING",
        [sid, parent, stage, fp, observed_at, accepted_at],
    ).fetchone()[0]
    present = con.execute(
        "SELECT snapshot_id FROM competition_snapshot "
        "WHERE parent_snapshot_id = ? AND content_fingerprint = ?",
        [parent, fp],
    ).fetchone()[0]
    return present, inserted == 1
