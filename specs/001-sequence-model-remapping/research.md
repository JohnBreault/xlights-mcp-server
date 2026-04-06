# Research: Sequence Model Remapping

**Feature Branch**: `001-sequence-model-remapping`
**Date**: 2025-07-18

## R-001: XML Remapping Strategy — Raw Tree vs. Rebuild

**Decision**: Use raw lxml XML tree manipulation (parse → rename → serialize), NOT the existing `xsq_writer.py` rebuild approach.

**Rationale**:
- The existing `xsq_writer.py` is a **build-from-scratch** writer. It constructs a new `.xsq` from `SequenceSpec` Pydantic models, emitting only the subset it knows about (`head`, `ColorPalettes`, `EffectDB`, `DisplayElements`, `ElementEffects`, `TimingTags`). Any XML structure not captured in the Pydantic models would be silently dropped.
- The existing `xsq_reader.py` is **summary-only** — it reads effect counts, basic metadata, and truncated settings (EffectDB entries are capped at 200 chars). It does NOT preserve raw effect settings strings, `ref` attributes, palette indices, or layer-level detail with full fidelity. Timing track labels use `label` attr but the reader checks `name`.
- The `xsq_writer.py` does NOT write model groups into `ElementEffects` — it only iterates `show_config.models`. The remapper must handle groups as first-class entities (FR-020a), which means working directly with the XML tree where group elements already exist.
- Raw XML manipulation preserves **everything**: unknown attributes, vendor extensions, exact formatting, EffectDB entries, palette text, layer structure, and model groups. The only modification needed is renaming `Element/@name` attributes in `DisplayElements` and `ElementEffects`, plus rewriting media paths in EffectDB and effect settings.

**Alternatives Considered**:
1. **Full reader→writer round-trip**: Rejected because the reader loses fidelity (truncated settings, missing timing labels, no group support) and the writer drops unmodeled XML.
2. **Hybrid: lxml parse + selective writer for modified sections**: Over-engineered — if the XML tree is already parsed, renaming in-place is simpler and safer than rebuilding sections.

## R-002: Zip Package Extraction Strategy

**Decision**: Use `zipfile.ZipFile.infolist()` with per-entry validation and manual extraction. Never use `extractall()`.

**Rationale**:
- Community zip packages may contain macOS metadata (`__MACOSX/`, `._*` files, `.DS_Store`) that must be silently skipped (FR-001d).
- Zip-slip attacks are possible if archive paths contain `../` traversal — each entry must be validated against the target directory.
- The spec requires never overwriting existing user files (FR-001a, Constitution Principle III).
- Only specific file types should be extracted: `.xsq`, `xlights_rgbeffects.xml`, `.mp3`, `.mp4`, `.png`, `.fs`, `.obj`.

**Implementation Details**:
- Filter entries: skip `__MACOSX/`, `._*` prefix, `.DS_Store`, directories
- Zip-slip prevention: `PurePosixPath` normalize → join to show folder → `resolve()` → reject if outside target
- Zip-bomb guards: max member count (1000), max total uncompressed size (2GB), max single file (500MB)
- Allowlist of extractable extensions: `.xsq`, `.xml`, `.mp3`, `.mp4`, `.png`, `.fs`, `.obj`
- Preserve relative subfolder structure (`Videos/`, `Shaders/`, `3D/`, `ImportedMedia/`)
- Skip extraction if destination file already exists; log as "already present"
- Show folder path from `ServerConfig.active_show_path` property

**Alternatives Considered**:
1. **`extractall()` with post-cleanup**: Rejected — extracts junk files before cleanup, and doesn't prevent zip-slip natively.
2. **`shutil.unpack_archive()`**: Rejected — no fine-grained control over filtering or overwrite prevention.

## R-003: Model Matching Algorithm Design

**Decision**: Greedy priority-pipeline matching with pixel-count tie-breaking. Not Hungarian/bipartite optimization.

**Rationale**:
- The spec explicitly defines a strict priority order (FR-003): exact name → similar word → model type → similar prop → pixel count fallback. A globally optimal algorithm (Hungarian) would blur these priority boundaries — a "better" pixel-count match at priority 5 should never displace a word match at priority 2.
- FR-008 requires tie-breaking by closest pixel count within the same priority level, confirming a greedy-with-tiebreak approach.
- The model counts (typically 10–500 models per side) make O(n²) per-priority-pass entirely feasible and far simpler than graph-based optimization.

**Algorithm Outline**:
```
1. Apply manual overrides first (FR-012) — remove from both pools
2. For each priority level [exact, word, type, prop, pixel]:
   a. Build candidate pairs from unmatched pools
   b. Sort candidates by pixel-count closeness (tie-break)
   c. Greedily assign best pairs, removing from pools
3. Remaining unmatched → report
```

**Data Structures**:
- `unmatched_imported: set[str]` — imported model names not yet matched
- `unmatched_user: set[str]` — user model names not yet matched
- `matches: list[ModelMapping]` — matched pairs with rule annotation
- Index lookups: token→models dict for word matching, display_as→models dict for type matching

**Alternatives Considered**:
1. **Hungarian algorithm**: Rejected — O(n³), harder to implement, and violates the spec's explicit priority ordering.
2. **Scoring-based single-pass**: Rejected — conflates priority levels into a single score, making it hard to guarantee priority order per FR-003.

## R-004: Word Tokenization and Filler Words

**Decision**: Regex split on non-alphanumeric characters, lowercase normalization, configurable filler word exclusion list.

**Rationale**:
- xLights model names use mixed conventions: spaces ("Mega Tree"), hyphens ("Candy-Cane"), numbers ("Arch 1"), and directional suffixes ("Snowflake Left").
- Splitting on `\W+` (non-word characters) handles all these consistently.
- Filler words are excluded per FR-005 to prevent false matches on positional terms.

**Filler Word List**:
```python
FILLER_WORDS = frozenset({
    # Positional/directional
    "left", "right", "top", "bottom", "center", "centre", "middle",
    "upper", "lower", "inner", "outer", "front", "back",
    # Articles/prepositions
    "a", "an", "the", "of", "and", "for", "with", "in", "on",
    # Ordinals/numbers (single digits)
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
})
```

**Alternatives Considered**:
1. **Fuzzy string matching (Levenshtein/Jaro-Winkler)**: Rejected for word matching — the spec requires shared significant words (FR-005), not approximate string distance. Adds complexity and external dependencies.
2. **NLP-based tokenization (spaCy, nltk)**: Over-engineered for model names which are short multi-word labels.

## R-005: Effect Parameter Path Rewriting

**Decision**: Regex-based path rewriting targeting `FILEPICKERCTRL` patterns in EffectDB settings strings.

**Rationale**:
- Effect settings in EffectDB are stored as comma-separated `key=value` strings (confirmed by `xsq_reader.py` and `xsq_writer.py`).
- Path-bearing keys follow the pattern `*FILEPICKERCTRL*` (e.g., `E_FILEPICKERCTRL_Video_Filename`, `E_0FILEPICKERCTRL_IFS`).
- The original creator's absolute paths (e.g., `/Users/xtreme/Desktop/Christmas 2023/Videos/foo.mp4`) must be rewritten to the user's show folder.
- Strategy: extract the filename from the original path, check if it exists (either in the show folder or as an extracted asset), and rewrite to the user's show folder path. If not found, keep the rewritten path but log a warning (FR-019b).

**Implementation**:
- Parse EffectDB entries as comma-separated key=value pairs
- Find keys matching `*FILEPICKERCTRL*` pattern
- Extract basename from value, resolve to user show folder
- Rebuild the settings string with rewritten paths
- Also rewrite `mediaFile` in `<head>` section (FR-019)

**Alternatives Considered**:
1. **AST-based settings parser**: Over-engineered — the format is simple comma-separated key=value pairs.
2. **Path mapping table (old→new)**: Could work but is less robust than basename-based resolution since original paths vary across creators.

## R-006: Incremented File Naming

**Decision**: Glob-based suffix detection with `(remapped N)` naming convention.

**Rationale**:
- FR-014 requires `SongName (remapped 1).xsq`, incrementing for subsequent runs.
- Use `glob` to find existing `*remapped*` files and extract the highest N, then increment.
- Consistent with existing Constitution Principle III patterns (`(generated N)` in the sequencer).

**Implementation**:
```python
import re
from pathlib import Path

def next_remapped_path(base_name: str, show_folder: Path) -> Path:
    pattern = re.compile(rf"^{re.escape(base_name)} \(remapped (\d+)\)\.xsq$")
    max_n = 0
    for f in show_folder.glob(f"{base_name} (remapped *)*.xsq"):
        m = pattern.match(f.name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return show_folder / f"{base_name} (remapped {max_n + 1}).xsq"
```

## R-007: Singing Model Handling

**Decision**: Separate singing models into a dedicated matching sub-pool before general matching begins.

**Rationale**:
- FR-003b requires singing models (those with `face_definitions`) to only match other singing models.
- This is best implemented by partitioning both imported and user models into singing/non-singing pools before the priority pipeline runs.
- If no singing target exists, the imported singing model is left unmatched (effects skipped).
- The existing `LightModel` already has `face_definitions: list` field — a non-empty list indicates a singing model.

**Implementation**:
- Before matching: split both pools into `singing_imported`, `non_singing_imported`, `singing_user`, `non_singing_user`
- Run the full priority pipeline on singing pools first
- Run the full priority pipeline on non-singing pools second
- Unmatched singing models never fall through to the non-singing pool

## R-008: Model Group Handling

**Decision**: Treat model groups as first-class matching entities alongside individual models.

**Rationale**:
- FR-020/FR-020a require groups to participate in matching with the same priority rules.
- Community sequences may have 153 groups vs 10 individual models — groups dominate.
- In the `.xsq` XML, groups appear as `Element[@type="model"]` just like individual models (there's no separate `type="group"` attribute). The distinction comes from whether the name matches a `modelGroup` entry in `xlights_rgbeffects.xml`.
- For matching purposes, groups use the group name (same tokenization, same word matching). Pixel count and `display_as` are not directly available for groups (they aggregate their members). Group-to-group matching should prefer name-based rules (exact, word, prop word) and skip pixel-count-dependent rules.
- Group-to-group matching is preferred over group-to-individual (FR-020a SHOULD).

**Implementation**:
- Build a unified matching pool: `MatchCandidate` with fields `name`, `pixel_count` (0 for groups), `display_as` (empty for groups), `is_group`, `is_singing`, `face_definitions`
- For groups, aggregate pixel count from members if available (sum of member pixel counts), or leave at 0
- Run matching with groups and individuals in the same pool, but with group-to-group preference at tie-breaking
