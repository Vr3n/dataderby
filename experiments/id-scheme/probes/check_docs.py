"""Lint the two new markdown documents for table width drift."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

for name in ("docs/production-patterns-research.md", "plans/v1-build-plan.md"):
    text = (ROOT / name).read_text(encoding="utf-8")
    breaks: list[tuple[int, int, int]] = []
    prev: int | None = None
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            width = stripped.count("|")
            if prev is not None and width != prev:
                breaks.append((number, width, prev))
            prev = width
        else:
            prev = None
    print(f"{name}: {len(text.splitlines())} lines, table breaks: {breaks or 'none'}")
