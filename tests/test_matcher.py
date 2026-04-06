"""Unit tests for the matcher module (all priority levels)."""

from __future__ import annotations

import pytest

from xlights_mcp.remapper.matcher import (
    _apply_overrides,
    _match_exact_name,
    _match_model_type,
    _match_pixel_count_fallback,
    _match_similar_prop,
    _match_similar_word,
    build_candidates_from_import,
    build_candidates_from_user_show,
    match_models,
    pixel_counts_compatible,
)
from xlights_mcp.remapper.models import (
    ImportedModelMeta,
    MatchCandidate,
    MatchRule,
)
from xlights_mcp.xlights.models import LightModel, ModelGroup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_candidate(
    name: str,
    source: str = "imported",
    pixel_count: int = 0,
    display_as: str = "",
    is_singing: bool = False,
    is_group: bool = False,
    face_definitions: list[str] | None = None,
) -> MatchCandidate:
    return MatchCandidate(
        name=name,
        source=source,
        pixel_count=pixel_count,
        display_as=display_as,
        is_singing=is_singing,
        is_group=is_group,
        face_definitions=face_definitions or [],
    )


def _pool(candidates: list[MatchCandidate]) -> dict[str, MatchCandidate]:
    return {c.name: c for c in candidates}


# ---------------------------------------------------------------------------
# pixel_counts_compatible  (T020)
# ---------------------------------------------------------------------------


class TestPixelCountsCompatible:
    def test_exact_match(self):
        assert pixel_counts_compatible(100, 100) is True

    def test_above_threshold(self):
        assert pixel_counts_compatible(80, 100) is True  # 0.80

    def test_below_threshold(self):
        assert pixel_counts_compatible(50, 100) is False  # 0.50

    def test_at_threshold(self):
        assert pixel_counts_compatible(70, 100) is True  # exactly 0.70

    def test_zero_a(self):
        assert pixel_counts_compatible(0, 100) is False

    def test_zero_b(self):
        assert pixel_counts_compatible(100, 0) is False

    def test_both_zero(self):
        assert pixel_counts_compatible(0, 0) is False

    def test_custom_threshold(self):
        assert pixel_counts_compatible(50, 100, threshold=0.50) is True


# ---------------------------------------------------------------------------
# build_candidates  (T007, T008)
# ---------------------------------------------------------------------------


class TestBuildCandidates:
    def test_from_user_show(self):
        models = [LightModel(name="Mega Tree", display_as="Tree", pixel_count=1000)]
        groups = [ModelGroup(name="All Arches", members=["Arch 1"])]
        cands = build_candidates_from_user_show(models, groups)
        assert len(cands) == 2
        assert cands[0].source == "user"
        assert cands[1].is_group is True

    def test_from_import_no_meta(self):
        cands = build_candidates_from_import(["A", "B"])
        assert len(cands) == 2
        assert cands[0].pixel_count == 0

    def test_from_import_with_meta(self):
        meta = [ImportedModelMeta(name="A", display_as="Tree", pixel_count=500)]
        cands = build_candidates_from_import(["A"], meta)
        assert cands[0].pixel_count == 500
        assert cands[0].display_as == "Tree"


# ---------------------------------------------------------------------------
# Priority 1: Exact name  (T016)
# ---------------------------------------------------------------------------


class TestMatchExactName:
    def test_case_insensitive(self):
        imp = _pool([_make_candidate("mega tree", "imported")])
        usr = _pool([_make_candidate("Mega Tree", "user")])
        mappings = _match_exact_name(imp, usr)
        assert len(mappings) == 1
        assert mappings[0].rule == MatchRule.EXACT_NAME

    def test_whitespace_trimmed(self):
        imp = _pool([_make_candidate("  Arch Left  ", "imported")])
        usr = _pool([_make_candidate("Arch Left", "user")])
        mappings = _match_exact_name(imp, usr)
        assert len(mappings) == 1

    def test_no_false_positive(self):
        imp = _pool([_make_candidate("Mega Tree", "imported")])
        usr = _pool([_make_candidate("Big Tree", "user")])
        mappings = _match_exact_name(imp, usr)
        assert len(mappings) == 0

    def test_pools_reduced(self):
        imp = _pool([
            _make_candidate("A", "imported"),
            _make_candidate("B", "imported"),
        ])
        usr = _pool([
            _make_candidate("A", "user"),
            _make_candidate("C", "user"),
        ])
        _match_exact_name(imp, usr)
        assert "A" not in imp
        assert "B" in imp
        assert "A" not in usr
        assert "C" in usr

    def test_singing_pool_isolation(self):
        """Singing and non-singing models CAN match by exact name
        within same pool (isolation is done at orchestrator level)."""
        imp = _pool([_make_candidate("Snowman", "imported", is_singing=True)])
        usr = _pool([_make_candidate("Snowman", "user", is_singing=False)])
        mappings = _match_exact_name(imp, usr)
        # Within the same pool call, exact name match works
        assert len(mappings) == 1


# ---------------------------------------------------------------------------
# Priority 2: Similar word  (T029 partial)
# ---------------------------------------------------------------------------


class TestMatchSimilarWord:
    def test_shared_token(self):
        imp = _pool([_make_candidate("Snowflake Left", "imported")])
        usr = _pool([_make_candidate("Large Snowflake", "user")])
        mappings = _match_similar_word(imp, usr)
        assert len(mappings) == 1
        assert "snowflake" in mappings[0].shared_tokens

    def test_filler_excluded(self):
        """'Left' is a filler word, shouldn't cause a match alone."""
        imp = _pool([_make_candidate("Something Left", "imported")])
        usr = _pool([_make_candidate("Other Left", "user")])
        mappings = _match_similar_word(imp, usr)
        # "left" is filler, "something" vs "other" have no overlap
        assert len(mappings) == 0

    def test_no_overlap(self):
        imp = _pool([_make_candidate("Alpha", "imported")])
        usr = _pool([_make_candidate("Beta", "user")])
        mappings = _match_similar_word(imp, usr)
        assert len(mappings) == 0


# ---------------------------------------------------------------------------
# Priority 3: Model type  (T025)
# ---------------------------------------------------------------------------


class TestMatchModelType:
    def test_same_type_compatible_pixels(self):
        imp = _pool([_make_candidate("X", "imported", pixel_count=100, display_as="Arches")])
        usr = _pool([_make_candidate("Y", "user", pixel_count=90, display_as="Arches")])
        mappings = _match_model_type(imp, usr)
        assert len(mappings) == 1
        assert mappings[0].rule == MatchRule.MODEL_TYPE

    def test_skip_without_metadata(self):
        imp = _pool([_make_candidate("X", "imported", display_as="")])
        usr = _pool([_make_candidate("Y", "user", display_as="Arches")])
        mappings = _match_model_type(imp, usr)
        assert len(mappings) == 0

    def test_incompatible_pixels(self):
        imp = _pool([_make_candidate("X", "imported", pixel_count=100, display_as="Arches")])
        usr = _pool([_make_candidate("Y", "user", pixel_count=10, display_as="Arches")])
        mappings = _match_model_type(imp, usr)
        assert len(mappings) == 0


# ---------------------------------------------------------------------------
# Priority 4: Similar prop  (T026)
# ---------------------------------------------------------------------------


class TestMatchSimilarProp:
    def test_shared_prop_word(self):
        imp = _pool([_make_candidate("My Snowflake", "imported", pixel_count=100)])
        usr = _pool([_make_candidate("Big Snowflake", "user", pixel_count=90)])
        mappings = _match_similar_prop(imp, usr)
        assert len(mappings) == 1
        assert "snowflake" in mappings[0].shared_tokens

    def test_incompatible_pixels(self):
        imp = _pool([_make_candidate("My Snowflake", "imported", pixel_count=100)])
        usr = _pool([_make_candidate("Big Snowflake", "user", pixel_count=10)])
        mappings = _match_similar_prop(imp, usr)
        assert len(mappings) == 0


# ---------------------------------------------------------------------------
# Priority 5: Pixel count fallback  (T034)
# ---------------------------------------------------------------------------


class TestMatchPixelCountFallback:
    def test_closest_pixel_count(self):
        imp = _pool([_make_candidate("A", "imported", pixel_count=100)])
        usr = _pool([
            _make_candidate("X", "user", pixel_count=95),
            _make_candidate("Y", "user", pixel_count=80),
        ])
        mappings = _match_pixel_count_fallback(imp, usr)
        assert len(mappings) == 1
        assert mappings[0].user_name == "X"

    def test_threshold_enforced(self):
        imp = _pool([_make_candidate("A", "imported", pixel_count=100)])
        usr = _pool([_make_candidate("X", "user", pixel_count=10)])
        mappings = _match_pixel_count_fallback(imp, usr)
        assert len(mappings) == 0

    def test_no_steal_from_higher_priority(self):
        """Fallback only applies to models still in the pool."""
        imp = _pool([_make_candidate("A", "imported", pixel_count=100)])
        usr = _pool([_make_candidate("X", "user", pixel_count=95)])
        # First, exact match removes them
        # Then fallback has empty pools
        _match_exact_name(imp, usr)  # no match (different names)
        assert len(imp) == 1  # still there
        mappings = _match_pixel_count_fallback(imp, usr)
        assert len(mappings) == 1

    def test_zero_pixel_count_skipped(self):
        imp = _pool([_make_candidate("A", "imported", pixel_count=0)])
        usr = _pool([_make_candidate("X", "user", pixel_count=100)])
        mappings = _match_pixel_count_fallback(imp, usr)
        assert len(mappings) == 0


# ---------------------------------------------------------------------------
# Manual overrides  (T042)
# ---------------------------------------------------------------------------


class TestApplyOverrides:
    def test_valid_override(self):
        imp = _pool([_make_candidate("Their Tree", "imported")])
        usr = _pool([_make_candidate("My Tree", "user")])
        mappings, warnings = _apply_overrides(
            {"Their Tree": "My Tree"}, imp, usr
        )
        assert len(mappings) == 1
        assert mappings[0].rule == MatchRule.MANUAL_OVERRIDE
        assert len(imp) == 0
        assert len(usr) == 0

    def test_invalid_imported_name(self):
        imp = _pool([_make_candidate("A", "imported")])
        usr = _pool([_make_candidate("B", "user")])
        mappings, warnings = _apply_overrides(
            {"Nonexistent": "B"}, imp, usr
        )
        assert len(mappings) == 0
        assert any("not found" in w for w in warnings)

    def test_invalid_user_name(self):
        imp = _pool([_make_candidate("A", "imported")])
        usr = _pool([_make_candidate("B", "user")])
        mappings, warnings = _apply_overrides(
            {"A": "Nonexistent"}, imp, usr
        )
        assert len(mappings) == 0
        assert any("not found" in w for w in warnings)

    def test_override_before_auto(self):
        """Override removes from pools so auto-matching doesn't see it."""
        imp = _pool([
            _make_candidate("A", "imported"),
            _make_candidate("B", "imported"),
        ])
        usr = _pool([
            _make_candidate("X", "user"),
            _make_candidate("Y", "user"),
        ])
        mappings, _ = _apply_overrides({"A": "X"}, imp, usr)
        assert len(mappings) == 1
        assert "A" not in imp
        assert "X" not in usr


# ---------------------------------------------------------------------------
# Full orchestrator  (T010)
# ---------------------------------------------------------------------------


class TestMatchModels:
    def test_basic_exact_match(self):
        imp = [_make_candidate("Mega Tree", "imported")]
        usr = [_make_candidate("Mega Tree", "user")]
        report = match_models(imp, usr)
        assert report.total_matched == 1
        assert report.mappings[0].rule == MatchRule.EXACT_NAME

    def test_singing_isolation(self):
        """Singing models should not match non-singing and vice versa."""
        imp = [
            _make_candidate("Snowman", "imported", is_singing=True,
                          face_definitions=["Face"]),
        ]
        usr = [
            _make_candidate("Snowman", "user", is_singing=False),
        ]
        report = match_models(imp, usr)
        # Singing model is in singing pool, non-singing in non-singing
        # They are in different pools so exact match won't find them
        assert report.total_matched == 0

    def test_with_overrides(self):
        imp = [_make_candidate("A", "imported"), _make_candidate("B", "imported")]
        usr = [_make_candidate("X", "user"), _make_candidate("B", "user")]
        report = match_models(
            imp, usr,
            overrides={"A": "X"},
        )
        # A→X via override, B→B via exact
        assert report.total_matched == 2
        override_map = next(
            m for m in report.mappings if m.rule == MatchRule.MANUAL_OVERRIDE
        )
        assert override_map.imported_name == "A"

    def test_report_invariants(self):
        imp = [_make_candidate("A", "imported")]
        usr = [_make_candidate("B", "user")]
        report = match_models(imp, usr)
        assert report.total_imported_models == 1
        assert report.total_user_models == 1
        assert report.total_matched == 0
        assert len(report.unmatched_imported) == 1
        assert len(report.unmatched_user) == 1

    def test_unmatched_has_reason(self):
        imp = [_make_candidate("A", "imported")]
        usr = [_make_candidate("B", "user")]
        report = match_models(imp, usr)
        assert report.unmatched_imported[0].reason != ""
        assert report.unmatched_user[0].reason != ""

    def test_report_statistics(self):
        imp = [
            _make_candidate("Mega Tree", "imported"),
            _make_candidate("Arch Left", "imported"),
        ]
        usr = [
            _make_candidate("Mega Tree", "user"),
            _make_candidate("Arch Left", "user"),
        ]
        report = match_models(imp, usr)
        assert report.match_rule_distribution.get("exact_name") == 2
