"""Pydantic data models for the sequence model remapping pipeline.

These models define the data contracts between remapper modules:
importer → matcher → generator → server tool.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MatchRule(str, Enum):
    """Which algorithm rule produced a model mapping."""

    MANUAL_OVERRIDE = "manual_override"
    EXACT_NAME = "exact_name"
    SIMILAR_WORD = "similar_word"
    MODEL_TYPE = "model_type"
    SIMILAR_PROP = "similar_prop"
    PIXEL_COUNT_FALLBACK = "pixel_count_fallback"


class AssetStatus(str, Enum):
    """Extraction outcome for a zip-packaged asset."""

    EXTRACTED = "extracted"
    ALREADY_EXISTS = "already_exists"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Matching entities
# ---------------------------------------------------------------------------

# Filler words excluded from name tokenisation (positional, articles, digits)
FILLER_WORDS: frozenset[str] = frozenset(
    {
        # Positional / directional
        "left",
        "right",
        "top",
        "bottom",
        "center",
        "centre",
        "middle",
        "upper",
        "lower",
        "inner",
        "outer",
        "front",
        "back",
        # Articles / prepositions
        "a",
        "an",
        "the",
        "of",
        "and",
        "for",
        "with",
        "in",
        "on",
        # Single digits
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
    }
)

_TOKEN_RE = re.compile(r"\W+")


def _tokenize_name(name: str) -> list[str]:
    """Split a model name into significant lowercase tokens."""
    raw = _TOKEN_RE.split(name.strip().lower())
    return [t for t in raw if t and t not in FILLER_WORDS]


class MatchCandidate(BaseModel):
    """A model or group eligible for matching (imported or user side)."""

    name: str
    normalized_name: str = ""
    name_tokens: list[str] = Field(default_factory=list)
    pixel_count: int = 0
    display_as: str = ""
    is_group: bool = False
    is_singing: bool = False
    face_definitions: list[str] = Field(default_factory=list)
    source: Literal["imported", "user"]

    @field_validator("name")
    @classmethod
    def _name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name must be non-empty")
        return v

    @field_validator("pixel_count")
    @classmethod
    def _pixel_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("pixel_count must be >= 0")
        return v

    @model_validator(mode="after")
    def _derive_fields(self) -> MatchCandidate:
        if not self.normalized_name:
            self.normalized_name = self.name.strip().lower()
        if not self.name_tokens:
            self.name_tokens = _tokenize_name(self.name)
        # Enforce singing ↔ face_definitions invariant
        if self.face_definitions and not self.is_singing:
            self.is_singing = True
        return self


class ModelMapping(BaseModel):
    """A matched pair: imported model → user model."""

    imported_name: str
    user_name: str
    rule: MatchRule
    confidence: float = 1.0
    pixel_ratio: float | None = None
    shared_tokens: list[str] = Field(default_factory=list)
    notes: str = ""

    @field_validator("imported_name", "user_name")
    @classmethod
    def _names_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name must be non-empty")
        return v

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v

    @field_validator("pixel_ratio")
    @classmethod
    def _pixel_ratio_range(cls, v: float | None) -> float | None:
        if v is not None and not 0.0 <= v <= 1.0:
            raise ValueError("pixel_ratio must be between 0.0 and 1.0")
        return v

    @model_validator(mode="after")
    def _pixel_ratio_required_for_rules(self) -> ModelMapping:
        rules_requiring_pixel_ratio = {
            MatchRule.MODEL_TYPE,
            MatchRule.SIMILAR_PROP,
            MatchRule.PIXEL_COUNT_FALLBACK,
        }
        if self.rule in rules_requiring_pixel_ratio and self.pixel_ratio is None:
            raise ValueError(
                f"pixel_ratio is required for rule {self.rule.value}"
            )
        return self


class UnmatchedModel(BaseModel):
    """A model that could not be matched."""

    name: str
    source: Literal["imported", "user"]
    reason: str = ""
    pixel_count: int = 0
    display_as: str = ""
    is_singing: bool = False
    is_group: bool = False


# ---------------------------------------------------------------------------
# Asset extraction
# ---------------------------------------------------------------------------


class ExtractedAsset(BaseModel):
    """A file extracted from a zip package."""

    archive_path: str
    destination_path: str
    status: AssetStatus
    file_type: str
    size_bytes: int = 0


# ---------------------------------------------------------------------------
# Import metadata
# ---------------------------------------------------------------------------


class ImportedModelMeta(BaseModel):
    """Model metadata parsed from an imported xlights_rgbeffects.xml."""

    name: str
    display_as: str = ""
    pixel_count: int = 0
    face_definitions: list[str] = Field(default_factory=list)
    is_group: bool = False
    group_members: list[str] = Field(default_factory=list)


class ImportedSequenceData(BaseModel):
    """Parsed data from an imported .xsq file.

    The actual lxml tree is NOT stored here — it is passed alongside this
    model as a separate argument because lxml elements are not
    Pydantic-serialisable.
    """

    file_name: str
    song_title: str = ""
    artist: str = ""
    media_file: str = ""
    duration_ms: int = 0

    model_names: list[str] = Field(default_factory=list)
    timing_track_names: list[str] = Field(default_factory=list)

    total_effects: int = 0
    palette_count: int = 0
    effect_db_count: int = 0


# ---------------------------------------------------------------------------
# Pipeline I/O
# ---------------------------------------------------------------------------


class MappingReport(BaseModel):
    """Full mapping result with statistics and provenance."""

    mappings: list[ModelMapping] = Field(default_factory=list)
    unmatched_imported: list[UnmatchedModel] = Field(default_factory=list)
    unmatched_user: list[UnmatchedModel] = Field(default_factory=list)
    extracted_assets: list[ExtractedAsset] = Field(default_factory=list)
    missing_assets: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    # Statistics
    total_imported_models: int = 0
    total_user_models: int = 0
    total_matched: int = 0
    match_rule_distribution: dict[str, int] = Field(default_factory=dict)

    # Metadata
    imported_source: str = ""
    has_imported_metadata: bool = False
    timing_tracks_preserved: int = 0

    @model_validator(mode="after")
    def _validate_invariants(self) -> MappingReport:
        if self.total_matched != len(self.mappings):
            raise ValueError(
                f"total_matched ({self.total_matched}) must equal "
                f"len(mappings) ({len(self.mappings)})"
            )
        expected_imported = len(self.mappings) + len(self.unmatched_imported)
        if self.total_imported_models != expected_imported:
            raise ValueError(
                f"total_imported_models ({self.total_imported_models}) must equal "
                f"len(mappings) + len(unmatched_imported) ({expected_imported})"
            )
        dist_sum = sum(self.match_rule_distribution.values())
        if dist_sum != self.total_matched:
            raise ValueError(
                f"match_rule_distribution sum ({dist_sum}) must equal "
                f"total_matched ({self.total_matched})"
            )
        return self


class RemapRequest(BaseModel):
    """Input parameters for the remap_sequence MCP tool."""

    import_path: str
    overrides: dict[str, str] = Field(default_factory=dict)
    pixel_threshold: float = 0.70

    @field_validator("import_path")
    @classmethod
    def _valid_extension(cls, v: str) -> str:
        lower = v.lower()
        if not (lower.endswith(".xsq") or lower.endswith(".zip")):
            raise ValueError("import_path must end with .xsq or .zip")
        return v

    @field_validator("pixel_threshold")
    @classmethod
    def _threshold_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("pixel_threshold must be between 0.0 and 1.0")
        return v

    @field_validator("overrides")
    @classmethod
    def _overrides_non_empty_strings(cls, v: dict[str, str]) -> dict[str, str]:
        for key, val in v.items():
            if not key or not key.strip():
                raise ValueError("override keys must be non-empty strings")
            if not val or not val.strip():
                raise ValueError("override values must be non-empty strings")
        return v


class RemapResult(BaseModel):
    """Complete output from the remap_sequence tool."""

    success: bool
    output_path: str = ""
    mapping_report: MappingReport | None = None
    error: str | None = None
