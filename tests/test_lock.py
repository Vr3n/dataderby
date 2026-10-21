"""Exclusive pipeline-lock tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from dataderby.lock import LockHeld, exclusive_lock


def test_lock_is_exclusive_then_reusable(tmp_path: Path) -> None:
    path = tmp_path / "pipeline.lock"

    with exclusive_lock(path), pytest.raises(LockHeld), exclusive_lock(path):
        pass

    with exclusive_lock(path):
        pass
