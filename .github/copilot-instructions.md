# xlights-mcp-server Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-06

## Active Technologies

- Python 3.11+ with type annotations, FastMCP (MCP protocol), Pydantic 2.x (data models), lxml 5.x (XML parsing/writing) (001-sequence-model-remapping)

## Project Structure

```text
src/
tests/
```

## Commands

Run from the repository root:

```bash
uv venv
uv pip install -e ".[dev]"
uv run pytest
uv run pytest tests/test_remap_integration.py
uv run pytest tests/test_remap_integration.py::TestBasicXsqPipeline::test_end_to_end_xsq
uv run ruff check .
uv build
uv run xlights-mcp-server
```

`pip install -e ".[dev]"` is the alternative documented in CONTRIBUTING.md;
with that environment activated, use `pytest` and `ruff check .` directly.
Packaging uses Hatchling. Ruff targets Python 3.11 with a 100-character line length;
pytest discovers `tests/` and uses `asyncio_mode = "auto"`.
Audio handling requires ffmpeg. Optional extras are `separation` (Demucs),
`beats` (madmom), `lyrics` (Whisper), and `all`.

## Code Style

Python 3.11+ with type annotations.

## Recent Changes

- 001-sequence-model-remapping: Added Python 3.11+ with type annotations, FastMCP (MCP protocol), Pydantic 2.x (data models), lxml 5.x (XML parsing/writing)

<!-- MANUAL ADDITIONS START -->

## Architecture

- `server.py` owns the FastMCP instance and `@mcp.tool()` API. The console entry
  point calls `main()` and runs stdio transport. Tools import feature modules
  lazily; keep diagnostics in logging rather than stdout, which carries MCP.
- Generation flows from `xlights/show.py` (show XML -> `ShowConfig`) and
  `audio/analyzer.py` (beats, spectrum, sections, optional stems -> `SongAnalysis`)
  into `sequencer/engine.py`. The engine creates `SequenceSpec`/`EffectPlacement`
  models, then `xlights/xsq_writer.py` serializes a new `.xsq` using ElementTree.
  `auto` generates output; `guided` currently returns a section preview;
  `template` currently returns a not-implemented error.
- Remapping is a separate pipeline: `remapper/importer.py` reads `.xsq`/`.zip`
  into metadata plus a raw lxml tree; `matcher.py` produces a `MappingReport`;
  `generator.py` deep-copies and renames the tree, removes unmatched models, and
  invokes `path_rewriter.py`. Do not rebuild imports through `SequenceSpec`:
  preserving timing tracks, effect settings, palettes, and unknown XML is central
  to remapping.
- On Windows, `main()` swaps FastMCP's stdio transport for `win_stdio.run()`
  when stdin is a pipe: a pending blocking stdin read deadlocks native-extension
  imports (numpy/librosa) on the first tool call. Keep heavy imports lazy and
  route startup changes through both transport paths.
- FPP integration uses httpx against the player's REST API. Uploads accept
  rendered `.fseq` files and optional audio, not the generated `.xsq` XML.
  Generation itself does not require a running xLights GUI or FPP connection.

## Repository Conventions

- Pydantic models carry data across module boundaries. MCP tools return dicts,
  serializing models with `model_dump()`. Return explicit `error` responses at
  the tool boundary; lower-level import/parsing functions may raise exceptions.
  `RemapResult` is the remapping tool's success/error envelope.
- `config.py` persists settings in `~/.xlights-mcp/config.json`; `server.py`
  lazily caches the loaded `ServerConfig`. Detected folders remain suggestions
  until confirmed via `add_show_folder`. Generation/remapping use `_resolve_show`:
  when multiple shows exist, return the selection response and require an
  explicit `show_name`, rather than silently using `active_show`.
- Treat `xlights_rgbeffects.xml` and `xlights_networks.xml` as read-only. Derive
  capabilities from `display_as`, face definitions, and configured groups, not
  hardcoded user model names or controller defaults. Generation prefers
  configured groups and falls back to common-prefix grouping.
- Never overwrite user sequences: generated output uses `(generated N)` and
  remapped output uses `(remapped N)`. Preserve ZIP extraction's no-overwrite,
  path-traversal, extension, and size guards. Report missing imported assets
  through the mapping report rather than silently discarding references.
- Automatic matching is one-to-one, consuming candidates in priority order:
  manual overrides, exact name, shared words, model type, similar prop, pixel
  count. Automatic passes partition singing and non-singing candidates;
  overrides run first. Unknown/zero pixel counts are not pixel-compatible.
- Audio-analysis times are in seconds; sequence placements are in integer
  milliseconds, with a default 25 ms frame interval. Keep generated effects
  tied to musical events. Layers have distinct roles: L0 background bed,
  L1 rhythmic motion, L2 accents. Singing models are excluded from regular
  effects and use dedicated Faces/lyric timing tracks.
- Effect settings are string-valued xLights parameter dictionaries serialized
  as comma-separated `key=value` entries. The writer deduplicates `EffectDB`
  settings and references palettes by index; retain valid xLights parameter
  names and ranges when extending effects.
- Optional Demucs/madmom/Whisper paths must degrade to core librosa analysis or
  skip singing features, with logged diagnostics. Stem separation reuses cached
  WAVs; its current default location is beside the audio under
  `stems/<song>/`, so do not assume every cache uses `AudioConfig.cache_dir`.
- `mcp` is pinned `<2`. `pyproject.toml` declares static `[tool.uv.dependency-metadata]`
  for madmom so default uv resolution never builds that legacy optional package;
  keep it in sync if the `beats` extra changes.
- Remapping tests use small XML fixtures in `tests/fixtures/remapping`,
  `tmp_path` output folders, and ZIPs constructed inside tests, checking XML
  preservation, mapping rules, asset rewriting, and incremented filenames.
  Engine/audio tests (`test_engine_accents.py`, `test_stem_onsets.py`) use
  synthetic `SongAnalysis` objects or generated WAVs written to `tmp_path`. No test needs live show folders, audio
  models, or hardware.

## Spec-Driven Guidance

`.specify/memory/constitution.md` governs feature work, including non-destructive
output, model-agnostic behavior, musical fidelity, and optional-feature fallbacks.
Feature specifications and tool contracts live under `specs/`; consult the
relevant feature before changing its behavior. This file's generated sections
are managed by Spec Kit; keep hand-maintained guidance between the
`MANUAL ADDITIONS` markers when updating agent context.

<!-- MANUAL ADDITIONS END -->
