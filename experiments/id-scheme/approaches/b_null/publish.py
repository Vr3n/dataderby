"""Variant B-null: ULID + UNIQUE(parent, content) with a NULL parent for the first row.

This is not a candidate. It exists to measure the trap: SQL treats NULLs as distinct in
a UNIQUE constraint, so the very first observation can be inserted twice.

It also changes the natural key semantics — the root edge is not deduped *by the
database*, only by the application's "compare to checkpoint" rule. The test exercises
the case where that rule is unavailable (lost or stale checkpoint).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import common
from approaches.b_ulid.publish import ulid

NAME = "B-null"
SCHEME = "ULID + UNIQUE(parent, content), NULL parent at the root"


def create_schema(con: Any) -> None:
    common.create_schema(con, unique_edge=True, parent_nullable=True)


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
    stored_parent = None if parent == common.GENESIS else parent
    inserted = con.execute(
        "INSERT INTO competition_snapshot "
        "(snapshot_id, parent_snapshot_id, stage_id, content_fingerprint, "
        " observed_at, accepted_at) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (parent_snapshot_id, content_fingerprint) DO NOTHING",
        [sid, stored_parent, stage, fp, observed_at, accepted_at],
    ).fetchone()[0]
    if stored_parent is None:
        present = con.execute(
            "SELECT snapshot_id FROM competition_snapshot "
            "WHERE parent_snapshot_id IS NULL AND content_fingerprint = ? "
            "ORDER BY accepted_at LIMIT 1",
            [fp],
        ).fetchone()[0]
    else:
        present = con.execute(
            "SELECT snapshot_id FROM competition_snapshot "
            "WHERE parent_snapshot_id = ? AND content_fingerprint = ?",
            [stored_parent, fp],
        ).fetchone()[0]
    return present, inserted == 1
