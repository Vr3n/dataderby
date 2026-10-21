"""Fixture calendar ingestion.

The source publishes one CSV per competition. This package downloads the UTC export,
converts kick-off times to Asia/Kolkata, and stores the calendar in SQLite so that
Dagster can schedule scrapes around real kick-offs.
"""

from dataderby.fixtures.competitions import COMPETITIONS, Competition, get_competition

__all__ = ["COMPETITIONS", "Competition", "get_competition"]
