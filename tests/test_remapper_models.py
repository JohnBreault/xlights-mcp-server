"""Unit tests for remapper Pydantic data models."""

from __future__ import annotations

import pytest

from xlights_mcp.remapper.models import (
    AssetStatus,
    ExtractedAsset,
    ImportedModelMeta,
    ImportedSequenceData,
    MappingReport,
    MatchCandidate,
    MatchRule,
    ModelMapping,
    RemapRequest,
    RemapResult,
    UnmatchedModel,
)


# ---------------------------------------------------------------------------
# MatchCandidate
# ---------------------------------------------------------------------------


class TestMatchCandidate:
    def test_derived_normalized_name(self):
        c = MatchCandidate(name="  Mega Tree  ", source="user")
        assert c.normalized_name == "mega tree"

    def test_derived_name_tokens(self):
        c = MatchCandidate(name="Snowflake Left 1", source="imported")
        # "left" and "1" are filler words
        assert c.name_tokens == ["snowflake"]

    def test_singing_derived_from_face_definitions(self):
        c = MatchCandidate(
            name="Snowman",
            source="user",
            face_definitions=["Singing Face"],
        )
        assert c.is_singing is True

    def test_name_must_be_non_empty(self):
        with pytest.raises(ValueError, match="non-empty"):
            MatchCandidate(name="", source="user")

    def test_name_must_not_be_whitespace(self):
        with pytest.raises(ValueError, match="non-empty"):
            MatchCandidate(name="   ", source="user")

    def test_pixel_count_non_negative(self):
        with pytest.raises(ValueError, match=">= 0"):
            MatchCandidate(name="A", source="user", pixel_count=-1)

    def test_default_pixel_count(self):
        c = MatchCandidate(name="A", source="user")
        assert c.pixel_count == 0

    def test_group_candidate(self):
        c = MatchCandidate(name="All Arches", source="user", is_group=True)
        assert c.is_group is True
        assert c.pixel_count == 0


# ---------------------------------------------------------------------------
# ModelMapping
# ---------------------------------------------------------------------------


class TestModelMapping:
    def test_exact_name_mapping(self):
        m = ModelMapping(
            imported_name="Mega Tree",
            user_name="Mega Tree",
            rule=MatchRule.EXACT_NAME,
            confidence=1.0,
        )
        assert m.pixel_ratio is None

    def test_confidence_out_of_range(self):
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            ModelMapping(
                imported_name="A",
                user_name="B",
                rule=MatchRule.EXACT_NAME,
                confidence=1.5,
            )

    def test_negative_confidence(self):
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            ModelMapping(
                imported_name="A",
                user_name="B",
                rule=MatchRule.EXACT_NAME,
                confidence=-0.1,
            )

    def test_pixel_ratio_range(self):
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            ModelMapping(
                imported_name="A",
                user_name="B",
                rule=MatchRule.MODEL_TYPE,
                confidence=0.8,
                pixel_ratio=1.5,
            )

    def test_pixel_ratio_required_for_model_type(self):
        with pytest.raises(ValueError, match="pixel_ratio is required"):
            ModelMapping(
                imported_name="A",
                user_name="B",
                rule=MatchRule.MODEL_TYPE,
                confidence=0.8,
            )

    def test_pixel_ratio_required_for_similar_prop(self):
        with pytest.raises(ValueError, match="pixel_ratio is required"):
            ModelMapping(
                imported_name="A",
                user_name="B",
                rule=MatchRule.SIMILAR_PROP,
                confidence=0.7,
            )

    def test_pixel_ratio_required_for_fallback(self):
        with pytest.raises(ValueError, match="pixel_ratio is required"):
            ModelMapping(
                imported_name="A",
                user_name="B",
                rule=MatchRule.PIXEL_COUNT_FALLBACK,
                confidence=0.6,
            )

    def test_pixel_ratio_not_required_for_exact_name(self):
        m = ModelMapping(
            imported_name="A",
            user_name="B",
            rule=MatchRule.EXACT_NAME,
            confidence=1.0,
        )
        assert m.pixel_ratio is None

    def test_names_must_be_non_empty(self):
        with pytest.raises(ValueError, match="non-empty"):
            ModelMapping(
                imported_name="",
                user_name="B",
                rule=MatchRule.EXACT_NAME,
            )

    def test_shared_tokens(self):
        m = ModelMapping(
            imported_name="Snowflake Left",
            user_name="Large Snowflake",
            rule=MatchRule.SIMILAR_WORD,
            confidence=0.8,
            shared_tokens=["snowflake"],
        )
        assert m.shared_tokens == ["snowflake"]


# ---------------------------------------------------------------------------
# MappingReport invariants
# ---------------------------------------------------------------------------


class TestMappingReport:
    def test_valid_report(self):
        r = MappingReport(
            mappings=[
                ModelMapping(
                    imported_name="A",
                    user_name="B",
                    rule=MatchRule.EXACT_NAME,
                    confidence=1.0,
                )
            ],
            unmatched_imported=[
                UnmatchedModel(name="C", source="imported", reason="No match")
            ],
            unmatched_user=[],
            total_imported_models=2,
            total_user_models=1,
            total_matched=1,
            match_rule_distribution={"exact_name": 1},
            imported_source="/test.xsq",
        )
        assert r.total_matched == 1

    def test_total_matched_invariant(self):
        with pytest.raises(ValueError, match="total_matched"):
            MappingReport(
                mappings=[],
                total_imported_models=0,
                total_user_models=0,
                total_matched=1,  # wrong
                match_rule_distribution={},
            )

    def test_total_imported_invariant(self):
        with pytest.raises(ValueError, match="total_imported_models"):
            MappingReport(
                mappings=[
                    ModelMapping(
                        imported_name="A",
                        user_name="B",
                        rule=MatchRule.EXACT_NAME,
                    )
                ],
                total_imported_models=5,  # wrong: should be 1
                total_user_models=1,
                total_matched=1,
                match_rule_distribution={"exact_name": 1},
            )

    def test_distribution_sum_invariant(self):
        with pytest.raises(ValueError, match="match_rule_distribution sum"):
            MappingReport(
                mappings=[
                    ModelMapping(
                        imported_name="A",
                        user_name="B",
                        rule=MatchRule.EXACT_NAME,
                    )
                ],
                total_imported_models=1,
                total_user_models=1,
                total_matched=1,
                match_rule_distribution={"exact_name": 2},  # wrong sum
            )

    def test_empty_report_valid(self):
        r = MappingReport(
            total_imported_models=0,
            total_user_models=0,
            total_matched=0,
            match_rule_distribution={},
        )
        assert r.total_matched == 0


# ---------------------------------------------------------------------------
# RemapRequest
# ---------------------------------------------------------------------------


class TestRemapRequest:
    def test_valid_xsq_path(self):
        r = RemapRequest(import_path="/path/to/song.xsq")
        assert r.pixel_threshold == 0.70

    def test_valid_zip_path(self):
        r = RemapRequest(import_path="/path/to/package.zip")
        assert r.import_path.endswith(".zip")

    def test_invalid_extension(self):
        with pytest.raises(ValueError, match=".xsq or .zip"):
            RemapRequest(import_path="/path/to/song.mp3")

    def test_threshold_too_high(self):
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            RemapRequest(import_path="/a.xsq", pixel_threshold=1.5)

    def test_threshold_too_low(self):
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            RemapRequest(import_path="/a.xsq", pixel_threshold=-0.1)

    def test_override_empty_key(self):
        with pytest.raises(ValueError, match="non-empty"):
            RemapRequest(import_path="/a.xsq", overrides={"": "B"})

    def test_override_empty_value(self):
        with pytest.raises(ValueError, match="non-empty"):
            RemapRequest(import_path="/a.xsq", overrides={"A": ""})


# ---------------------------------------------------------------------------
# RemapResult
# ---------------------------------------------------------------------------


class TestRemapResult:
    def test_success_result(self):
        r = RemapResult(success=True, output_path="/out.xsq")
        assert r.error is None

    def test_error_result(self):
        r = RemapResult(success=False, error="File not found")
        assert r.mapping_report is None


# ---------------------------------------------------------------------------
# ImportedSequenceData
# ---------------------------------------------------------------------------


class TestImportedSequenceData:
    def test_basic_fields(self):
        d = ImportedSequenceData(
            file_name="test.xsq",
            model_names=["A", "B"],
            total_effects=10,
        )
        assert len(d.model_names) == 2
        assert d.total_effects == 10

    def test_defaults(self):
        d = ImportedSequenceData(file_name="test.xsq")
        assert d.song_title == ""
        assert d.model_names == []
        assert d.duration_ms == 0


# ---------------------------------------------------------------------------
# ImportedModelMeta
# ---------------------------------------------------------------------------


class TestImportedModelMeta:
    def test_basic_model_meta(self):
        m = ImportedModelMeta(
            name="Mega Tree",
            display_as="Tree Flat",
            pixel_count=1000,
        )
        assert m.is_group is False
        assert m.group_members == []

    def test_group_meta(self):
        m = ImportedModelMeta(
            name="All Arches",
            is_group=True,
            group_members=["Arch 1", "Arch 2"],
        )
        assert m.is_group is True


# ---------------------------------------------------------------------------
# ExtractedAsset
# ---------------------------------------------------------------------------


class TestExtractedAsset:
    def test_extracted_asset(self):
        a = ExtractedAsset(
            archive_path="Videos/intro.mp4",
            destination_path="/show/Videos/intro.mp4",
            status=AssetStatus.EXTRACTED,
            file_type=".mp4",
            size_bytes=15_000_000,
        )
        assert a.status == AssetStatus.EXTRACTED

    def test_skipped_asset(self):
        a = ExtractedAsset(
            archive_path="__MACOSX/._junk",
            destination_path="",
            status=AssetStatus.SKIPPED,
            file_type="",
        )
        assert a.status == AssetStatus.SKIPPED
