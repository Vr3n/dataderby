"""Approach A: snapshot id derived from (parent, stage, content).

Dedupe is the primary key alone. No unique constraint on the edge, because the edge is
already encoded in the id.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

import common

NAME = "A-derived"
SCHEME = "snap_ + sha256(parent|stage|content_fp)[:32]"


def create_schema(con: Any) -> None:
    common.create_schema(con, unique_edge=False, parent_nullable=False)


def new_id(parent: str, stage: str, content_fp: str) -> str:
    digest = hashlib.sha256(f"{parent}|{stage}|{content_fp}".encode("utf-8"))
    return "snap_" + digest.hexdigest()[:32]


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
        "ON CONFLICT (snapshot_id) DO NOTHING",
        [sid, parent, stage, fp, observed_at, accepted_at],
    ).fetchone()[0]
    return sid, inserted == 1
