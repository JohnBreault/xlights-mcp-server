"""Rewrite hardcoded file paths in effect parameters.

Handles FILEPICKERCTRL keys in EffectDB settings strings and
the mediaFile attribute in <head>.
"""

from __future__ import annotations

import logging
from pathlib import Path, PurePosixPath

from lxml import etree

logger = logging.getLogger(__name__)


def rewrite_effect_paths(
    root: etree._Element,
    show_folder: Path,
) -> list[str]:
    """Rewrite foreign absolute paths in the cloned tree.

    Targets:
    1. EffectDB entries: FILEPICKERCTRL key=value pairs
    2. <head> mediaFile attribute

    Returns list of warnings for missing media files.
    """
    warnings: list[str] = []

    # --- Rewrite EffectDB paths ---
    effect_db = root.find("EffectDB")
    if effect_db is not None:
        for effect_elem in effect_db:
            original = effect_elem.text or ""
            if "FILEPICKERCTRL" not in original:
                continue
            rewritten = _rewrite_settings_string(original, show_folder, warnings)
            if rewritten != original:
                effect_elem.text = rewritten

    # --- Rewrite <head> mediaFile ---
    head = root.find("head")
    if head is not None:
        media_elem = head.find("mediaFile")
        media_text = ""
        if media_elem is not None and media_elem.text:
            media_text = media_elem.text.strip()
        elif head.get("mediaFile"):
            media_text = head.get("mediaFile", "").strip()

        if media_text:
            basename = PurePosixPath(media_text).name or Path(media_text).name
            if basename:
                new_path = show_folder / basename
                if media_elem is not None:
                    media_elem.text = str(new_path)
                else:
                    head.set("mediaFile", str(new_path))
                if not new_path.exists():
                    warnings.append(
                        f"Media file not found in show folder: {basename}"
                    )

    return warnings


def _rewrite_settings_string(
    settings: str,
    show_folder: Path,
    warnings: list[str],
) -> str:
    """Rewrite FILEPICKERCTRL paths in a comma-separated settings string.

    Non-path keys are preserved unchanged.
    """
    parts = settings.split(",")
    rewritten_parts: list[str] = []

    for part in parts:
        if "FILEPICKERCTRL" not in part:
            rewritten_parts.append(part)
            continue

        eq_idx = part.find("=")
        if eq_idx < 0:
            rewritten_parts.append(part)
            continue

        key = part[:eq_idx]
        value = part[eq_idx + 1:]

        if not value.strip():
            rewritten_parts.append(part)
            continue

        # Extract basename from the foreign path
        basename = PurePosixPath(value.strip()).name or Path(value.strip()).name
        if not basename:
            rewritten_parts.append(part)
            continue

        new_path = show_folder / basename
        rewritten_parts.append(f"{key}={new_path}")

        if not new_path.exists():
            warnings.append(
                f"Referenced media not found: {basename}"
            )

    return ",".join(rewritten_parts)
