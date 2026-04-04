"""Full audio analysis pipeline — combines all analysis modules."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from xlights_mcp.audio.beats import BeatMap, detect_beats
from xlights_mcp.audio.spectrum import SpectrumAnalysis, analyze_spectrum
from xlights_mcp.audio.structure import SongSection, detect_structure
from xlights_mcp.audio.separator import StemPaths, separate_stems
from xlights_mcp.config import AudioConfig

logger = logging.getLogger(__name__)


class SongAnalysis(BaseModel):
    """Complete analysis of a music file for sequence generation."""

    file_path: str
    file_name: str
    duration_seconds: float = 0.0
    beats: BeatMap = Field(default_factory=BeatMap)
    spectrum: SpectrumAnalysis = Field(default_factory=SpectrumAnalysis)
    sections: list[SongSection] = Field(default_factory=list)
    stems: StemPaths = Field(default_factory=StemPaths)

    @property
    def duration_ms(self) -> int:
        return int(self.duration_seconds * 1000)


def full_analysis(
    audio_path: Path,
    audio_config: AudioConfig | None = None,
    include_stems: bool = False,
) -> SongAnalysis:
    """Run the complete audio analysis pipeline.

    Args:
        audio_path: Path to the audio file (.mp3, .wav, etc.)
        audio_config: Audio configuration settings
        include_stems: Whether to run Demucs source separation
    """
    if audio_config is None:
        audio_config = AudioConfig()

    sr = audio_config.sample_rate
    logger.info(f"Starting full analysis: {audio_path}")

    # Run all analyses
    beats = detect_beats(audio_path, sr=sr)
    spectrum = analyze_spectrum(audio_path, sr=sr)
    sections = detect_structure(audio_path, sr=sr)

    # Optional stem separation
    stems = StemPaths()
    if include_stems:
        cache_dir = Path(audio_config.cache_dir).expanduser()
        stems = separate_stems(
            audio_path,
            output_dir=cache_dir / audio_path.stem,
            model=audio_config.demucs_model,
        )

    analysis = SongAnalysis(
        file_path=str(audio_path),
        file_name=audio_path.name,
        duration_seconds=spectrum.duration_seconds,
        beats=beats,
        spectrum=spectrum,
        sections=sections,
        stems=stems,
    )

    logger.info(
        f"Analysis complete: {analysis.duration_seconds:.1f}s, "
        f"{beats.tempo:.0f} BPM, "
        f"{len(sections)} sections, "
        f"{len(beats.beat_times)} beats"
    )

    return analysis
