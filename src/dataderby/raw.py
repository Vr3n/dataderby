"""Atomic raw landing for page, standings, and feed payloads."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from dataderby.config import StageSpec


@dataclass(frozen=True, slots=True)
class RawPayload:
    """One page, standings view, or feed body to archive."""

    section: str
    view: str
    body: bytes
    captured_at: datetime
    url: str
    content_type: str | None = None
    status: int = 200
    attempt: int = 1
    is_gate: bool = False


@dataclass(frozen=True, slots=True)
class RawFile:
    """One archived file and the metadata needed for the ledger."""

    section: str
    view: str
    path: Path
    sha256: str
    byte_count: int
    captured_at: datetime
    url: str
    content_type: str | None
    status: int
    attempt: int
    is_gate: bool


def _stamp(observed_at: datetime) -> str:
    if observed_at.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware")
    return observed_at.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%S.%fZ")


def target_dir(root: Path, spec: StageSpec, observed_at: datetime) -> Path:
    """Return the run's raw directory without creating it."""
    return (
        root
        / str(spec.whoscored_tournament_id)
        / str(spec.whoscored_season_id)
        / str(spec.whoscored_stage_id)
        / _stamp(observed_at)
    )


def _file_name(section: str, view: str) -> str:
    suffix = ".html" if section == "page" else ".json"
    return f"{section}__{view}{suffix}"


def _write_exclusive(path: Path, body: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def _meta(payload: RawPayload, sha256: str) -> bytes:
    record = {
        "url": payload.url,
        "status": payload.status,
        "content_type": payload.content_type,
        "sha256": sha256,
        "bytes": len(payload.body),
        "attempt": payload.attempt,
        "captured_at": payload.captured_at.isoformat(),
    }
    return json.dumps(record, sort_keys=True).encode("utf-8")


def write_bundle(
    root: Path,
    spec: StageSpec,
    observed_at: datetime,
    payloads: tuple[RawPayload, ...],
) -> tuple[RawFile, ...]:
    """Write one run's payloads as an all-or-nothing directory.

    The files are written under a temporary sibling directory and the directory
    is renamed into place only after every file and sidecar exists. An existing
    target is never overwritten.

    Args:
        root: Raw root, normally ``data/raw``.
        spec: Stage configuration.
        observed_at: The run's fixed observation timestamp.
        payloads: Page, standings, and nine feed bodies.

    Returns:
        Archived files in the same order as ``payloads``.

    Raises:
        ValueError: If two payloads share a ``(section, view)`` key.
        FileExistsError: If the target directory already exists.
    """
    keys = [(payload.section, payload.view) for payload in payloads]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate raw payload section/view")

    destination = target_dir(root, spec, observed_at)
    if destination.exists():
        raise FileExistsError(f"raw capture already exists: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    temporary.mkdir()
    archived: list[RawFile] = []

    try:
        for payload in payloads:
            filename = _file_name(payload.section, payload.view)
            path = temporary / filename
            _write_exclusive(path, payload.body)
            sha256 = hashlib.sha256(payload.body).hexdigest()
            _write_exclusive(
                temporary / f"{filename}.meta.json",
                _meta(payload, sha256),
            )
            archived.append(
                RawFile(
                    section=payload.section,
                    view=payload.view,
                    path=destination / filename,
                    sha256=sha256,
                    byte_count=len(payload.body),
                    captured_at=payload.captured_at,
                    url=payload.url,
                    content_type=payload.content_type,
                    status=payload.status,
                    attempt=payload.attempt,
                    is_gate=payload.is_gate,
                )
            )

        if destination.exists():
            raise FileExistsError(f"raw capture appeared while writing: {destination}")
        temporary.replace(destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    return tuple(archived)
