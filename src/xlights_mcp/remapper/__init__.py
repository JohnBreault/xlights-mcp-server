"""Sequence model remapping for xLights.

Import an existing .xsq sequence or .zip package created for a different
xLights show layout and intelligently remap it to the user's own model layout.

The remapper implements a multi-priority matching algorithm:
    1. Manual overrides (user-specified mappings)
    2. Exact name match (case-insensitive, whitespace-trimmed)
    3. Similar word match (shared significant name tokens)
    4. Model type match (same display_as + pixel count compatibility)
    5. Similar prop match (shared prop-type word + pixel compatibility)
    6. Pixel count fallback (closest compatible pixel count)

Public API:
    import_package              — Handle .xsq / .zip input, extract assets
    match_models                — Multi-priority model matching algorithm
    generate_remapped_sequence  — Write a remapped .xsq file

Modules:
    importer        — Zip/xsq input handling, asset extraction, metadata parsing
    matcher         — Multi-priority model matching algorithm
    generator       — Remapped .xsq file generation via raw XML manipulation
    path_rewriter   — Effect parameter path rewriting (FILEPICKERCTRL paths)
    models          — Pydantic data models for the remapping pipeline
"""

from __future__ import annotations

__all__ = [
    # Public API functions
    "import_package",
    "match_models",
    "generate_remapped_sequence",
    # Data models
    "MatchRule",
    "MatchCandidate",
    "ModelMapping",
    "UnmatchedModel",
    "MappingReport",
    "ImportedSequenceData",
    "ImportedModelMeta",
    "ExtractedAsset",
    "AssetStatus",
    "RemapRequest",
    "RemapResult",
]

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
from xlights_mcp.remapper.importer import import_package
from xlights_mcp.remapper.matcher import match_models
from xlights_mcp.remapper.generator import generate_remapped_sequence
