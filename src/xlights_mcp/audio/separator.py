"""Source separation using Demucs (optional dependency)."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class StemPaths(BaseModel):
    """Paths to separated audio stems."""

    vocals: str = ""
    drums: str = ""
    bass: str = ""
    other: str = ""
    available: bool = False


def separate_stems(
    audio_path: Path,
    output_dir: Path | None = None,
    model: str = "htdemucs",
) -> StemPaths:
    """Separate audio into stems using Demucs.

    Requires the 'separation' optional dependency:
        pip install xlights-mcp-server[separation]

    Args:
        audio_path: Path to audio file
        output_dir: Where to save stems (defaults to audio_cache)
        model: Demucs model name
    """
    try:
        import torch
        import demucs.api
    except ImportError:
        logger.warning(
            "Demucs not installed. Install with: pip install xlights-mcp-server[separation]"
        )
        return StemPaths(available=False)

    if output_dir is None:
        output_dir = audio_path.parent / "stems" / audio_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check cache
    stems = StemPaths(available=True)
    expected = {
        "vocals": output_dir / "vocals.wav",
        "drums": output_dir / "drums.wav",
        "bass": output_dir / "bass.wav",
        "other": output_dir / "other.wav",
    }

    if all(p.exists() for p in expected.values()):
        logger.info("Using cached stems")
        stems.vocals = str(expected["vocals"])
        stems.drums = str(expected["drums"])
        stems.bass = str(expected["bass"])
        stems.other = str(expected["other"])
        return stems

    logger.info(f"Separating stems with {model}: {audio_path}")

    try:
        separator = demucs.api.Separator(model=model)
        _, outputs = separator.separate_audio_file(str(audio_path))

        import soundfile as sf

        for stem_name, tensor in outputs.items():
            out_path = output_dir / f"{stem_name}.wav"
            # Convert from torch tensor to numpy
            audio_np = tensor.cpu().numpy()
            if audio_np.ndim > 1:
                audio_np = audio_np.T  # channels last
            sf.write(str(out_path), audio_np, separator.samplerate)
            setattr(stems, stem_name, str(out_path))

        logger.info(f"Stems saved to {output_dir}")
    except Exception as e:
        logger.error(f"Stem separation failed: {e}")
        stems.available = False

    return stems
