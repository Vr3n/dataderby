"""Shared fixtures for the test suite."""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence

HEADER: tuple[str, ...] = (
    "Match Number",
    "Round Number",
    "Date",
    "Location",
    "Home Team",
    "Away Team",
    "Result",
)

ROWS: tuple[tuple[str, ...], ...] = (
    ("1", "1", "21/08/2026 19:00", "Emirates Stadium", "Arsenal", "Coventry", "3 - 0"),
    ("2", "1", "22/08/2026 11:30", "MKM Stadium", "Hull", "Man Utd", ""),
)


def csv_bytes(
    rows: Sequence[Sequence[str]] = ROWS,
    header: Sequence[str] = HEADER,
) -> bytes:
    """Render rows as the source's CSV shape.

    Args:
        rows: Data rows.
        header: Column names.

    Returns:
        UTF-8 encoded CSV.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")
