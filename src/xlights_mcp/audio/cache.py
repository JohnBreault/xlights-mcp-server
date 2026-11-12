"""Versioned, validated core-analysis cache; optional stems are never cached here."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pydantic import BaseModel, ValidationError

from xlights_mcp.audio.beats import BeatMap
from xlights_mcp.audio.spectrum import SpectrumAnalysis
from xlights_mcp.audio.structure import SongSection

logger = logging.getLogger(__name__)
CACHE_VERSION = 1
# ponytail: no eviction; add a size budget if cached analyses become large.


class CoreAnalysis(BaseModel):
    beats: BeatMap
    spectrum: SpectrumAnalysis
    sections: list[SongSection]


def _dependency_versions() -> dict[str, str | None]:
    versions = {}
    for package in ("librosa", "numpy", "scipy", "soundfile", "madmom"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return versions


def cache_key(audio_path: Path, sr: int) -> str:
    with audio_path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256")
    digest.update(
        json.dumps(
            {"version": CACHE_VERSION, "sample_rate": sr, "dependencies": _dependency_versions()},
            sort_keys=True,
        ).encode()
    )
    return digest.hexdigest()


def load_core(cache_dir: Path, key: str) -> CoreAnalysis | None:
    path = cache_dir / f"analysis-v{CACHE_VERSION}-{key}.json"
    try:
        return CoreAnalysis.model_validate_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, ValidationError) as exc:
        logger.warning("Cannot read analysis cache %s; recomputing: %s", path, exc)
        return None


def save_core(cache_dir: Path, key: str, analysis: CoreAnalysis) -> None:
    temporary: Path | None = None
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=cache_dir, prefix=".analysis-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(analysis.model_dump_json())
        os.replace(temporary, cache_dir / f"analysis-v{CACHE_VERSION}-{key}.json")
    except OSError as exc:
        logger.warning("Cannot persist analysis cache: %s", exc)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Cannot remove temporary analysis cache %s: %s", temporary, exc)
