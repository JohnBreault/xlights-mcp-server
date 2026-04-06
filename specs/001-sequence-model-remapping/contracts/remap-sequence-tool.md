# MCP Tool Contract: remap_sequence

**Protocol**: MCP (Model Context Protocol) via FastMCP
**Transport**: stdio (local process)

## Tool Registration

```python
@mcp.tool()
async def remap_sequence(
    import_path: str,
    overrides: dict[str, str] | None = None,
    pixel_threshold: float = 0.70,
) -> dict:
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `import_path` | `str` | Yes | — | Absolute path to a `.xsq` file or `.zip` package containing a sequence from a different show layout. |
| `overrides` | `dict[str, str] \| None` | No | `None` | Manual mapping overrides. Keys are imported model names, values are user model names. Applied before automatic matching. |
| `pixel_threshold` | `float` | No | `0.70` | Pixel count similarity threshold for prop/type/fallback matching. Range: 0.0–1.0. |

## Return Schema

### Success Response

```json
{
  "success": true,
  "output_path": "/path/to/show/SongName (remapped 1).xsq",
  "mapping_report": {
    "mappings": [
      {
        "imported_name": "Mega Tree",
        "user_name": "Mega Tree",
        "rule": "exact_name",
        "confidence": 1.0,
        "pixel_ratio": null,
        "shared_tokens": [],
        "notes": "Exact name match (case-insensitive)"
      },
      {
        "imported_name": "Snowflake Left",
        "user_name": "Large Snowflake 1",
        "rule": "similar_word",
        "confidence": 0.8,
        "pixel_ratio": 0.8,
        "shared_tokens": ["snowflake"],
        "notes": "Shared word 'snowflake', pixel ratio 200/250=0.80"
      }
    ],
    "unmatched_imported": [
      {
        "name": "Custom Prop XYZ",
        "source": "imported",
        "reason": "No compatible user model available (no name overlap, type mismatch, pixel ratio 0.12 below 0.70 threshold)",
        "pixel_count": 50,
        "display_as": "Custom",
        "is_singing": false,
        "is_group": false
      }
    ],
    "unmatched_user": [
      {
        "name": "New Display 2024",
        "source": "user",
        "reason": "No imported model matched this user model",
        "pixel_count": 800,
        "display_as": "Matrix",
        "is_singing": false,
        "is_group": false
      }
    ],
    "extracted_assets": [
      {
        "archive_path": "Videos/intro.mp4",
        "destination_path": "/path/to/show/Videos/intro.mp4",
        "status": "extracted",
        "file_type": ".mp4",
        "size_bytes": 15234567
      }
    ],
    "missing_assets": [
      "/Users/xtreme/Desktop/Christmas 2023/Videos/custom_video.mp4"
    ],
    "warnings": [
      "Effect on 'Mega Tree' layer 2 references missing media: custom_video.mp4"
    ],
    "total_imported_models": 15,
    "total_user_models": 12,
    "total_matched": 10,
    "match_rule_distribution": {
      "exact_name": 4,
      "similar_word": 3,
      "model_type": 1,
      "similar_prop": 1,
      "pixel_count_fallback": 1
    },
    "imported_source": "/downloads/CommunitySequence.zip",
    "has_imported_metadata": true,
    "timing_tracks_preserved": 3
  }
}
```

### Error Responses

```json
{
  "success": false,
  "error": "File not found: /path/to/nonexistent.xsq"
}
```

```json
{
  "success": false,
  "error": "No .xsq sequence file found in the zip archive."
}
```

```json
{
  "success": false,
  "error": "Multiple .xsq files found in zip: ['Song1.xsq', 'Song2.xsq']. Please extract the desired .xsq and provide it directly."
}
```

```json
{
  "success": false,
  "error": "No active show configured. Use switch_show() first."
}
```

```json
{
  "success": false,
  "error": "No models found in user's active show."
}
```

```json
{
  "success": false,
  "error": "Imported sequence contains no models with effects."
}
```

```json
{
  "success": false,
  "error": "Failed to parse imported .xsq file: [lxml error details]"
}
```

## Behavioral Contract

1. **Never Destructive**: The tool MUST NOT modify the imported file, any existing user files, or the user's show configuration XMLs. It writes only ONE new file: the remapped `.xsq` with an incremented suffix.

2. **Idempotent Naming**: Running the tool twice on the same input produces `(remapped 1).xsq` then `(remapped 2).xsq`. Never overwrites.

3. **Override Precedence**: Manual `overrides` are applied before any automatic matching. Overridden models are excluded from the automatic matching pool on both sides.

4. **Singing Model Isolation**: Models with `face_definitions` are matched only against other models with `face_definitions`. No cross-pool matching.

5. **Timing Track Passthrough**: Timing tracks (`Element[@type="timing"]`) are preserved in the output unchanged.

6. **Group Handling**: Model groups participate in matching with the same priority rules as individual models. Groups appear in the `.xsq` as `Element[@type="model"]` — they are matched by name.

7. **Asset Extraction** (zip only): Media assets are extracted to the user's show folder preserving subfolder structure. Existing files are never overwritten. macOS metadata is skipped.

8. **Path Rewriting**: All `FILEPICKERCTRL` paths in effect parameters are rewritten from the original creator's paths to the user's show folder. The `mediaFile` in `<head>` is updated to the copied audio file path.

9. **Graceful Failure**: Missing media triggers warnings in the report but does not abort the import. Parsing errors return structured error dicts, never raise unhandled exceptions.

## Integration Pattern

Following the existing server.py pattern (confirmed from codebase analysis):

```python
@mcp.tool()
async def remap_sequence(
    import_path: str,
    overrides: dict[str, str] | None = None,
    pixel_threshold: float = 0.70,
) -> dict:
    """Import a sequence from a different show layout and remap it to your models.

    Accepts a .xsq file or .zip package from the xLights community. Automatically
    matches imported models to your show's models using name similarity, model type,
    and pixel count. Generates a new .xsq with effects remapped to your layout.

    Args:
        import_path: Path to the .xsq or .zip file to import.
        overrides: Optional dict mapping imported model names to your model names.
            These take precedence over automatic matching.
        pixel_threshold: Similarity threshold for pixel count matching (0.0-1.0).
            Default 0.70 means models must have at least 70% pixel count similarity.

    Returns:
        Dict with mapping report, output path, and summary statistics.
    """
    from pathlib import Path
    from xlights_mcp.config import load_config
    from xlights_mcp.remapper.importer import import_package
    from xlights_mcp.remapper.matcher import match_models
    from xlights_mcp.remapper.generator import generate_remapped_sequence

    # ... validation and orchestration ...
```
