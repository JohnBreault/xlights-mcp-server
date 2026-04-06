"""Unit tests for the importer module (xsq parsing, zip extraction, metadata)."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from xlights_mcp.remapper.importer import parse_xsq, _parse_imported_metadata

FIXTURES = Path(__file__).parent / "fixtures" / "remapping"


# ---------------------------------------------------------------------------
# parse_xsq  (T015)
# ---------------------------------------------------------------------------


class TestParseXsq:
    def test_model_names_extracted(self):
        seq_data, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        assert "Mega Tree" in seq_data.model_names
        assert "Arch Left" in seq_data.model_names
        assert "Snowflake 1" in seq_data.model_names
        assert len(seq_data.model_names) == 3

    def test_timing_track_names_extracted(self):
        seq_data, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        assert "Lyrics" in seq_data.timing_track_names

    def test_media_file_parsed(self):
        seq_data, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        assert seq_data.media_file == "audio.mp3"

    def test_song_title_parsed(self):
        seq_data, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        assert seq_data.song_title == "TestSong"

    def test_artist_parsed(self):
        seq_data, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        assert seq_data.artist == "Test Artist"

    def test_duration_parsed(self):
        seq_data, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        assert seq_data.duration_ms == 60000

    def test_effect_counts(self):
        seq_data, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        # 2 timing effects + 2 Mega Tree L1 + 1 Mega Tree L2 + 1 Arch + 2 Snowflake = 8
        assert seq_data.total_effects == 8

    def test_palette_count(self):
        seq_data, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        assert seq_data.palette_count == 2

    def test_effect_db_count(self):
        seq_data, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        assert seq_data.effect_db_count == 3

    def test_returns_lxml_root(self):
        seq_data, root = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        assert root.tag == "xsequence"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_xsq(Path("/nonexistent/file.xsq"))

    def test_corrupt_xml(self, tmp_path):
        bad_file = tmp_path / "corrupt.xsq"
        bad_file.write_text("this is not xml at all!")
        with pytest.raises(etree.XMLSyntaxError):
            parse_xsq(bad_file)

    def test_file_name_set(self):
        seq_data, _ = parse_xsq(FIXTURES / "minimal_sequence.xsq")
        assert seq_data.file_name == "minimal_sequence.xsq"


# ---------------------------------------------------------------------------
# _parse_imported_metadata  (T030 partial)
# ---------------------------------------------------------------------------


class TestParseImportedMetadata:
    def test_model_metadata(self):
        metas = _parse_imported_metadata(FIXTURES / "minimal_rgbeffects.xml")
        names = {m.name for m in metas}
        assert "Mega Tree" in names
        assert "Arch Left" in names

    def test_pixel_count_computed(self):
        metas = _parse_imported_metadata(FIXTURES / "minimal_rgbeffects.xml")
        mega_tree = next(m for m in metas if m.name == "Mega Tree")
        # parm1=25, parm2=40 → 1000
        assert mega_tree.pixel_count == 1000

    def test_display_as(self):
        metas = _parse_imported_metadata(FIXTURES / "minimal_rgbeffects.xml")
        mega_tree = next(m for m in metas if m.name == "Mega Tree")
        assert mega_tree.display_as == "Tree Flat"

    def test_face_definitions(self):
        metas = _parse_imported_metadata(FIXTURES / "minimal_rgbeffects.xml")
        snowflake = next(m for m in metas if m.name == "Snowflake 1")
        assert "Singing Snowflake" in snowflake.face_definitions

    def test_group_detection(self):
        metas = _parse_imported_metadata(FIXTURES / "minimal_rgbeffects.xml")
        group = next(m for m in metas if m.name == "All Arches")
        assert group.is_group is True
        assert "Arch Left" in group.group_members

    def test_nonexistent_file(self):
        result = _parse_imported_metadata(Path("/nonexistent.xml"))
        assert result == []
