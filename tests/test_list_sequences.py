"""Tests for sequence discovery in nested show folders."""

from __future__ import annotations

from pathlib import Path

import pytest

from xlights_mcp import server
from xlights_mcp.config import ServerConfig


@pytest.fixture
def show(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "xlights_rgbeffects.xml").write_text("<xrgb/>")
    (tmp_path / "Top Level.xsq").write_text("<xsequence/>")
    nested = tmp_path / "Sequences" / "2025" / "Jingle"
    nested.mkdir(parents=True)
    (nested / "Jingle Bells.xsq").write_text("<xsequence/>")
    backup = tmp_path / "Backup" / "2025-12-01_OnStart"
    backup.mkdir(parents=True)
    (backup / "Jingle Bells.xsq").write_text("<xsequence/>")
    cache = tmp_path / "RenderCache"
    cache.mkdir()
    (cache / "Cached.xsq").write_text("<xsequence/>")

    config = ServerConfig(show_folders={"test": str(tmp_path)}, active_show="test")
    monkeypatch.setattr(server, "_config", config)
    return tmp_path


def test_list_sequences_includes_subfolders_and_skips_backups(show: Path):
    result = server.list_sequences()
    names = sorted(s["name"] for s in result["sequences"])
    assert names == ["Jingle Bells", "Top Level"]
    jingle = next(s for s in result["sequences"] if s["name"] == "Jingle Bells")
    assert "Backup" not in Path(jingle["path"]).parts


def test_inspect_sequence_finds_nested_sequence(show: Path, monkeypatch: pytest.MonkeyPatch):
    seen: list[Path] = []
    import xlights_mcp.xlights.xsq_reader as reader

    monkeypatch.setattr(reader, "read_xsq_summary", lambda p: seen.append(p) or {"ok": True})
    assert server.inspect_sequence("Jingle Bells") == {"ok": True}
    assert seen[0] == show / "Sequences" / "2025" / "Jingle" / "Jingle Bells.xsq"


def test_inspect_sequence_missing(show: Path):
    assert "error" in server.inspect_sequence("Nope")
