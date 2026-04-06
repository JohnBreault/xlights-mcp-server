"""Import .xsq and .zip sequence packages for remapping.

Handles:
- Standalone .xsq parsing (model names, timing tracks, metadata)
- Zip package extraction (assets, metadata XML, security guards)
- Import dispatcher (.xsq vs .zip)
"""

from __future__ import annotations

import logging
import re
import zipfile
from pathlib import Path, PurePosixPath

from lxml import etree

from xlights_mcp.remapper.models import (
    AssetStatus,
    ExtractedAsset,
    ImportedModelMeta,
    ImportedSequenceData,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Zip extraction constants
# ---------------------------------------------------------------------------

_MACOS_PREFIXES = ("__MACOSX/", "._")
_SKIP_NAMES = {".DS_Store"}
_ALLOWED_EXTENSIONS = frozenset({".xsq", ".xml", ".mp3", ".mp4", ".png", ".fs", ".obj"})
_MAX_ZIP_ENTRIES = 1000
_MAX_TOTAL_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
_MAX_SINGLE_FILE = 500 * 1024 * 1024  # 500 MB


# ---------------------------------------------------------------------------
# .xsq parsing  (T006)
# ---------------------------------------------------------------------------


def parse_xsq(xsq_path: Path) -> tuple[ImportedSequenceData, etree._Element]:
    """Parse a .xsq file and return metadata + raw lxml tree.

    Returns:
        Tuple of (ImportedSequenceData, lxml root element).

    Raises:
        FileNotFoundError: If the file does not exist.
        etree.XMLSyntaxError: If the XML is corrupt.
    """
    if not xsq_path.exists():
        raise FileNotFoundError(f"File not found: {xsq_path}")

    tree = etree.parse(str(xsq_path))
    root = tree.getroot()

    # --- head metadata ---
    head = root.find("head")
    song_title = ""
    artist = ""
    media_file = ""
    duration_ms = 0

    if head is not None:
        song_title = (head.findtext("song") or "").strip()
        artist = (head.findtext("artist") or "").strip()
        media_file = (head.findtext("mediaFile") or head.get("mediaFile", "")).strip()
        dur_text = (head.findtext("sequenceDuration") or "").strip()
        if dur_text:
            try:
                duration_ms = int(float(dur_text) * 1000)
            except ValueError:
                pass

    # --- model names from ElementEffects (authoritative for which models have effects) ---
    model_names: list[str] = []
    timing_track_names: list[str] = []

    for elem in root.iter("Element"):
        etype = elem.get("type", "")
        ename = elem.get("name", "")
        if not ename:
            continue
        if etype == "model":
            if ename not in model_names:
                model_names.append(ename)
        elif etype == "timing":
            if ename not in timing_track_names:
                timing_track_names.append(ename)

    # --- counts ---
    total_effects = 0
    for effect_layer in root.iter("EffectLayer"):
        total_effects += len(effect_layer.findall("Effect"))

    palettes_elem = root.find("ColorPalettes")
    palette_count = len(palettes_elem) if palettes_elem is not None else 0

    effect_db = root.find("EffectDB")
    effect_db_count = len(effect_db) if effect_db is not None else 0

    seq_data = ImportedSequenceData(
        file_name=xsq_path.name,
        song_title=song_title,
        artist=artist,
        media_file=media_file,
        duration_ms=duration_ms,
        model_names=model_names,
        timing_track_names=timing_track_names,
        total_effects=total_effects,
        palette_count=palette_count,
        effect_db_count=effect_db_count,
    )

    return seq_data, root


# ---------------------------------------------------------------------------
# Zip extraction  (T022)
# ---------------------------------------------------------------------------


def _is_macos_junk(name: str) -> bool:
    """Return True if the zip entry is macOS metadata junk."""
    basename = PurePosixPath(name).name
    if basename in _SKIP_NAMES:
        return True
    for prefix in _MACOS_PREFIXES:
        if name.startswith(prefix) or basename.startswith(prefix):
            return True
    return False


def _extract_zip(
    zip_path: Path, target_dir: Path
) -> list[ExtractedAsset]:
    """Extract a zip package to the target directory with security guards.

    Implements:
    - macOS junk filtering (__MACOSX/, ._, .DS_Store)
    - Zip-slip prevention (path traversal rejection)
    - Zip-bomb guards (entry count, total size, single file size)
    - Extension allowlist
    - No-overwrite policy
    """
    assets: list[ExtractedAsset] = []
    target_resolved = target_dir.resolve()

    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.infolist()

        # Zip-bomb guard: entry count
        if len(members) > _MAX_ZIP_ENTRIES:
            raise ValueError(
                f"Zip archive contains {len(members)} entries (max {_MAX_ZIP_ENTRIES})"
            )

        # Zip-bomb guard: total size
        total_size = sum(m.file_size for m in members)
        if total_size > _MAX_TOTAL_SIZE:
            raise ValueError(
                f"Zip archive total size {total_size} exceeds limit "
                f"({_MAX_TOTAL_SIZE} bytes)"
            )

        for info in members:
            # Skip directories
            if info.is_dir():
                continue

            # Skip macOS junk
            if _is_macos_junk(info.filename):
                assets.append(
                    ExtractedAsset(
                        archive_path=info.filename,
                        destination_path="",
                        status=AssetStatus.SKIPPED,
                        file_type="",
                        size_bytes=info.file_size,
                    )
                )
                continue

            # Extension allowlist
            ext = PurePosixPath(info.filename).suffix.lower()
            if ext not in _ALLOWED_EXTENSIONS:
                assets.append(
                    ExtractedAsset(
                        archive_path=info.filename,
                        destination_path="",
                        status=AssetStatus.SKIPPED,
                        file_type=ext,
                        size_bytes=info.file_size,
                    )
                )
                continue

            # Single-file size guard
            if info.file_size > _MAX_SINGLE_FILE:
                logger.warning(
                    f"Skipping oversized file: {info.filename} "
                    f"({info.file_size} bytes)"
                )
                assets.append(
                    ExtractedAsset(
                        archive_path=info.filename,
                        destination_path="",
                        status=AssetStatus.SKIPPED,
                        file_type=ext,
                        size_bytes=info.file_size,
                    )
                )
                continue

            # Zip-slip prevention
            dest = (target_dir / info.filename).resolve()
            if not str(dest).startswith(str(target_resolved)):
                logger.warning(
                    f"Zip-slip rejected: {info.filename} resolves outside target"
                )
                assets.append(
                    ExtractedAsset(
                        archive_path=info.filename,
                        destination_path=str(dest),
                        status=AssetStatus.SKIPPED,
                        file_type=ext,
                        size_bytes=info.file_size,
                    )
                )
                continue

            # No-overwrite
            if dest.exists():
                assets.append(
                    ExtractedAsset(
                        archive_path=info.filename,
                        destination_path=str(dest),
                        status=AssetStatus.ALREADY_EXISTS,
                        file_type=ext,
                        size_bytes=info.file_size,
                    )
                )
                continue

            # Extract
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(dest, "wb") as dst:
                dst.write(src.read())

            assets.append(
                ExtractedAsset(
                    archive_path=info.filename,
                    destination_path=str(dest),
                    status=AssetStatus.EXTRACTED,
                    file_type=ext,
                    size_bytes=info.file_size,
                )
            )

    return assets


# ---------------------------------------------------------------------------
# Imported metadata parsing  (T023)
# ---------------------------------------------------------------------------


def _parse_imported_metadata(
    rgbeffects_path: Path,
) -> list[ImportedModelMeta]:
    """Parse xlights_rgbeffects.xml to extract model metadata.

    Returns list of ImportedModelMeta for models and groups found.
    """
    if not rgbeffects_path.exists():
        return []

    tree = etree.parse(str(rgbeffects_path))
    root = tree.getroot()
    models_elem = root.find("models")
    if models_elem is None:
        return []

    result: list[ImportedModelMeta] = []

    for elem in models_elem:
        if elem.tag == "model":
            name = elem.get("name", "")
            if not name:
                continue

            display_as = elem.get("DisplayAs", "")
            pixel_count = 0
            parm1 = elem.get("parm1", "0")
            parm2 = elem.get("parm2", "0")
            pixel_count_attr = elem.get("PixelCount", "")
            if pixel_count_attr:
                try:
                    pixel_count = int(pixel_count_attr)
                except ValueError:
                    pass
            elif parm1 and parm2:
                try:
                    pixel_count = int(parm1) * int(parm2)
                except ValueError:
                    pass

            face_definitions: list[str] = []
            for child in elem:
                if child.tag == "faceInfo":
                    face_name = child.get("Name", "")
                    if face_name:
                        face_definitions.append(face_name)

            result.append(
                ImportedModelMeta(
                    name=name,
                    display_as=display_as,
                    pixel_count=pixel_count,
                    face_definitions=face_definitions,
                )
            )

        elif elem.tag == "modelGroup":
            name = elem.get("name", "")
            if not name:
                continue
            members_str = elem.get("models", "")
            members = [m.strip() for m in members_str.split(",") if m.strip()]
            result.append(
                ImportedModelMeta(
                    name=name,
                    is_group=True,
                    group_members=members,
                )
            )

    return result


# ---------------------------------------------------------------------------
# Import dispatcher  (T024)
# ---------------------------------------------------------------------------


def import_package(
    import_path: Path,
    show_folder: Path,
) -> tuple[
    ImportedSequenceData,
    etree._Element,
    list[ImportedModelMeta] | None,
    list[ExtractedAsset],
]:
    """Dispatch import based on file extension (.xsq or .zip).

    Returns:
        Tuple of (seq_data, lxml_root, imported_meta_or_None, extracted_assets).

    Raises:
        FileNotFoundError: If the import file doesn't exist.
        ValueError: If a zip has 0 or >1 .xsq files.
    """
    if not import_path.exists():
        raise FileNotFoundError(f"File not found: {import_path}")

    ext = import_path.suffix.lower()

    if ext == ".xsq":
        seq_data, root = parse_xsq(import_path)
        return seq_data, root, None, []

    if ext == ".zip":
        # Extract assets
        assets = _extract_zip(import_path, show_folder)

        # Find extracted .xsq files
        xsq_assets = [
            a for a in assets
            if a.file_type == ".xsq" and a.status in (AssetStatus.EXTRACTED, AssetStatus.ALREADY_EXISTS)
        ]
        if len(xsq_assets) == 0:
            raise ValueError("No .xsq sequence file found in the zip archive.")
        if len(xsq_assets) > 1:
            names = [PurePosixPath(a.archive_path).name for a in xsq_assets]
            raise ValueError(
                f"Multiple .xsq files found in zip: {names}. "
                "Please extract the desired .xsq and provide it directly."
            )

        xsq_path = Path(xsq_assets[0].destination_path)
        seq_data, root = parse_xsq(xsq_path)

        # Look for xlights_rgbeffects.xml in extracted assets
        imported_meta: list[ImportedModelMeta] | None = None
        for asset in assets:
            if (
                PurePosixPath(asset.archive_path).name == "xlights_rgbeffects.xml"
                and asset.status in (AssetStatus.EXTRACTED, AssetStatus.ALREADY_EXISTS)
            ):
                meta_path = Path(asset.destination_path)
                imported_meta = _parse_imported_metadata(meta_path)
                break

        return seq_data, root, imported_meta, assets

    raise ValueError(f"Unsupported file type: {ext}")
