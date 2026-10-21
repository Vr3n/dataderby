"""Cross-platform exclusive pipeline lock."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class LockHeld(RuntimeError):
    """Raised when another process holds the pipeline lock."""


@contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    """Hold an OS-level exclusive lock for the duration of the block.

    The lock is released by the OS if the process dies, so a stale lock file is
    not a stale lock.

    Args:
        path: Lock-file path. Its parent is created if needed.

    Yields:
        Control to the caller's block.

    Raises:
        LockHeld: If another process already holds the lock.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    locked = False

    try:
        if os.name == "nt":
            import msvcrt

            try:
                handle.seek(0)
                if handle.read(1) == b"":
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise LockHeld(f"pipeline lock is held: {path}") from exc
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise LockHeld(f"pipeline lock is held: {path}") from exc

        locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
