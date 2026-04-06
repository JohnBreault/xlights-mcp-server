"""Integration tests for the full remap pipeline."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from lxml import etree

from xlights_mcp.remapper.importer import import_package, parse_xsq
from xlights_mcp.remapper.matcher import (
    build_candidates_from_import,
    build_candidates_from_user_show,
    match_models,
)
from xlights_mcp.remapper.generator import generate_remapped_sequence
from xlights_mcp.remapper.models import MatchRule
from xlights_mcp.xlights.models import LightModel, ModelGroup

FIXTURES = Path(__file__).parent / "fixtures" / "remapping"


# ---------------------------------------------------------------------------
# Helper: build a mock user show
# ---------------------------------------------------------------------------


def _user_models() -> list[LightModel]:
    return [
        LightModel(name="Mega Tree", display_as="Tree Flat", pixel_count=1000),
        LightModel(name="Arch Left", display_as="Arches", pixel_count=50),
        LightModel(name="My Snowflake", display_as="Custom", pixel_count=100),
    ]


def _user_groups() -> list[ModelGroup]:
    return [
        ModelGroup(name="All Arches", members=["Arch Left", "Arch Right"]),
    ]


# ---------------------------------------------------------------------------
# T018: Basic .xsq → remap pipeline
# ---------------------------------------------------------------------------


class TestBasicXsqPipeline:
    def test_end_to_end_xsq(self, tmp_path):
        """Full pipeline: parse → match → generate for standalone .xsq."""
        # Parse imported sequence
        seq_data, lxml_root = parse_xsq(FIXTURES / "minimal_sequence.xsq")

        # Build candidates
        user_cands = build_candidates_from_user_show(
            _user_models(), _user_groups()
        )
        imported_cands = build_candidates_from_import(seq_data.model_names)

        # Match
        report = match_models(
            imported_cands,
            user_cands,
            imported_source=str(FIXTURES / "minimal_sequence.xsq"),
        )

        # Verify matching results
        assert report.total_imported_models == 3
        assert report.total_matched >= 2  # Mega Tree and Arch Left should match

        matched_names = {m.imported_name for m in report.mappings}
        assert "Mega Tree" in matched_names
        assert "Arch Left" in matched_names

        # Generate
        output_path, missing, warnings = generate_remapped_sequence(
            lxml_root, report, tmp_path, base_name="TestSong"
        )

        # Verify output
        assert output_path.exists()
        assert output_path.name == "TestSong (remapped 1).xsq"

        # Verify output XML structure
        parsed = etree.parse(str(output_path))
        root = parsed.getroot()
        assert root.tag == "xsequence"

        # Verify matched models have effects
        effects = root.find("ElementEffects")
        model_names = [
            e.get("name") for e in effects if e.get("type") == "model"
        ]
        assert "Mega Tree" in model_names  # exact match
        assert "Arch Left" in model_names  # exact match

        # Verify timing preserved
        timing_names = [
            e.get("name") for e in effects if e.get("type") == "timing"
        ]
        assert "Lyrics" in timing_names

    def test_report_structure(self, tmp_path):
        """Verify report has all required fields."""
        seq_data, lxml_root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        user_cands = build_candidates_from_user_show(
            _user_models(), _user_groups()
        )
        imported_cands = build_candidates_from_import(seq_data.model_names)
        report = match_models(imported_cands, user_cands)

        # Report structure
        assert report.total_imported_models >= 0
        assert report.total_user_models >= 0
        assert report.total_matched == len(report.mappings)
        assert isinstance(report.match_rule_distribution, dict)

        # Every mapping has a rule
        for m in report.mappings:
            assert m.rule is not None
            assert isinstance(m.rule, MatchRule)


# ---------------------------------------------------------------------------
# T043: Full integration with zip (basic version)
# ---------------------------------------------------------------------------


class TestZipPipeline:
    def test_end_to_end_zip(self, tmp_path):
        """Full pipeline with a zip package containing .xsq + rgbeffects."""
        # Create a test zip
        zip_path = tmp_path / "test_package.zip"
        show_dir = tmp_path / "show"
        show_dir.mkdir()

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(
                FIXTURES / "minimal_sequence.xsq",
                "minimal_sequence.xsq",
            )
            zf.write(
                FIXTURES / "minimal_rgbeffects.xml",
                "xlights_rgbeffects.xml",
            )

        # Import
        seq_data, lxml_root, imported_meta, assets = import_package(
            zip_path, show_dir
        )

        assert seq_data.model_names
        assert imported_meta is not None
        assert len(assets) >= 2

        # Build candidates with metadata
        user_cands = build_candidates_from_user_show(
            _user_models(), _user_groups()
        )
        imported_cands = build_candidates_from_import(
            seq_data.model_names, imported_meta
        )

        # Match
        report = match_models(
            imported_cands,
            user_cands,
            has_imported_metadata=True,
        )

        assert report.total_matched >= 2

        # Generate
        output_path, _, _ = generate_remapped_sequence(
            lxml_root, report, show_dir, base_name="ZipTest"
        )
        assert output_path.exists()

    def test_incremented_naming_on_second_run(self, tmp_path):
        """Running twice produces (remapped 1) then (remapped 2)."""
        seq_data, lxml_root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        report = match_models(
            build_candidates_from_import(seq_data.model_names),
            build_candidates_from_user_show(_user_models(), _user_groups()),
        )

        p1, _, _ = generate_remapped_sequence(
            lxml_root, report, tmp_path, base_name="Song"
        )
        p2, _, _ = generate_remapped_sequence(
            lxml_root, report, tmp_path, base_name="Song"
        )
        assert p1.name == "Song (remapped 1).xsq"
        assert p2.name == "Song (remapped 2).xsq"
