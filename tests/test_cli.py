"""CLI tests."""

from __future__ import annotations

from pathlib import Path

from dataderby.fixtures.cli import main
from dataderby.fixtures.competitions import get_competition
from dataderby.fixtures.service import refresh
from tests.helpers import csv_bytes


def _seeded(tmp_path: Path) -> Path:
    competition = get_competition("epl")
    db_path = tmp_path / "fixtures.sqlite3"
    refresh(
        db_path,
        tmp_path / "data",
        (competition,),
        fetcher=lambda slug: csv_bytes(),
    )
    return db_path


def test_competitions_lists_stored_rows(tmp_path: Path, capsys: object) -> None:
    db_path = _seeded(tmp_path)

    assert main(["competitions", "--db", str(db_path)]) == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert "English Premier League" in captured.out
    assert "1 of 12 configured competitions stored" in captured.out


def test_show_rejects_unknown_competition(tmp_path: Path) -> None:
    db_path = _seeded(tmp_path)

    assert main(["show", "nope", "--db", str(db_path)]) == 4


def test_show_renders_ist_kickoff(tmp_path: Path, capsys: object) -> None:
    db_path = _seeded(tmp_path)

    assert main(["show", "epl", "--limit", "1", "--db", str(db_path)]) == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert "2026-08-22 00:30" in captured.out
    assert "Arsenal" in captured.out


def test_definitions_module_imports() -> None:
    from dataderby.fixtures import definitions

    assert definitions.defs is not None
