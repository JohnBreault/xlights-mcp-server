"""Remapped .xsq file generation via raw XML tree manipulation.

Implements:
- Deep-copy lxml tree with model renaming
- Incremented file naming (remapped N)
- Effect parameter path rewriting integration
"""

from __future__ import annotations

import copy
import logging
import re
from pathlib import Path

from lxml import etree

from xlights_mcp.remapper.models import MappingReport, ModelMapping

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Incremented naming  (T012)
# ---------------------------------------------------------------------------

_REMAPPED_RE = re.compile(r"^(.+?) \(remapped (\d+)\)\.xsq$")


def next_remapped_path(base_name: str, show_folder: Path) -> Path:
    """Determine the next incremented (remapped N).xsq path.

    Scans the show folder for existing remapped files and returns the
    next incremented filename.
    """
    pattern = re.compile(
        rf"^{re.escape(base_name)} \(remapped (\d+)\)\.xsq$"
    )
    max_n = 0
    for f in show_folder.glob(f"{base_name} (remapped *)*.xsq"):
        m = pattern.match(f.name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return show_folder / f"{base_name} (remapped {max_n + 1}).xsq"


# ---------------------------------------------------------------------------
# Tree cloning and renaming  (T011)
# ---------------------------------------------------------------------------


def _clone_and_remap_tree(
    root: etree._Element,
    mappings: list[ModelMapping],
    unmatched_imported_names: set[str],
) -> etree._Element:
    """Deep-copy the lxml tree and remap model names.

    - Rename Element/@name in DisplayElements and ElementEffects per mappings
    - Remove elements for unmatched imported models (effects not placed)
    - Preserve all timing tracks unchanged
    """
    new_root = copy.deepcopy(root)

    # Build rename mapping: imported_name → user_name
    rename_map: dict[str, str] = {m.imported_name: m.user_name for m in mappings}

    # Process DisplayElements
    display_elems = new_root.find("DisplayElements")
    if display_elems is not None:
        to_remove = []
        for elem in display_elems:
            if elem.get("type") != "model":
                continue
            name = elem.get("name", "")
            if name in rename_map:
                elem.set("name", rename_map[name])
            elif name in unmatched_imported_names:
                to_remove.append(elem)
        for elem in to_remove:
            display_elems.remove(elem)

    # Process ElementEffects
    effect_elems = new_root.find("ElementEffects")
    if effect_elems is not None:
        to_remove = []
        for elem in effect_elems:
            if elem.get("type") != "model":
                continue
            name = elem.get("name", "")
            if name in rename_map:
                elem.set("name", rename_map[name])
            elif name in unmatched_imported_names:
                to_remove.append(elem)
        for elem in to_remove:
            effect_elems.remove(elem)

    return new_root


# ---------------------------------------------------------------------------
# Missing asset detection  (T037)
# ---------------------------------------------------------------------------


def _detect_missing_assets(
    root: etree._Element,
    show_folder: Path,
) -> tuple[list[str], list[str]]:
    """Scan cloned tree for FILEPICKERCTRL paths and check existence.

    Returns (missing_paths, warnings).
    """
    missing: list[str] = []
    warnings: list[str] = []

    effect_db = root.find("EffectDB")
    if effect_db is None:
        return missing, warnings

    for effect_elem in effect_db:
        settings = effect_elem.text or ""
        for pair in settings.split(","):
            if "FILEPICKERCTRL" not in pair:
                continue
            parts = pair.split("=", 1)
            if len(parts) != 2:
                continue
            path_val = parts[1].strip()
            if not path_val:
                continue
            # Check if the resolved path exists
            resolved = show_folder / Path(path_val).name
            if not resolved.exists() and path_val not in missing:
                missing.append(path_val)
                warnings.append(
                    f"Effect references missing media: {Path(path_val).name}"
                )

    return missing, warnings


# ---------------------------------------------------------------------------
# Main generation  (T013)
# ---------------------------------------------------------------------------


def generate_remapped_sequence(
    root: etree._Element,
    report: MappingReport,
    show_folder: Path,
    base_name: str | None = None,
) -> tuple[Path, list[str], list[str]]:
    """Generate a remapped .xsq file in the user's show folder.

    Args:
        root: Original lxml tree root from the imported sequence.
        report: MappingReport with matched/unmatched models.
        show_folder: User's show folder path.
        base_name: Base name for the output file (without extension).
            Defaults to the song name from <head>.

    Returns:
        Path to the written .xsq file.
    """
    # Determine base name
    if not base_name:
        head = root.find("head")
        if head is not None:
            base_name = (head.findtext("song") or "").strip()
        if not base_name:
            base_name = "Sequence"

    # Clone and remap
    unmatched_names = {u.name for u in report.unmatched_imported}
    new_root = _clone_and_remap_tree(root, report.mappings, unmatched_names)

    # Path rewriting (import lazy to avoid circular)
    try:
        from xlights_mcp.remapper.path_rewriter import rewrite_effect_paths

        rewrite_effect_paths(new_root, show_folder)
    except ImportError:
        logger.debug("path_rewriter not available, skipping path rewriting")

    # Detect missing assets
    missing_assets, asset_warnings = _detect_missing_assets(new_root, show_folder)
    # Note: caller should update report.missing_assets and report.warnings

    # Determine output path
    output_path = next_remapped_path(base_name, show_folder)

    # Write XML
    xml_bytes = etree.tostring(
        new_root,
        xml_declaration=True,
        encoding="utf-8",
        pretty_print=True,
    )
    output_path.write_bytes(xml_bytes)

    logger.info(f"Wrote remapped sequence: {output_path}")
    return output_path, missing_assets, asset_warnings
