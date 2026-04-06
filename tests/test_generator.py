"""Unit tests for the generator module (XML cloning, naming, writing)."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from xlights_mcp.remapper.generator import (
    _clone_and_remap_tree,
    generate_remapped_sequence,
    next_remapped_path,
)
from xlights_mcp.remapper.importer import parse_xsq
from xlights_mcp.remapper.models import (
    MappingReport,
    MatchRule,
    ModelMapping,
    UnmatchedModel,
)

FIXTURES = Path(__file__).parent / "fixtures" / "remapping"


# ---------------------------------------------------------------------------
# next_remapped_path  (T012)
# ---------------------------------------------------------------------------


class TestNextRemappedPath:
    def test_first_remapped(self, tmp_path):
        result = next_remapped_path("TestSong", tmp_path)
        assert result.name == "TestSong (remapped 1).xsq"

    def test_increments(self, tmp_path):
        (tmp_path / "TestSong (remapped 1).xsq").touch()
        result = next_remapped_path("TestSong", tmp_path)
        assert result.name == "TestSong (remapped 2).xsq"

    def test_skips_gaps(self, tmp_path):
        (tmp_path / "TestSong (remapped 1).xsq").touch()
        (tmp_path / "TestSong (remapped 3).xsq").touch()
        result = next_remapped_path("TestSong", tmp_path)
        assert result.name == "TestSong (remapped 4).xsq"

    def test_ignores_other_files(self, tmp_path):
        (tmp_path / "OtherSong (remapped 5).xsq").touch()
        result = next_remapped_path("TestSong", tmp_path)
        assert result.name == "TestSong (remapped 1).xsq"


# ---------------------------------------------------------------------------
# _clone_and_remap_tree  (T011)
# ---------------------------------------------------------------------------


class TestCloneAndRemapTree:
    def test_preserves_original(self):
        _, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        mappings = [
            ModelMapping(
                imported_name="Mega Tree",
                user_name="My Tree",
                rule=MatchRule.EXACT_NAME,
            )
        ]
        _clone_and_remap_tree(root, mappings, set())
        # Original should be unchanged
        display = root.find("DisplayElements")
        names = [e.get("name") for e in display if e.get("type") == "model"]
        assert "Mega Tree" in names

    def test_renames_in_display_elements(self):
        _, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        mappings = [
            ModelMapping(
                imported_name="Mega Tree",
                user_name="My Big Tree",
                rule=MatchRule.EXACT_NAME,
            )
        ]
        new_root = _clone_and_remap_tree(root, mappings, set())
        display = new_root.find("DisplayElements")
        names = [e.get("name") for e in display if e.get("type") == "model"]
        assert "My Big Tree" in names
        assert "Mega Tree" not in names

    def test_renames_in_element_effects(self):
        _, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        mappings = [
            ModelMapping(
                imported_name="Arch Left",
                user_name="Arch Right",
                rule=MatchRule.EXACT_NAME,
            )
        ]
        new_root = _clone_and_remap_tree(root, mappings, set())
        effects = new_root.find("ElementEffects")
        model_names = [
            e.get("name") for e in effects if e.get("type") == "model"
        ]
        assert "Arch Right" in model_names

    def test_removes_unmatched(self):
        _, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        new_root = _clone_and_remap_tree(root, [], {"Snowflake 1"})
        display = new_root.find("DisplayElements")
        names = [e.get("name") for e in display if e.get("type") == "model"]
        assert "Snowflake 1" not in names

    def test_preserves_timing_tracks(self):
        _, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        new_root = _clone_and_remap_tree(root, [], set())
        effects = new_root.find("ElementEffects")
        timing_names = [
            e.get("name") for e in effects if e.get("type") == "timing"
        ]
        assert "Lyrics" in timing_names


# ---------------------------------------------------------------------------
# generate_remapped_sequence  (T013, T017)
# ---------------------------------------------------------------------------


class TestGenerateRemappedSequence:
    def test_writes_valid_xml(self, tmp_path):
        _, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        report = MappingReport(
            mappings=[
                ModelMapping(
                    imported_name="Mega Tree",
                    user_name="My Tree",
                    rule=MatchRule.EXACT_NAME,
                )
            ],
            unmatched_imported=[
                UnmatchedModel(name="Arch Left", source="imported", reason="No match"),
                UnmatchedModel(name="Snowflake 1", source="imported", reason="No match"),
            ],
            total_imported_models=3,
            total_user_models=1,
            total_matched=1,
            match_rule_distribution={"exact_name": 1},
        )
        output_path, _, _ = generate_remapped_sequence(
            root, report, tmp_path, base_name="TestSong"
        )
        assert output_path.exists()
        # Verify it's valid XML
        parsed = etree.parse(str(output_path))
        assert parsed.getroot().tag == "xsequence"

    def test_incremented_naming(self, tmp_path):
        _, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        report = MappingReport(
            mappings=[],
            total_imported_models=0,
            total_user_models=0,
            total_matched=0,
            match_rule_distribution={},
        )
        path1, _, _ = generate_remapped_sequence(
            root, report, tmp_path, base_name="Song"
        )
        assert path1.name == "Song (remapped 1).xsq"

        path2, _, _ = generate_remapped_sequence(
            root, report, tmp_path, base_name="Song"
        )
        assert path2.name == "Song (remapped 2).xsq"
