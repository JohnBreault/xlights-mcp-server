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
        import demucs.separate
    except ImportError:
        logger.warning(
            "Demucs not installed. Install with: pip install xlights-mcp-server[separation]"
        )
        return StemPaths(available=False)

    if output_dir is None:
        output_dir = audio_path.parent / "stems" / audio_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check cache — vocals is the minimum required stem
    stems = StemPaths(available=True)
    expected = {
        "vocals": output_dir / "vocals.wav",
        "drums": output_dir / "drums.wav",
        "bass": output_dir / "bass.wav",
        "other": output_dir / "other.wav",
    }

    vocals_cached = expected["vocals"].exists()
    if vocals_cached:
        logger.info("Using cached stems")
        stems.vocals = str(expected["vocals"])
        for name in ("drums", "bass", "other"):
            if expected[name].exists():
                setattr(stems, name, str(expected[name]))
        return stems

    logger.info(f"Separating stems with {model}: {audio_path}")

    try:
        # Fix SSL cert issues on macOS
        import os
        try:
            import certifi
            os.environ.setdefault("SSL_CERT_FILE", certifi.where())
            os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
        except ImportError:
            pass

        # Try newer demucs.api first, fall back to CLI-based separation
        try:
            import demucs.api
            separator = demucs.api.Separator(model=model)
            _, outputs = separator.separate_audio_file(str(audio_path))

            import soundfile as sf
            for stem_name, tensor in outputs.items():
                out_path = output_dir / f"{stem_name}.wav"
                audio_np = tensor.cpu().numpy()
                if audio_np.ndim > 1:
                    audio_np = audio_np.T
                sf.write(str(out_path), audio_np, separator.samplerate)
                setattr(stems, stem_name, str(out_path))
        except (ImportError, AttributeError):
            # Older demucs — use CLI-style separation
            import subprocess
            import sys
            result = subprocess.run(
                [sys.executable, "-m", "demucs.separate",
                 "-n", model,
                 "-o", str(output_dir.parent),
                 str(audio_path)],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode != 0:
                raise RuntimeError(f"demucs failed: {result.stderr[-1000:]}")

            # Demucs CLI outputs to: output_dir.parent / model / audio_stem / *.wav
            cli_out = output_dir.parent / model / audio_path.stem
            import shutil
            for stem_name in ("vocals", "drums", "bass", "other"):
                src = cli_out / f"{stem_name}.wav"
                if src.exists():
                    dst = expected[stem_name]
                    shutil.move(str(src), str(dst))
                    setattr(stems, stem_name, str(dst))

        logger.info(f"Stems saved to {output_dir}")
    except Exception as e:
        logger.error(f"Stem separation failed: {e}")
        stems.available = False

    return stems
