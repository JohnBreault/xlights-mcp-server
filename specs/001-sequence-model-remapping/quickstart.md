# Quickstart: Sequence Model Remapping

**Feature Branch**: `001-sequence-model-remapping`
**Date**: 2025-07-18

## What This Feature Does

Imports an xLights sequence (`.xsq` or `.zip`) built for a different show layout and remaps it to your own models. The system automatically matches models by name, type, and pixel count, then generates a new `.xsq` file with all effects applied to your layout.

## Prerequisites

- An active xLights show configured with at least one model
- An imported `.xsq` file or `.zip` package from the xLights community
- The MCP server running with the show folder set

## MCP Tool Usage

### Basic Import (standalone .xsq)

```
remap_sequence(import_path="/downloads/CommunitySequence.xsq")
```

The system:
1. Parses the imported sequence to find model names
2. Reads your active show's models from `xlights_rgbeffects.xml`
3. Matches imported models → your models (exact name, word overlap, type, pixel count)
4. Generates `/your/show/CommunitySequence (remapped 1).xsq`
5. Returns a mapping report showing every decision

### Rich Import (zip package)

```
remap_sequence(import_path="/downloads/CommunityPackage.zip")
```

Zip packages provide richer matching because they include `xlights_rgbeffects.xml` with pixel counts and model types. The system also extracts media assets (mp3, mp4, shader files) to your show folder.

### With Manual Overrides

```
remap_sequence(
    import_path="/downloads/CommunitySequence.xsq",
    overrides={
        "Their Mega Tree": "My Big Tree",
        "Arch Left": "Arch 3"
    }
)
```

Overrides are applied first — the specified models are matched exactly as you declare, and removed from the automatic matching pool.

### Custom Pixel Threshold

```
remap_sequence(
    import_path="/downloads/CommunitySequence.xsq",
    pixel_threshold=0.50
)
```

Lower the threshold (default 0.70) to allow more aggressive pixel-count matching. Higher values require more similar pixel counts.

## Matching Priority Order

1. **Exact Name** — case-insensitive, whitespace-trimmed
2. **Similar Word** — shared significant words (e.g., both contain "snowflake")
3. **Model Type** — same `display_as` value + pixel count within threshold (zip only)
4. **Similar Prop** — shared prop word + pixel count within threshold
5. **Pixel Count Fallback** — any remaining models with compatible pixel counts

## Understanding the Mapping Report

The report tells you:
- **Matched pairs**: each with the rule that matched them and pixel ratio
- **Unmatched imported models**: effects from these are skipped (not randomly placed)
- **Unmatched user models**: these get no effects (left empty)
- **Extracted assets**: media files copied from zip to your show folder
- **Warnings**: missing media files or other non-fatal issues

## Architecture Overview

```
remap_sequence (MCP tool in server.py)
    │
    ├── importer.py      — handles .xsq/.zip input, asset extraction
    ├── matcher.py       — multi-priority model matching algorithm
    ├── generator.py     — raw XML remapping, writes new .xsq
    └── path_rewriter.py — rewrites hardcoded file paths in effects
```

All new code lives in `src/xlights_mcp/remapper/`. Existing modules (`xlights/show.py`, `xlights/models.py`) are used read-only for loading user show configuration.

## Key Design Decisions

1. **Raw XML manipulation** (not rebuild) — preserves ALL original effect parameters, layer structure, and unknown XML attributes
2. **Greedy priority matching** (not globally optimal) — respects the explicit priority order from the spec
3. **Singing model isolation** — singing models only match singing models, never cross-pool
4. **Groups as first-class** — model groups participate in matching with the same rules as individual models
5. **Never destructive** — new files only, incremented naming, existing files never modified
