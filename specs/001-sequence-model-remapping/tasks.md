# Tasks: Sequence Model Remapping

**Input**: Design documents from `/specs/001-sequence-model-remapping/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Included — plan.md explicitly defines test files as part of the project structure.

**Organization**: Tasks are grouped by user story (5 stories from spec.md, P1–P5) to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5)
- Exact file paths included in all task descriptions

## Path Conventions

- Source: `src/xlights_mcp/remapper/` (new package)
- Tests: `tests/` (flat structure matching plan.md)
- Fixtures: `tests/fixtures/remapping/`
- Existing (read-only): `src/xlights_mcp/xlights/models.py`, `show.py`, `xsq_reader.py`, `xsq_writer.py`

---

## Phase 1: Setup (Package Initialization)

**Purpose**: Create the new `remapper` package structure and test infrastructure

- [x] T001 Create remapper package directory with `src/xlights_mcp/remapper/__init__.py` exporting public API (import_package, match_models, generate_remapped_sequence)
- [x] T002 [P] Create test fixture directory `tests/fixtures/remapping/` with a minimal valid `.xsq` XML file (head + ColorPalettes + EffectDB + DisplayElements + ElementEffects with 3 models) and a minimal `xlights_rgbeffects.xml` (3 model definitions with display_as and pixel_count)
- [x] T003 [P] Verify `lxml` >= 5.0 is listed in `pyproject.toml` dependencies; add if missing

---

## Phase 2: Foundational (Data Models — Blocks All User Stories)

**Purpose**: Define ALL Pydantic models that establish the data contracts between remapper modules. Every user story depends on these models.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Create all Pydantic data models in `src/xlights_mcp/remapper/models.py`: MatchRule enum (MANUAL_OVERRIDE, EXACT_NAME, SIMILAR_WORD, MODEL_TYPE, SIMILAR_PROP, PIXEL_COUNT_FALLBACK), MatchCandidate, ModelMapping, UnmatchedModel, AssetStatus enum, ExtractedAsset, MappingReport (with validation invariants from data-model.md), ImportedSequenceData (without lxml tree — held separately per research R-001), ImportedModelMeta, RemapRequest (with path/threshold validators), RemapResult
- [x] T005 [P] Create unit tests for all Pydantic models in `tests/test_remapper_models.py`: validate field defaults, validation rules (confidence 0.0–1.0, pixel_ratio constraints per rule, non-empty names), MappingReport invariants (total_matched == len(mappings), total_imported_models == matched + unmatched), MatchCandidate derived fields (normalized_name, name_tokens), RemapRequest validators (file extension, threshold range)

**Checkpoint**: Data contracts established — all module interfaces defined

---

## Phase 3: User Story 1 — Import and Auto-Match Models (Priority: P1) 🎯 MVP

**Goal**: Accept a standalone `.xsq` file, parse imported model names, match them to user models by exact name, generate a remapped `.xsq` with effects applied to the user's layout, and return a basic mapping report.

**Independent Test**: Provide a `.xsq` file with known model names, a user show with some matching names, verify that a new `(remapped 1).xsq` is generated with effects correctly renamed and a report listing matched/unmatched models.

### Implementation for User Story 1

- [x] T006 [P] [US1] Implement `parse_xsq()` in `src/xlights_mcp/remapper/importer.py` — parse a `.xsq` file with lxml.etree.parse, extract model names from `ElementEffects/Element[@type="model"]/@name`, timing track names from `Element[@type="timing"]/@name`, song metadata from `<head>` (mediaFile, song title, duration), raw effect/palette/EffectDB counts; return `(ImportedSequenceData, lxml.etree._Element)` tuple
- [x] T007 [P] [US1] Implement `build_candidates_from_user_show()` in `src/xlights_mcp/remapper/matcher.py` — convert user's `LightModel` list and `ModelGroup` list (from existing `xlights/models.py`) into `MatchCandidate` objects with source="user", populating display_as, pixel_count, is_group, is_singing (from face_definitions), normalized_name
- [x] T008 [P] [US1] Implement `build_candidates_from_import()` in `src/xlights_mcp/remapper/matcher.py` — convert `ImportedSequenceData.model_names` list into `MatchCandidate` objects with source="imported" (xsq-only: no pixel_count, no display_as); accept optional `list[ImportedModelMeta]` to enrich candidates when zip metadata is available
- [x] T009 [US1] Implement `_match_exact_name()` (Priority 1) in `src/xlights_mcp/remapper/matcher.py` — case-insensitive, whitespace-trimmed comparison per FR-004; iterate imported candidates, find exact match in user pool, create `ModelMapping(rule=EXACT_NAME, confidence=1.0)`, remove both from pools
- [x] T010 [US1] Implement `match_models()` orchestrator in `src/xlights_mcp/remapper/matcher.py` — partition candidates into singing/non-singing pools per R-007, run priority pipeline (only exact name for now; later stories add rules) on singing pool first then non-singing pool, collect `ModelMapping` list and `UnmatchedModel` lists, assemble basic `MappingReport` with counts and rule distribution
- [x] T011 [P] [US1] Implement `_clone_and_remap_tree()` in `src/xlights_mcp/remapper/generator.py` — deep-copy lxml tree, iterate `DisplayElements/Element[@type="model"]` and `ElementEffects/Element[@type="model"]` renaming `@name` attributes per ModelMapping list, remove elements for unmatched imported models (effects not placed), preserve all `Element[@type="timing"]` unchanged per FR-020b
- [x] T012 [P] [US1] Implement `next_remapped_path()` in `src/xlights_mcp/remapper/generator.py` — glob-based detection of existing `(remapped N)` files per R-006, return `Path` to next incremented filename in user's show folder
- [x] T013 [US1] Implement `generate_remapped_sequence()` in `src/xlights_mcp/remapper/generator.py` — orchestrate: accept lxml tree + MappingReport + show_folder, call `_clone_and_remap_tree()`, call `next_remapped_path()`, write XML with `lxml.etree.tostring(xml_declaration=True, encoding="utf-8")`, return output path
- [x] T014 [US1] Register `remap_sequence` MCP tool in `src/xlights_mcp/server.py` — follow existing tool pattern (async def, docstring per contract, returns dict), orchestrate: validate import_path exists, load user show config via `load_show_config()`, call `parse_xsq()` from importer, call `match_models()` from matcher, call `generate_remapped_sequence()` from generator, return `RemapResult.model_dump()`
- [x] T015 [P] [US1] Unit tests for xsq parsing in `tests/test_importer.py` — test parse_xsq with fixture .xsq: verify model_names extracted, timing_track_names extracted, media file parsed, effect counts correct; test error on corrupt XML; test error on missing file
- [x] T016 [P] [US1] Unit tests for exact name matching in `tests/test_matcher.py` — test exact case-insensitive match, test whitespace-trimmed match, test no false positives, test singing pool isolation (singing model not matched to non-singing), test group candidates in pool
- [x] T017 [P] [US1] Unit tests for XML generation in `tests/test_generator.py` — test tree cloning preserves original, test model renaming in DisplayElements and ElementEffects, test unmatched model elements removed, test timing tracks preserved, test next_remapped_path increments correctly, test output file is valid XML
- [x] T018 [US1] Integration test for basic xsq→remap pipeline in `tests/test_remap_integration.py` — end-to-end: fixture .xsq + mock user show → remap_sequence tool → verify output .xsq exists with correct name, verify matched models have effects, verify unmatched models excluded, verify report structure

**Checkpoint**: MVP complete — standalone .xsq files can be imported and remapped with exact name matching. Feature is usable for shows where model names match.

---

## Phase 4: User Story 2 — Similar Word and Prop Matching (Priority: P2)

**Goal**: When model names don't match exactly, find matches by shared significant words (Priority 2), by model type with pixel compatibility (Priority 3), and by shared prop words with pixel compatibility (Priority 4). Also support zip package input with full metadata and media asset extraction.

**Independent Test**: Provide a `.zip` package where zero model names match exactly but models share common words (e.g., "snowflake", "arch") and types (e.g., both "Arches"), verify word/type/prop rules produce correct matches with proper confidence and pixel ratios.

### Implementation for User Story 2

- [x] T019 [P] [US2] Implement name tokenization and filler word filtering in `src/xlights_mcp/remapper/matcher.py` — define `FILLER_WORDS` frozenset per R-004, implement `_tokenize_name(name: str) -> list[str]` using `re.split(r'\W+', ...)` with lowercase normalization and filler exclusion, wire into `MatchCandidate.name_tokens` computation during candidate building
- [x] T020 [P] [US2] Implement `pixel_counts_compatible()` helper in `src/xlights_mcp/remapper/matcher.py` — `min(a, b) / max(a, b) >= threshold`, return False if either is 0 (unknown), per data-model.md formula
- [x] T021 [US2] Implement `_match_similar_word()` (Priority 2) in `src/xlights_mcp/remapper/matcher.py` — find imported/user pairs sharing at least one significant token, tie-break by closest pixel count per FR-008, create `ModelMapping(rule=SIMILAR_WORD)` with shared_tokens and confidence based on token overlap ratio
- [x] T022 [US2] Implement zip extraction in `src/xlights_mcp/remapper/importer.py` — `_extract_zip()`: iterate `ZipFile.infolist()`, skip `__MACOSX/`, `._*`, `.DS_Store` per FR-001d, validate zip-slip (resolve against target dir) per R-002, enforce zip-bomb guards (max 1000 entries, 2GB total, 500MB single file), allowlist extensions (.xsq .xml .mp3 .mp4 .png .fs .obj), extract preserving subfolder structure (Videos/ Shaders/ 3D/ ImportedMedia/), skip if destination exists, return `list[ExtractedAsset]`
- [x] T023 [US2] Implement `_parse_imported_metadata()` in `src/xlights_mcp/remapper/importer.py` — parse `xlights_rgbeffects.xml` from zip: extract model definitions (name, display_as, pixel_count from Appearance/parm1×parm2, face_definitions from faceInfo), extract model groups (modelGroup entries with models attribute), return `list[ImportedModelMeta]`
- [x] T024 [US2] Implement `import_package()` dispatcher in `src/xlights_mcp/remapper/importer.py` — detect `.xsq` vs `.zip` extension, for .xsq: call parse_xsq directly, for .zip: extract → find .xsq (error if 0 or >1) → parse_xsq → optionally parse xlights_rgbeffects.xml → return `(ImportedSequenceData, lxml_tree, list[ImportedModelMeta] | None, list[ExtractedAsset])`
- [x] T025 [US2] Implement `_match_model_type()` (Priority 3) in `src/xlights_mcp/remapper/matcher.py` — match by same `display_as` value + `pixel_counts_compatible()`, skip entirely if no imported metadata (standalone .xsq) per FR-003a, tie-break by closest pixel count, create `ModelMapping(rule=MODEL_TYPE)` with pixel_ratio
- [x] T026 [US2] Implement `_match_similar_prop()` (Priority 4) in `src/xlights_mcp/remapper/matcher.py` — match by shared prop-type word (e.g., "snowflake", "arch", "tree") + `pixel_counts_compatible()`, tie-break by closest pixel count, create `ModelMapping(rule=SIMILAR_PROP)` with shared_tokens and pixel_ratio
- [x] T027 [P] [US2] Implement `rewrite_effect_paths()` in `src/xlights_mcp/remapper/path_rewriter.py` — parse EffectDB entries as comma-separated key=value, find keys matching `*FILEPICKERCTRL*` pattern, extract basename from value path, resolve to user's show folder, rebuild settings string; also rewrite `<head>` `mediaFile` attribute to point to copied audio in show folder per FR-019/FR-019a
- [x] T028 [US2] Integrate path_rewriter and zip metadata into pipeline — update `generate_remapped_sequence()` in `src/xlights_mcp/remapper/generator.py` to call `rewrite_effect_paths()` on cloned tree before writing; update `remap_sequence` in `src/xlights_mcp/server.py` to use `import_package()` dispatcher and pass ImportedModelMeta to `build_candidates_from_import()`
- [x] T029 [P] [US2] Unit tests for tokenization, word matching, type matching, and prop matching in `tests/test_matcher.py` — test filler word exclusion, test shared-token detection, test pixel compatibility helper (edge cases: 0 pixels, exact threshold, below threshold), test model type matching with/without metadata, test similar prop with pixel ratio, test tie-breaking by pixel closeness
- [x] T030 [P] [US2] Unit tests for zip extraction and metadata parsing in `tests/test_importer.py` — test macOS metadata skipping, test zip-slip rejection, test allowlist enforcement, test existing file skip, test xlights_rgbeffects.xml parsing (model metadata, group detection, face definitions), test import_package dispatcher for .xsq and .zip paths, test error on zip with no .xsq, test error on zip with multiple .xsq files
- [x] T031 [P] [US2] Unit tests for path rewriting in `tests/test_path_rewriter.py` — test FILEPICKERCTRL key detection and basename extraction, test path rewriting from foreign absolute path to user show folder, test mediaFile head rewriting, test missing media file produces warning not error, test settings string round-trip (non-path keys preserved)

**Checkpoint**: Word, type, and prop matching active. Zip packages fully supported with metadata and media extraction. Path rewriting handles foreign absolute paths. SC-002 target (70% auto-match) achievable for shows with similar naming conventions.

---

## Phase 5: User Story 3 — Fallback Pixel Count Matching (Priority: P3)

**Goal**: After name-based and type-based rules are exhausted, match remaining unmatched models purely by pixel count proximity, maximizing coverage.

**Independent Test**: Provide models with completely unrelated names but compatible pixel counts, verify they are matched by the fallback rule with correct confidence and pixel_ratio.

### Implementation for User Story 3

- [x] T032 [US3] Implement `_match_pixel_count_fallback()` (Priority 5) in `src/xlights_mcp/remapper/matcher.py` — iterate remaining unmatched imported models, for each find the unmatched user model with the closest pixel count that passes `pixel_counts_compatible()`, prefer closest absolute pixel difference per FR-008, create `ModelMapping(rule=PIXEL_COUNT_FALLBACK)` with pixel_ratio
- [x] T033 [US3] Wire fallback rule into `match_models()` orchestrator in `src/xlights_mcp/remapper/matcher.py` — add Priority 5 pass after all name/type/prop passes, ensure it only runs on remaining unmatched pools, respect `pixel_threshold` parameter from RemapRequest
- [x] T034 [P] [US3] Unit tests for pixel count fallback in `tests/test_matcher.py` — test fallback matches by closest pixel count, test threshold enforcement (reject if below), test fallback only applies to truly unmatched models (not stealing from higher-priority matches), test multiple candidates prefer closest count

**Checkpoint**: Maximum automatic coverage achieved. All five priority levels operational. Models with unrelated names but similar pixel counts are now matched.

---

## Phase 6: User Story 4 — Mapping Report and Unmatched Model Handling (Priority: P4)

**Goal**: Provide full transparency into every matching decision. Unmatched models get human-readable explanations. Statistics and warnings enable users to assess quality and identify issues.

**Independent Test**: Import a sequence with deliberate mismatches, verify every matched pair has rule + confidence + notes, every unmatched model has a specific reason, statistics are mathematically consistent, and missing media files are warned.

### Implementation for User Story 4

- [x] T035 [US4] Implement `_compute_report_statistics()` in `src/xlights_mcp/remapper/matcher.py` — calculate match_rule_distribution (count per MatchRule), total_imported_models, total_user_models, total_matched, validate MappingReport invariants (totals consistent with lists), set has_imported_metadata and imported_source
- [x] T036 [US4] Implement unmatched model reasoning in `src/xlights_mcp/remapper/matcher.py` — for each UnmatchedModel, generate a human-readable `reason` string explaining why no match was found (e.g., "No compatible user model: no name overlap, type mismatch, pixel ratio 0.12 below 0.70 threshold" or "Singing model with no singing target in user show")
- [x] T037 [US4] Implement missing asset detection in `src/xlights_mcp/remapper/generator.py` — after path rewriting, scan all FILEPICKERCTRL values in the cloned tree, check if resolved paths exist on disk, collect missing paths into `MappingReport.missing_assets`, generate warning strings for `MappingReport.warnings` listing affected model and effect per FR-019b
- [x] T038 [US4] Enrich `MappingReport` assembly in `src/xlights_mcp/remapper/matcher.py` — set `timing_tracks_preserved` count from ImportedSequenceData, populate `extracted_assets` from importer results, wire `_compute_report_statistics()` and unmatched reasoning into `match_models()` return
- [x] T039 [P] [US4] Unit tests for report completeness in `tests/test_matcher.py` — test statistics invariants hold for various match distributions, test every unmatched model has non-empty reason, test missing_assets populated when media not found, test warnings contain model name and file reference, test timing_tracks_preserved count matches input

**Checkpoint**: SC-004 satisfied — 100% of matched pairs have rule, 100% of unmatched models have reason. Users can make fully informed override decisions.

---

## Phase 7: User Story 5 — Manual Override of Mappings (Priority: P5)

**Goal**: Users can provide explicit model-to-model assignments that bypass automatic matching. Overrides are applied first and overridden models are excluded from all automatic matching pools.

**Independent Test**: Provide overrides dict alongside an import, verify overridden pairs appear with rule=MANUAL_OVERRIDE, overridden models are absent from automatic matching pools, and remaining models still match automatically.

### Implementation for User Story 5

- [x] T040 [US5] Implement `_apply_overrides()` in `src/xlights_mcp/remapper/matcher.py` — validate override keys exist in imported pool and values exist in user pool (warn and skip invalid entries), create `ModelMapping(rule=MANUAL_OVERRIDE, confidence=1.0)` for each valid override, remove overridden models from both imported and user candidate pools before automatic matching begins per FR-012
- [x] T041 [US5] Wire overrides into `match_models()` and MCP tool in `src/xlights_mcp/remapper/matcher.py` — accept `overrides: dict[str, str]` parameter, call `_apply_overrides()` as first step before pool partitioning, pass through from `remap_sequence` server tool via `RemapRequest.overrides`
- [x] T042 [P] [US5] Unit tests for manual override logic in `tests/test_matcher.py` — test overrides applied before automatic matching, test overridden models excluded from pools, test invalid override keys/values produce warnings not errors, test override + automatic matching coexist correctly, test override takes precedence over what would have been an exact name match

**Checkpoint**: SC-007 satisfied — manual overrides correctly take precedence in 100% of cases. Full feature complete.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation, performance, documentation, and cross-story integration testing

- [x] T043 [P] Full integration test in `tests/test_remap_integration.py` — end-to-end: zip package with metadata + manual overrides + all 5 matching rules + path rewriting → verify output .xsq, verify mapping report completeness, verify extracted assets, verify timing tracks preserved, verify incremented naming on second run
- [x] T044 [P] Performance validation — create test with 500 model candidates per side and verify `match_models()` completes within 30 seconds per SC-006
- [x] T045 [P] Run quickstart.md scenarios (basic .xsq import, zip import, overrides, custom threshold) against the implementation and verify expected outcomes
- [x] T046 Update `src/xlights_mcp/remapper/__init__.py` with complete module docstrings, `__all__` exports, and version reference

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3–7)**: All depend on Foundational phase completion
  - US1 (Phase 3): No dependencies on other stories — **MVP**
  - US2 (Phase 4): Builds on US1's matcher framework (adds rules to the same module)
  - US3 (Phase 5): Builds on US2's `pixel_counts_compatible()` helper
  - US4 (Phase 6): Builds on US1–US3's matching output (enriches reports)
  - US5 (Phase 7): Modifies US1's `match_models()` entry point (adds override pre-step)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 2) — standalone, delivers MVP
- **US2 (P2)**: Depends on US1 (extends matcher.py with additional rules, extends importer.py with zip support)
- **US3 (P3)**: Depends on US2 (uses `pixel_counts_compatible()` from US2, adds final rule to pipeline)
- **US4 (P4)**: Depends on US1 (enriches MappingReport that US1 creates); can run in parallel with US2/US3 if report structure is stable
- **US5 (P5)**: Depends on US1 (modifies `match_models()` entry point); can run in parallel with US2/US3/US4

### Within Each User Story

- Models (Phase 2) before any implementation
- Importer before matcher (provides candidates)
- Matcher before generator (provides mappings)
- Generator before server tool integration (provides output)
- Unit tests can be written in parallel with implementation (same story, different files)

### Parallel Opportunities

- **Phase 1**: T002 and T003 can run in parallel
- **Phase 2**: T004 and T005 can run in parallel (models + model tests)
- **Phase 3 (US1)**: T006, T007, T008 can run in parallel (importer, user candidates, import candidates — all different functions); T011 and T012 in parallel (tree cloning, naming utility); T015, T016, T017 in parallel (test files)
- **Phase 4 (US2)**: T019 and T020 in parallel (tokenization, pixel helper); T027 in parallel with T022/T023 (path rewriter vs zip extraction); T029, T030, T031 in parallel (test files)
- **Phase 5 (US3)**: T034 in parallel with T032 (test + implementation on different files)
- **Phase 8**: T043, T044, T045 all run in parallel (independent validation tasks)

---

## Parallel Example: User Story 1

```
# Launch parallel implementation tasks (after Phase 2 complete):
Task T006: "Implement parse_xsq() in src/xlights_mcp/remapper/importer.py"
Task T007: "Implement build_candidates_from_user_show() in src/xlights_mcp/remapper/matcher.py"
Task T008: "Implement build_candidates_from_import() in src/xlights_mcp/remapper/matcher.py"

# After T006–T008 complete, launch parallel generator tasks:
Task T011: "Implement _clone_and_remap_tree() in src/xlights_mcp/remapper/generator.py"
Task T012: "Implement next_remapped_path() in src/xlights_mcp/remapper/generator.py"

# Launch all US1 tests in parallel:
Task T015: "Unit tests for xsq parsing in tests/test_importer.py"
Task T016: "Unit tests for exact name matching in tests/test_matcher.py"
Task T017: "Unit tests for XML generation in tests/test_generator.py"
```

## Parallel Example: User Story 2

```
# Launch parallel foundational tasks for US2:
Task T019: "Tokenization and filler words in matcher.py"
Task T020: "pixel_counts_compatible() helper in matcher.py"
Task T027: "Path rewriter in path_rewriter.py"

# Launch all US2 tests in parallel:
Task T029: "Matching rule tests in tests/test_matcher.py"
Task T030: "Zip extraction tests in tests/test_importer.py"
Task T031: "Path rewriter tests in tests/test_path_rewriter.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational models (T004–T005)
3. Complete Phase 3: User Story 1 (T006–T018)
4. **STOP and VALIDATE**: Test with a real community `.xsq` file against a show layout
5. Delivers: standalone .xsq import → exact name matching → remapped .xsq output

### Incremental Delivery

1. Setup + Foundational → Data contracts established
2. **US1** → Exact name matching MVP → Usable for shows with matching names
3. **US2** → Word/type/prop matching + zip support → Dramatically higher match rate
4. **US3** → Pixel fallback → Maximum automatic coverage
5. **US4** → Rich reporting → Full transparency for users
6. **US5** → Manual overrides → Complete user control
7. Polish → End-to-end validation, performance, documentation

### Key Technical Notes

- **Raw XML manipulation** (not rebuild) per R-001 — preserves ALL effect parameters, layer structure, unknown XML attributes
- **Greedy priority pipeline** per R-003 — strict priority order, no global optimization
- **Singing model isolation** per R-007 — separate pools, no cross-contamination
- **Groups as first-class** per R-008 — same matching rules as individual models
- **Never destructive** per Constitution III — incremented naming, no overwrites, no modifications to existing files

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story is independently testable at its checkpoint
- Commit after each task or logical group
- The `remapper/` package is fully isolated — existing modules (`xlights/`, `sequencer/`) are untouched
- All 5 constitution principles verified in plan.md (pre-design and post-design gates both PASS)
