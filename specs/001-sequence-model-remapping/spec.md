# Feature Specification: Sequence Model Remapping

**Feature Branch**: `001-sequence-model-remapping`
**Created**: 2025-07-18
**Status**: Draft
**Input**: User description: "Applying imported sequences to the user's model layout — import an existing .xsq sequence or .zip package created for a different show layout and intelligently remap/apply it to the user's own model layout."

## Clarifications

### Session 2026-04-06

- Q: How should zip asset files (mp3, mp4, png) be handled during import? → A: Auto-copy all dependent assets to the user's show folder.
- Q: Should the imported show's xlights_rgbeffects.xml be parsed for model metadata? → A: Yes, parse it for full model metadata (pixel count, type, face definitions).
- Q: Should singing face models be matched only to other singing models? → A: Yes, singing models only match to singing models; skip if no singing target available.
- Q: Should the tool accept both standalone .xsq files and .zip packages? → A: Yes, accept both; zip gives richer matching data, fall back to xsq-only when no zip.
- Q: Should model type (display_as) be added as a matching signal? → A: Yes, insert type matching between word match and prop match (priority 2.5).

### Session 2026-04-06 (advanced sequence analysis)

Analysis of the "Christmas Time Don't Let The Bells End" community sequence package revealed additional requirements:

- Zip packages may contain shader files (`.fs`), 3D model files (`.obj`), and `ImportedMedia/` subdirectories with nested video assets — all must be extracted preserving subfolder structure (FR-001a updated).
- Effect parameters contain hardcoded absolute paths from the original creator's machine (e.g., `/Users/xtreme/Desktop/Christmas 2023/Videos/...`). These MUST be rewritten to the user's show folder paths (FR-019a added).
- Sequences may be heavily group-based: 153 model groups vs. only 10 individual models. Groups must be first-class matching entities (FR-020a added).
- Timing tracks (Beats, Drums, Background Vocals) are model-independent and must be preserved as-is (FR-020b added).
- Zip files from macOS may contain `__MACOSX/` resource forks and `.DS_Store` files that must be skipped (FR-001d added).
- Missing media assets referenced by effects should warn but not fail the import (FR-019b added).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Import and Auto-Match Models (Priority: P1)

A user downloads a popular community sequence file (.xsq) from the internet. The sequence was built for a different show layout with different model names and configurations. The user wants to apply this sequence to their own show layout with minimal effort. They provide the .xsq file path and the system automatically matches models from the imported sequence to the user's models, generates a mapping report showing what matched and how, and produces a new .xsq file with effects remapped to the user's models.

**Why this priority**: This is the core value proposition — the ability to take any community sequence and make it work on the user's own layout. Without this, the feature has no purpose.

**Independent Test**: Can be fully tested by providing an .xsq file from a different show layout and verifying that a new .xsq file is generated with effects correctly remapped to the user's models. The mapping report confirms which models matched and by which rule.

**Acceptance Scenarios**:

1. **Given** a user has an active show with 12 models loaded, **When** they provide a path to an imported .xsq file containing effects for 10 models, **Then** the system produces a mapping report showing each imported model, the matched user model, the match rule used (exact name, similar word, similar prop, or pixel count fallback), and any unmatched models from either side.
2. **Given** the imported sequence contains a model named "Mega Tree" and the user's show has a model also named "Mega Tree", **When** the remapping runs, **Then** those two models are matched by the exact-name rule and all effects from the imported "Mega Tree" are applied to the user's "Mega Tree".
3. **Given** the mapping report is generated, **When** the user confirms the mapping (or accepts the auto mapping), **Then** a new .xsq file is written to the show folder with an incremented suffix (e.g., `SongName (remapped 1).xsq`) and the original imported file is never modified.

---

### User Story 2 — Similar Word and Prop Matching (Priority: P2)

A user imports a sequence where model names don't exactly match their own, but are semantically similar. For example, the imported sequence has "Snowflake Left" and the user has "Large Snowflake 1". The system uses word-overlap matching and prop-type similarity with pixel count thresholds to find the best available match.

**Why this priority**: Exact name matches alone are rarely sufficient across different show layouts. Word-similarity and prop-type matching dramatically increase the percentage of models that can be automatically mapped, reducing manual intervention.

**Independent Test**: Can be tested by providing an imported sequence where zero model names match exactly but models share common words (e.g., "snowflake", "arch", "tree") and verifying that the system correctly identifies and maps these similar models.

**Acceptance Scenarios**:

1. **Given** the imported sequence has a model "Snowflake Left" (200 pixels) and the user's show has "Large Snowflake 1" (250 pixels), **When** the matching runs, **Then** these models are matched by the similar-word rule because both names contain "snowflake" and the pixel counts are within 70% of each other (200/250 = 80%, which exceeds the 70% threshold).
2. **Given** the imported sequence has "Snowflake Medium" (300 pixels) and the user has "Mini Snowflake" (50 pixels), **When** the matching runs, **Then** these models are NOT matched by the similar-prop rule because the pixel counts differ by more than 70% (50/300 = 16.7%), and the system attempts the next fallback rule instead.
3. **Given** the imported sequence has "Candy Cane 1" and the user's show has "Candy Cane Left", **When** the matching runs, **Then** they are matched by the similar-word rule because both contain "candy" and "cane".

---

### User Story 3 — Fallback Pixel Count Matching (Priority: P3)

After exhausting name-based and prop-type matching, some user models still have no match. The system falls back to matching these remaining unmatched user models with any remaining unused imported models that have a similar pixel count, regardless of name or type.

**Why this priority**: This fallback ensures maximum coverage — even models with completely unrelated names can receive effects if the pixel counts are compatible, which often means the effects will scale acceptably on the target model.

**Independent Test**: Can be tested by providing an imported sequence where no models share any name words with the user's models, and verifying that models are still matched based on pixel count proximity.

**Acceptance Scenarios**:

1. **Given** the user has a model "Front Yard Spiral" (150 pixels) with no name-based match to any imported model, and the imported sequence has an unmatched model "Pillar Wrap" (160 pixels), **When** the fallback matching runs, **Then** "Pillar Wrap" is matched to "Front Yard Spiral" because the pixel counts are within 70% of each other.
2. **Given** a fallback match is made, **When** the mapping report is generated, **Then** the match is clearly labeled as a "pixel count fallback" match so the user understands it was not a name-based match and can override it if desired.
3. **Given** multiple unmatched imported models have similar pixel counts to a user model, **When** the fallback runs, **Then** the system selects the closest pixel count match (smallest absolute difference).

---

### User Story 4 — Mapping Report and Unmatched Model Handling (Priority: P4)

The user wants full transparency into what the remapping did. The system provides a detailed mapping report. Some models from the imported sequence or the user's layout may remain unmatched — the report clearly identifies these and explains why.

**Why this priority**: Transparency and user trust are essential. Without a clear report, users cannot verify correctness or make informed decisions about manual overrides. Handling unmatched models gracefully is part of the "never destructive" and "graceful degradation" constitution principles.

**Independent Test**: Can be tested by importing a sequence where deliberate mismatches exist and verifying the report accurately lists every matched pair, every unmatched imported model (with reason), and every unmatched user model.

**Acceptance Scenarios**:

1. **Given** the import is complete, **When** the mapping report is returned, **Then** it contains: (a) a list of all matched model pairs with the rule that matched them, (b) a list of imported models that could not be matched to any user model, and (c) a list of user models that received no effects from the import.
2. **Given** the imported sequence has 15 models and the user's show has 10 models, **When** the matching completes, **Then** the report shows that at most 10 imported models could be matched and the remaining 5 imported models are listed as unmatched with the reason "no compatible user model available".
3. **Given** a user model has a pixel count of 500 and the only remaining unmatched imported model has 50 pixels, **When** the fallback matching evaluates this pair, **Then** it does NOT match them (50/500 = 10%, below the 70% threshold) and both remain listed as unmatched.

---

### User Story 5 — Manual Override of Mappings (Priority: P5)

After reviewing the mapping report, the user disagrees with some matches and wants to override specific model mappings before the remapped sequence is generated. They can specify explicit model-to-model assignments that take precedence over automatic matching.

**Why this priority**: Automatic matching cannot always get every model right. Giving users the ability to correct individual mappings before generation ensures the final sequence meets their expectations without re-running the entire process.

**Independent Test**: Can be tested by providing explicit mapping overrides and verifying that the overridden pairs are used in the generated sequence instead of the automatic matches.

**Acceptance Scenarios**:

1. **Given** the automatic matching mapped imported "Arch Left" to user's "Arch 1", **When** the user provides an override mapping "Arch Left" → "Arch 3", **Then** the generated sequence places "Arch Left" effects on "Arch 3" instead of "Arch 1", and "Arch 1" becomes available for other matches.
2. **Given** the user provides manual overrides as a dictionary of imported-model-name to user-model-name, **When** the remapping runs, **Then** overrides are applied first before any automatic matching begins, and overridden models are excluded from the automatic matching pool.

---

### Edge Cases

- What happens when the imported .xsq file is corrupt or unparseable? The system returns a clear error message and does not generate any output file.
- What happens when the imported sequence contains zero models with effects? The system returns a report indicating no effects were found to remap.
- What happens when the user's show has zero models? The system returns an error indicating no target models are available for remapping.
- What happens when a model name in the imported sequence contains special characters or Unicode? The system handles name matching using normalized string comparison (case-insensitive, trimmed whitespace).
- What happens when the imported sequence references model groups rather than individual models? Effects on model groups in the imported file are included in the remapping — the system matches group names using the same matching rules.
- What happens when two imported models are equally good matches for the same user model? The system assigns the first match (by matching priority order) and the second imported model continues to the next matching rule.
- What happens when the user runs the remap tool on the same imported sequence a second time? A new output file is generated with the next incremented suffix (e.g., `(remapped 2).xsq`), never overwriting the previous output.
- What happens when the zip contains no `.xsq` file? The system returns a clear error: "No .xsq sequence file found in the zip archive."
- What happens when the zip contains multiple `.xsq` files? The system lists them and asks the user to specify which one to import.
- What happens when a media asset from the zip already exists in the user's show folder? The existing file is preserved (not overwritten); the import logs that the asset was already present.
- What happens when the imported zip has no `xlights_rgbeffects.xml`? The system falls back to xsq-only matching (no imported pixel counts or model types) and notes the limitation in the mapping report.
- What happens when an imported singing model has no matching singing model in the user's show? The imported singing model is listed as unmatched; its face effects are not placed on a non-singing model.
- What happens when effects contain hardcoded absolute paths from the original creator's machine (e.g., `/Users/xtreme/Desktop/...`)? The system rewrites all `FILEPICKERCTRL` paths in effect parameters to point to the corresponding files in the user's show folder.
- What happens when a Video or Shader effect references a file not included in the zip? The system logs a warning listing the missing file and affected models but does not fail the import. The effect is included with the rewritten (but unresolvable) path.
- What happens when the imported sequence has far more model groups (GRP) than individual models (e.g., 153 groups vs. 10 models)? Group matching follows the same priority rules. Groups are first-class matching entities.
- What happens when the zip contains macOS resource fork metadata (`__MACOSX/`, `._*` files, `.DS_Store`)? These are silently skipped during extraction.
- What happens when the imported sequence contains timing tracks (Beats, Drums, etc.)? Timing tracks are preserved as-is in the generated sequence since they are not model-dependent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a file path to either a standalone `.xsq` sequence file or a `.zip` package containing a sequence and associated assets. For zip input, the system MUST locate the `.xsq` file within the archive automatically.
- **FR-001a**: When the input is a `.zip` package, the system MUST extract and copy all dependent media assets (`.mp3`, `.mp4`, `.png`, `.fs` shader files, `.obj` 3D models) into the user's active show folder, preserving the relative subfolder structure (e.g., `Videos/`, `Shaders/`, `3D/`, `ImportedMedia/`).
- **FR-001b**: When the input is a `.zip` package containing `xlights_rgbeffects.xml`, the system MUST parse it to obtain full model metadata (name, display_as, pixel_count, face_definitions) for the imported models.
- **FR-001c**: When the input is a standalone `.xsq` file without accompanying `xlights_rgbeffects.xml`, the system MUST fall back to xsq-only matching (model names from the sequence, no imported pixel counts or type data).
- **FR-001d**: When extracting zip contents, the system MUST skip macOS resource fork files (`__MACOSX/` directory, `._*` files) and `.DS_Store` files.
- **FR-002**: System MUST read the user's active show configuration to obtain the full list of user models with their properties (name, display_as, pixel_count, face_definitions, submodels).
- **FR-003**: System MUST execute model matching in strict priority order: (1) exact name match, (2) similar word match, (3) model type match (`display_as`), (4) similar prop with pixel count threshold, (5) fallback pixel count match.
- **FR-003a**: Model type matching (priority 3) MUST match models that share the same `display_as` value (e.g., both "Arches", both "Tree") and have pixel counts within the 70% threshold. This rule requires imported model metadata from `xlights_rgbeffects.xml`; it is skipped for standalone `.xsq` imports.
- **FR-003b**: Singing face models (models with `face_definitions`) MUST only be matched to other models that also have `face_definitions`. If no singing target is available in the user's show, the imported singing model MUST be listed as unmatched and its effects skipped rather than placed on a non-singing model.
- **FR-004**: Exact name matching MUST be case-insensitive and ignore leading/trailing whitespace.
- **FR-005**: Similar word matching MUST tokenize model names into individual words and match models that share at least one significant word (excluding common filler words such as "left", "right", "1", "2", "top", "bottom").
- **FR-006**: Similar prop matching MUST verify that two models sharing a prop-type word (e.g., "snowflake", "arch", "tree") also have pixel counts within 70% of each other, calculated as `min(a, b) / max(a, b) >= 0.70`.
- **FR-007**: Fallback pixel count matching MUST only consider models that were not matched by any higher-priority rule and MUST use the same 70% pixel count threshold.
- **FR-008**: When multiple candidates exist at the same matching priority level, the system MUST prefer the candidate with the closest pixel count (smallest absolute difference).
- **FR-009**: Each user model MUST be matched to at most one imported model, and each imported model MUST be matched to at most one user model (one-to-one mapping).
- **FR-010**: System MUST generate a mapping report containing: all matched pairs with their match rule, all unmatched imported models, and all unmatched user models.
- **FR-011**: System MUST accept optional manual override mappings (imported model name → user model name) that take precedence over all automatic matching rules.
- **FR-012**: Manual overrides MUST be applied before automatic matching begins, and overridden models MUST be excluded from the automatic matching pool on both sides.
- **FR-013**: System MUST generate a new .xsq file with effects remapped from matched imported models to the corresponding user models, preserving all effect parameters, timing, palettes, and layer structure.
- **FR-014**: The generated .xsq file MUST use an incremented naming convention (e.g., `SongName (remapped 1).xsq`) and MUST NOT overwrite any existing file.
- **FR-015**: The original imported .xsq file MUST NOT be modified in any way.
- **FR-016**: Effects from unmatched imported models MUST be excluded from the generated file (not placed on random models).
- **FR-017**: User models with no matched imported model MUST receive no effects in the generated file (left empty, not filled with placeholder effects).
- **FR-018**: System MUST return a structured result containing the mapping report, the path to the generated .xsq file, and summary statistics (total models matched, match rule distribution, unmatched counts).
- **FR-019**: System MUST handle the case where the imported sequence's media file reference differs from the user's audio file — the generated sequence MUST update the `mediaFile` path in the `<head>` section to point to the copied audio file's location in the user's show folder.
- **FR-019a**: System MUST rewrite hardcoded absolute file paths in effect parameters (Video `E_FILEPICKERCTRL_Video_Filename`, Shader `E_0FILEPICKERCTRL_IFS`, and any other `FILEPICKERCTRL` settings) to point to the corresponding assets in the user's show folder. The original creator's paths (e.g., `/Users/xtreme/Desktop/...`) MUST be replaced with the user's show folder path.
- **FR-019b**: If an effect references a media file that is not present in the zip package and cannot be resolved to a local file, the system MUST log a warning in the mapping report listing the missing asset and the affected effect, but MUST NOT fail the entire import.
- **FR-020**: Name matching at all levels MUST treat model groups the same as individual models — if the imported sequence places effects on a group name, the system attempts to match that group name against the user's model groups.
- **FR-020a**: Imported sequences may contain significantly more model groups than individual models (e.g., 153 groups vs. 10 individual models). The matching system MUST handle model groups as first-class entities in the matching pool, applying the same priority rules. Group-to-group matching SHOULD be preferred over group-to-individual matching.
- **FR-020b**: Timing tracks (e.g., "Beats", "Drums", "Background Vocals") from the imported sequence MUST be preserved in the generated .xsq file without modification, as they are not model-dependent.

### Key Entities

- **Imported Sequence**: The source `.xsq` file (standalone or within a `.zip` package) from a different show layout. Contains model names, effect placements with timing, color palettes, and effect definitions. When provided as a `.zip`, may also include `xlights_rgbeffects.xml` (full model metadata), audio (`.mp3`), and media assets (`.mp4`, `.png`) used by effects.
- **Imported Show Metadata**: The `xlights_rgbeffects.xml` from the source show (available in `.zip` imports). Provides pixel counts, `display_as` model types, and `face_definitions` for imported models, enabling richer matching.
- **User Show Layout**: The user's active show configuration containing all their models with full metadata (name, display_as, pixel_count, face_definitions, submodels, controller assignments).
- **Model Mapping**: A one-to-one pairing between an imported model name and a user model name, annotated with the matching rule that produced it (exact, similar word, model type, similar prop, pixel count fallback, or manual override).
- **Mapping Report**: A structured summary of all mapping decisions — matched pairs, unmatched imported models, unmatched user models, match statistics, and a list of copied assets.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can import a community sequence and generate a remapped version for their own show layout in a single tool invocation (excluding optional override step).
- **SC-002**: For show layouts where at least 50% of model names share common words with the imported sequence, the system automatically matches at least 70% of models without manual overrides.
- **SC-003**: The generated .xsq file opens in xLights without errors, warnings, or missing effect references.
- **SC-004**: The mapping report enables users to understand every matching decision — 100% of matched pairs include the match rule used and 100% of unmatched models include the reason for non-match.
- **SC-005**: No existing files are modified or overwritten during the remapping process — the tool produces only new files with incremented suffixes.
- **SC-006**: The remapping process completes within 30 seconds for sequences containing up to 500 models and 10,000 effect placements.
- **SC-007**: Manual overrides correctly take precedence in 100% of cases — overridden models never appear in automatic matching results.

## Assumptions

- Users have a valid active show loaded with at least one model defined in `xlights_rgbeffects.xml` and `xlights_networks.xml`.
- The imported `.xsq` file follows the standard xLights sequence format (XML structure with head, ColorPalettes, EffectDB, and ElementEffects sections).
- When imported as a `.zip`, the archive follows common xLights community packaging conventions: a root folder containing `xlights_rgbeffects.xml`, a `Sequences/` subfolder with the `.xsq`, and a `_lost/` or root-level folder with media assets.
- When the imported show's `xlights_rgbeffects.xml` is available (zip import), pixel counts and model types are available for both sides of the matching. For standalone `.xsq` imports, only user-side metadata is available and model type matching (priority 3) is skipped.
- The 70% pixel count threshold is a reasonable default for determining visual compatibility between models. This threshold may be adjusted in future iterations based on user feedback.
- Common filler words excluded from word matching (e.g., "left", "right", "1", "2", "top", "bottom", "a", "the") follow standard xLights community naming conventions.
- Model group matching follows the same rules as individual model matching — if a group name matches, all effects placed on that group in the imported sequence are mapped to the matched group in the user's layout.
- Copied media assets (mp3, mp4, png) are placed in the user's show folder preserving the relative path structure from the zip. Existing files with the same name are not overwritten.
- This feature does not perform effect parameter scaling (e.g., adjusting "butterfly" speed or "marquee" count based on differing pixel counts). Effects are transferred with their original parameters. Parameter scaling may be a future enhancement.
