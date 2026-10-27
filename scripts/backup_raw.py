"""Back up the irreplaceable layer: ``data/raw/`` to a second location.

The database is derivable; raw is not. A raw bundle plus ``replay`` rebuilds
any snapshot, so the backup copies raw bundles with their SHA-256 sidecars and
verifies the copy by comparing file hashes. The ``.duckdb`` file is
deliberately not backed up here: back that up and the first instinct on call
is to restore a derived file over the ledger.

Usage::

    uv run python scripts/backup_raw.py --dest D:\\dataderby-backup
    uv run python scripts/backup_raw.py --dest D:\\dataderby-backup --raw-dir data/raw

Standard library only. Exit 0 when every file verified, 1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        type=Path,
        default=os.environ.get("DATADERBY_BACKUP_DIR"),
        help="backup root (or set DATADERBY_BACKUP_DIR)",
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args()

    if args.dest is None:
        print(
            "backup_raw: no destination: pass --dest or set DATADERBY_BACKUP_DIR", file=sys.stderr
        )
        return 1
    if not args.raw_dir.is_dir():
        print(f"backup_raw: raw directory does not exist: {args.raw_dir}", file=sys.stderr)
        return 1

    files = sorted(p for p in args.raw_dir.rglob("*") if p.is_file())
    if not files:
        print(f"backup_raw: nothing to back up in {args.raw_dir}", file=sys.stderr)
        return 1

    failures = 0
    for source in files:
        target = args.dest / source.relative_to(args.raw_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if _sha256(source) != _sha256(target):
            print(f"backup_raw: MISMATCH {source}", file=sys.stderr)
            failures += 1

    print(f"backup_raw: {len(files) - failures}/{len(files)} files verified in {args.dest}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
