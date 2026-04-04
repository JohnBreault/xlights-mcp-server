"""Read and summarize existing .xsq sequence files."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EffectSummary(BaseModel):
    """Summary of an effect placement in a sequence."""

    name: str
    start_time_ms: int
    end_time_ms: int
    palette_ref: str = ""


class ModelEffects(BaseModel):
    """Effects placed on a specific model."""

    model_name: str
    model_type: str = "model"
    effect_count: int = 0
    effects: list[EffectSummary] = Field(default_factory=list)


class SequenceSummary(BaseModel):
    """Summary of an .xsq sequence file."""

    file_name: str
    version: str = ""
    song: str = ""
    artist: str = ""
    album: str = ""
    media_file: str = ""
    duration_seconds: float = 0.0
    timing: str = "25 ms"
    sequence_type: str = ""
    palette_count: int = 0
    effect_db_count: int = 0
    model_count: int = 0
    total_effect_placements: int = 0
    models_with_effects: list[ModelEffects] = Field(default_factory=list)
    effect_types_used: list[str] = Field(default_factory=list)


def read_xsq_summary(xsq_path: Path) -> dict:
    """Parse an .xsq file and return a structured summary."""
    try:
        tree = ET.parse(xsq_path)
    except ET.ParseError as e:
        return {"error": f"Failed to parse {xsq_path}: {e}"}

    root = tree.getroot()
    head = root.find("head")

    # Extract header info
    summary = SequenceSummary(file_name=xsq_path.name)
    if head is not None:
        summary.version = _text(head, "version")
        summary.song = _text(head, "song")
        summary.artist = _text(head, "artist")
        summary.album = _text(head, "album")
        summary.media_file = _text(head, "mediaFile")
        summary.timing = _text(head, "sequenceTiming", "25 ms")
        summary.sequence_type = _text(head, "sequenceType")

        duration_str = _text(head, "sequenceDuration", "0")
        try:
            summary.duration_seconds = float(duration_str)
        except ValueError:
            pass

    # Count palettes
    palettes = root.find("ColorPalettes")
    if palettes is not None:
        summary.palette_count = len(list(palettes))

    # Count effect definitions
    effect_db = root.find("EffectDB")
    if effect_db is not None:
        summary.effect_db_count = len(list(effect_db))

    # Parse element effects
    element_effects = root.find("ElementEffects")
    effect_types = set()
    total_placements = 0

    if element_effects is not None:
        for elem in element_effects:
            model_name = elem.get("name", "")
            model_type = elem.get("type", "model")

            effects_list = []
            for layer in elem:
                for effect in layer:
                    eff_name = effect.get("name", "")
                    start = int(effect.get("startTime", "0"))
                    end = int(effect.get("endTime", "0"))
                    palette = effect.get("palette", "")

                    effects_list.append(
                        EffectSummary(
                            name=eff_name,
                            start_time_ms=start,
                            end_time_ms=end,
                            palette_ref=palette,
                        )
                    )
                    effect_types.add(eff_name)
                    total_placements += 1

            if effects_list:
                summary.models_with_effects.append(
                    ModelEffects(
                        model_name=model_name,
                        model_type=model_type,
                        effect_count=len(effects_list),
                        effects=effects_list,
                    )
                )

        summary.model_count = len(list(element_effects))

    summary.total_effect_placements = total_placements
    summary.effect_types_used = sorted(effect_types)

    return summary.model_dump()


def read_xsq_palettes(xsq_path: Path) -> list[dict]:
    """Extract color palette definitions from an .xsq file."""
    tree = ET.parse(xsq_path)
    root = tree.getroot()
    palettes = root.find("ColorPalettes")
    if palettes is None:
        return []

    result = []
    for i, p in enumerate(palettes):
        text = p.text or ""
        colors = {}
        for pair in text.split(","):
            if "=" in pair:
                key, val = pair.split("=", 1)
                colors[key.strip()] = val.strip()
        result.append({"index": i, "raw": text, "colors": colors})
    return result


def read_xsq_effect_db(xsq_path: Path) -> list[dict]:
    """Extract the EffectDB (deduplicated effect settings) from an .xsq file."""
    tree = ET.parse(xsq_path)
    root = tree.getroot()
    effect_db = root.find("EffectDB")
    if effect_db is None:
        return []

    result = []
    for i, e in enumerate(effect_db):
        text = e.text or ""
        settings = {}
        for pair in text.split(","):
            if "=" in pair:
                key, val = pair.split("=", 1)
                settings[key.strip()] = val.strip()
        result.append({"index": i, "raw": text[:200], "settings": settings})
    return result


def _text(parent: ET.Element, tag: str, default: str = "") -> str:
    """Safely extract text from a child element."""
    elem = parent.find(tag)
    if elem is not None and elem.text:
        return elem.text.strip()
    return default
