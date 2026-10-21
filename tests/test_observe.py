"""JSON-lines logging tests."""

from __future__ import annotations

import json
from pathlib import Path

from pytest import CaptureFixture

from dataderby.observe import log


def test_log_appends_one_json_object_per_event(tmp_path: Path) -> None:
    log("run.start", log_dir=tmp_path, run_id="run_1", whoscored_stage_id=25544)
    log("run.landed", log_dir=tmp_path, run_id="run_1", files=12)

    paths = list(tmp_path.glob("*.jsonl"))
    assert len(paths) == 1
    records = [json.loads(line) for line in paths[0].read_text(encoding="utf-8").splitlines()]
    assert [record["event"] for record in records] == ["run.start", "run.landed"]
    assert records[0]["run_id"] == "run_1"
    assert records[0]["whoscored_stage_id"] == 25544
    assert records[1]["files"] == 12


def test_verbose_also_writes_to_stderr(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    log("run.start", log_dir=tmp_path, verbose=True, run_id="run_1")

    captured = capsys.readouterr()
    assert '"event": "run.start"' in captured.err
