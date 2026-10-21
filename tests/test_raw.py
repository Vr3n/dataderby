"""Raw landing tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dataderby.config import load_settings
from dataderby.raw import RawPayload, target_dir, write_bundle

_SPEC = load_settings(Path("config/stages.toml")).stages["epl-2026-2027"]
_OBSERVED = datetime(2026, 10, 21, 10, 1, 2, 345678, tzinfo=UTC)


def _payload(section: str, view: str, body: bytes) -> RawPayload:
    return RawPayload(
        section=section,
        view=view,
        body=body,
        captured_at=_OBSERVED,
        url="https://www.whoscored.com/example",
        content_type="text/html",
        status=200,
        attempt=1,
    )


def test_writes_a_bundle_and_sidecars(tmp_path: Path) -> None:
    payloads = (
        _payload("page", "show", b"<html>page</html>"),
        _payload("summary", "overall", b'{"teamTableStats":[]}'),
    )

    files = write_bundle(tmp_path, _SPEC, _OBSERVED, payloads)

    directory = target_dir(tmp_path, _SPEC, _OBSERVED)
    assert directory.name == "2026-10-21T10-01-02.345678Z"
    assert (directory / "page__show.html").read_bytes() == b"<html>page</html>"
    assert (directory / "summary__overall.json").read_bytes() == b'{"teamTableStats":[]}'
    assert files[0].path == directory / "page__show.html"
    assert files[0].sha256 == "639cf5f89793ec65e282fe1de4de829b3ffe7095c04517cf64156d0d35579f56"
    assert files[0].byte_count == len(b"<html>page</html>")

    meta = json.loads((directory / "page__show.html.meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == 200
    assert meta["bytes"] == len(b"<html>page</html>")
    assert meta["sha256"] == files[0].sha256


def test_never_overwrites_the_same_observed_at(tmp_path: Path) -> None:
    payload = (_payload("page", "show", b"<html>first</html>"),)
    write_bundle(tmp_path, _SPEC, _OBSERVED, payload)

    with pytest.raises(FileExistsError):
        write_bundle(tmp_path, _SPEC, _OBSERVED, payload)

    directory = target_dir(tmp_path, _SPEC, _OBSERVED)
    assert (directory / "page__show.html").read_bytes() == b"<html>first</html>"


def test_duplicate_section_view_is_rejected(tmp_path: Path) -> None:
    payloads = (
        _payload("summary", "overall", b"a"),
        _payload("summary", "overall", b"b"),
    )

    with pytest.raises(ValueError, match="duplicate"):
        write_bundle(tmp_path, _SPEC, _OBSERVED, payloads)


def test_naive_observed_at_is_rejected(tmp_path: Path) -> None:
    naive = datetime(2026, 10, 21, 10, 1, 2)

    with pytest.raises(ValueError, match="timezone-aware"):
        target_dir(tmp_path, _SPEC, naive)
