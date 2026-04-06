# Data Model: Sequence Model Remapping

**Feature Branch**: `001-sequence-model-remapping`
**Date**: 2025-07-18

## Entity Relationship Overview

```
ImportedPackage ──contains──► ImportedSequence
                ──contains──► ImportedShowMetadata (optional)
                ──contains──► ExtractedAsset[] (optional)

ImportedSequence ──has──► ImportedModel[]
ImportedShowMetadata ──has──► ImportedModelMeta[]

UserShowConfig ──has──► LightModel[] (existing)
              ──has──► ModelGroup[] (existing)

MatchCandidate (wraps either side's models/groups)

Matcher: MatchCandidate[] × MatchCandidate[] → ModelMapping[]

ModelMapping[] + unmatched → MappingReport

MappingReport + ImportedSequence → RemappedSequence (.xsq)
```

## Entities

### 1. MatchCandidate

Unified representation of a model or group from either side (imported or user) for the matching algorithm.

```python
class MatchCandidate(BaseModel):
    """A model or group eligible for matching."""
    name: str                          # Original name as it appears in XML
    normalized_name: str               # Lowercased, stripped
    name_tokens: list[str]             # Significant words (filler removed)
    pixel_count: int = 0              # 0 if unknown (standalone xsq) or group
    display_as: str = ""               # Model type (e.g., "Arches", "Tree"), empty for groups
    is_group: bool = False             # True if this is a model group
    is_singing: bool = False           # True if face_definitions is non-empty
    face_definitions: list[str] = []   # Face definition names (from faceInfo)
    source: Literal["imported", "user"]  # Which side this candidate comes from
```

**Validation Rules**:
- `name` must be non-empty
- `normalized_name` is derived: `name.strip().lower()`
- `name_tokens` is derived: regex split on `\W+`, lowercased, filler words removed
- `pixel_count` must be >= 0
- `is_singing` must be True iff `face_definitions` is non-empty

### 2. ModelMapping

A single matched pair with provenance.

```python
class MatchRule(str, Enum):
    MANUAL_OVERRIDE = "manual_override"
    EXACT_NAME = "exact_name"
    SIMILAR_WORD = "similar_word"
    MODEL_TYPE = "model_type"
    SIMILAR_PROP = "similar_prop"
    PIXEL_COUNT_FALLBACK = "pixel_count_fallback"

class ModelMapping(BaseModel):
    """A matched pair: imported model → user model."""
    imported_name: str                 # Name from imported sequence
    user_name: str                     # Name from user's show
    rule: MatchRule                    # Which rule produced this match
    confidence: float = 1.0           # 1.0 for exact, lower for fallbacks
    pixel_ratio: float | None = None  # min/max ratio if pixel count was a factor
    shared_tokens: list[str] = []     # Words that matched (for word-based rules)
    notes: str = ""                   # Human-readable explanation
```

**Validation Rules**:
- `imported_name` and `user_name` must be non-empty
- `confidence` must be between 0.0 and 1.0
- `pixel_ratio` when present must be between 0.0 and 1.0
- `pixel_ratio` is required (non-None) for rules: `SIMILAR_PROP`, `PIXEL_COUNT_FALLBACK`, `MODEL_TYPE`

### 3. UnmatchedModel

An imported or user model that found no partner.

```python
class UnmatchedModel(BaseModel):
    """A model that could not be matched."""
    name: str
    source: Literal["imported", "user"]
    reason: str                        # Human-readable reason for non-match
    pixel_count: int = 0
    display_as: str = ""
    is_singing: bool = False
    is_group: bool = False
```

### 4. ExtractedAsset

A media file extracted from a zip package.

```python
class AssetStatus(str, Enum):
    EXTRACTED = "extracted"            # Successfully extracted to show folder
    ALREADY_EXISTS = "already_exists"  # File already present, not overwritten
    SKIPPED = "skipped"                # Skipped (macOS metadata, unsupported type)

class ExtractedAsset(BaseModel):
    """A file extracted from a zip package."""
    archive_path: str                  # Path within the zip archive
    destination_path: str              # Absolute path where extracted (or would be)
    status: AssetStatus
    file_type: str                     # Extension (e.g., ".mp3", ".mp4", ".fs")
    size_bytes: int = 0
```

### 5. MappingReport

The complete output of the matching process.

```python
class MappingReport(BaseModel):
    """Full mapping result with statistics."""
    mappings: list[ModelMapping]
    unmatched_imported: list[UnmatchedModel]
    unmatched_user: list[UnmatchedModel]
    extracted_assets: list[ExtractedAsset] = []
    missing_assets: list[str] = []     # Media paths referenced but not found
    warnings: list[str] = []           # Non-fatal issues encountered

    # Statistics
    total_imported_models: int
    total_user_models: int
    total_matched: int
    match_rule_distribution: dict[str, int]  # rule_name → count

    # Metadata
    imported_source: str               # Original file path
    has_imported_metadata: bool        # Whether xlights_rgbeffects.xml was available
    timing_tracks_preserved: int = 0   # Count of timing tracks carried over
```

**Validation Rules**:
- `total_matched` must equal `len(mappings)`
- `total_imported_models` must equal `len(mappings) + len(unmatched_imported)`
- `match_rule_distribution` values must sum to `total_matched`

### 6. ImportedSequenceData

Raw data extracted from an imported .xsq for remapping (not the reader summary — this carries the full lxml tree).

```python
class ImportedSequenceData(BaseModel):
    """Parsed data from an imported .xsq file."""
    class Config:
        arbitrary_types_allowed = True  # For lxml Element

    file_name: str
    song_title: str = ""
    artist: str = ""
    media_file: str = ""
    duration_ms: int = 0

    # Model names found in ElementEffects (includes groups)
    model_names: list[str]
    timing_track_names: list[str] = []

    # Raw counts for reporting
    total_effects: int = 0
    palette_count: int = 0
    effect_db_count: int = 0

    # The full lxml tree is NOT stored in Pydantic — held separately
    # in the generator as a working variable
```

**Note**: The actual `lxml.etree._Element` tree is passed alongside this model (not embedded in it) because lxml elements are not Pydantic-serializable. The `ImportedSequenceData` captures the metadata needed for matching and reporting.

### 7. ImportedModelMeta

Metadata parsed from `xlights_rgbeffects.xml` inside a zip package.

```python
class ImportedModelMeta(BaseModel):
    """Model metadata from the imported show's xlights_rgbeffects.xml."""
    name: str
    display_as: str = ""
    pixel_count: int = 0
    face_definitions: list[str] = []
    is_group: bool = False
    group_members: list[str] = []      # Only for groups
```

### 8. RemapRequest

The top-level input to the remap pipeline.

```python
class RemapRequest(BaseModel):
    """Input parameters for the remap_sequence MCP tool."""
    import_path: str                   # Path to .xsq or .zip file
    overrides: dict[str, str] = {}     # imported_name → user_name manual overrides
    pixel_threshold: float = 0.70      # Configurable pixel ratio threshold
```

**Validation Rules**:
- `import_path` must point to an existing file with `.xsq` or `.zip` extension
- `pixel_threshold` must be between 0.0 and 1.0
- `overrides` keys and values must be non-empty strings

### 9. RemapResult

The top-level output from the remap pipeline.

```python
class RemapResult(BaseModel):
    """Complete output from the remap_sequence tool."""
    success: bool
    output_path: str                   # Path to the generated .xsq file
    mapping_report: MappingReport
    error: str | None = None           # Only set if success is False
```

## State Transitions

### Matching Pool Lifecycle

```
INITIAL
  ├── Manual overrides applied → models removed from both pools
  │
  ├── Priority 1: Exact Name
  │   └── Matched pairs removed from pools → ModelMapping(rule=EXACT_NAME)
  │
  ├── Priority 2: Similar Word
  │   └── Matched pairs removed → ModelMapping(rule=SIMILAR_WORD)
  │
  ├── Priority 3: Model Type (skipped if no imported metadata)
  │   └── Matched pairs removed → ModelMapping(rule=MODEL_TYPE)
  │
  ├── Priority 4: Similar Prop + Pixel Count
  │   └── Matched pairs removed → ModelMapping(rule=SIMILAR_PROP)
  │
  ├── Priority 5: Pixel Count Fallback
  │   └── Matched pairs removed → ModelMapping(rule=PIXEL_COUNT_FALLBACK)
  │
  └── FINAL: remaining in pools → UnmatchedModel[]
```

### Import Pipeline Lifecycle

```
INPUT (.xsq or .zip path)
  │
  ├── .zip path
  │   ├── Extract & filter entries → ExtractedAsset[]
  │   ├── Parse xlights_rgbeffects.xml → ImportedModelMeta[]
  │   └── Parse .xsq → ImportedSequenceData + lxml tree
  │
  └── .xsq path
      └── Parse .xsq → ImportedSequenceData + lxml tree
  │
  ├── Load user show → ShowConfig (existing)
  │
  ├── Build MatchCandidate pools (imported + user)
  │   ├── Partition: singing vs non-singing
  │   └── Apply matching pipeline (singing first, then non-singing)
  │
  ├── Generate MappingReport
  │
  ├── Clone lxml tree → rename Element/@name attributes per mappings
  │   ├── Rewrite FILEPICKERCTRL paths
  │   └── Update <head> mediaFile
  │
  ├── Write remapped .xsq with incremented suffix
  │
  └── OUTPUT: RemapResult
```

## Relationship to Existing Models

| Existing Model | Location | Relationship to Remapping |
|---|---|---|
| `LightModel` | `xlights/models.py` | User models are wrapped into `MatchCandidate(source="user")` |
| `ModelGroup` | `xlights/models.py` | User groups are wrapped into `MatchCandidate(source="user", is_group=True)` |
| `ShowConfig` | `xlights/models.py` | Provides user's full model/group inventory via `load_show_config()` |
| `SequenceSummary` | `xlights/xsq_reader.py` | NOT used — we need raw XML, not summaries. `ImportedSequenceData` replaces this for remapping. |
| `EffectPlacement` | `xlights/xsq_writer.py` | NOT used — remapping works on raw XML, not structured placements. |

## Pixel Count Threshold Formula

Used in rules: MODEL_TYPE, SIMILAR_PROP, PIXEL_COUNT_FALLBACK

```python
def pixel_counts_compatible(a: int, b: int, threshold: float = 0.70) -> bool:
    """Check if two pixel counts are within the threshold ratio."""
    if a == 0 or b == 0:
        return False  # Unknown pixel count — can't compare
    return min(a, b) / max(a, b) >= threshold
```

Per FR-006: `min(a, b) / max(a, b) >= 0.70`
