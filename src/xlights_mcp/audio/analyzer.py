"""Full audio analysis pipeline — combines all analysis modules."""

from __future__ import annotations

import logging
from pathlib import Path

import librosa
import numpy as np
from pydantic import BaseModel, Field

from xlights_mcp.audio.beats import BeatMap, detect_beats
from xlights_mcp.audio.spectrum import SpectrumAnalysis, analyze_spectrum
from xlights_mcp.audio.structure import SongSection, detect_structure
from xlights_mcp.audio.separator import StemPaths, separate_stems
from xlights_mcp.config import AudioConfig

logger = logging.getLogger(__name__)


class StemOnsets(BaseModel):
    """Onset and energy analysis for a single audio stem."""

    name: str  # "drums", "bass", "other", "vocals"
    onset_times: list[float] = Field(default_factory=list)  # seconds
    energy: list[float] = Field(default_factory=list)  # normalized 0-1 per frame
    energy_times: list[float] = Field(default_factory=list)  # seconds
    mean_energy: float = 0.0


class StemAnalysis(BaseModel):
    """Onset and energy analysis for all separated stems."""

    available: bool = False
    stems: dict[str, StemOnsets] = Field(default_factory=dict)  # name → StemOnsets

    def get_onsets_in_range(self, stem: str, start: float, end: float) -> list[float]:
        """Get onset times for a stem within a time range."""
        if stem not in self.stems:
            return []
        return [t for t in self.stems[stem].onset_times if start <= t < end]

    def get_mean_energy_in_range(self, stem: str, start: float, end: float) -> float:
        """Get mean energy for a stem within a time range."""
        if stem not in self.stems:
            return 0.0
        s = self.stems[stem]
        energies = [e for t, e in zip(s.energy_times, s.energy) if start <= t < end]
        return float(np.mean(energies)) if energies else 0.0

    def dominant_stem(self, start: float, end: float) -> str:
        """Return the stem name with highest mean energy in a time range."""
        best_name = "other"
        best_energy = 0.0
        for name, stem in self.stems.items():
            e = self.get_mean_energy_in_range(name, start, end)
            if e > best_energy:
                best_energy = e
                best_name = name
        return best_name


class SongAnalysis(BaseModel):
    """Complete analysis of a music file for sequence generation."""

    file_path: str
    file_name: str
    duration_seconds: float = 0.0
    beats: BeatMap = Field(default_factory=BeatMap)
    spectrum: SpectrumAnalysis = Field(default_factory=SpectrumAnalysis)
    sections: list[SongSection] = Field(default_factory=list)
    stems: StemPaths = Field(default_factory=StemPaths)
    stem_analysis: StemAnalysis = Field(default_factory=StemAnalysis)

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

    # Always try stem separation (results are cached)
    stems = StemPaths()
    stem_analysis = StemAnalysis()
    try:
        stems = separate_stems(audio_path)
        if stems.available:
            stem_analysis = analyze_stems(stems, sr=sr)
    except Exception as e:
        logger.info(f"Stem analysis unavailable: {e}")

    analysis = SongAnalysis(
        file_path=str(audio_path),
        file_name=audio_path.name,
        duration_seconds=spectrum.duration_seconds,
        beats=beats,
        spectrum=spectrum,
        sections=sections,
        stems=stems,
        stem_analysis=stem_analysis,
    )

    logger.info(
        f"Analysis complete: {analysis.duration_seconds:.1f}s, "
        f"{beats.tempo:.0f} BPM, "
        f"{len(sections)} sections, "
        f"{len(beats.beat_times)} beats, "
        f"stems={'yes' if stem_analysis.available else 'no'}"
    )

    return analysis


def analyze_stems(stem_paths: StemPaths, sr: int = 22050) -> StemAnalysis:
    """Run onset detection and energy analysis on separated stems.

    Args:
        stem_paths: Paths to the Demucs-separated stem .wav files
        sr: Sample rate for analysis
    """
    stem_map = {
        "drums": stem_paths.drums,
        "bass": stem_paths.bass,
        "other": stem_paths.other,
        "vocals": stem_paths.vocals,
    }

    results: dict[str, StemOnsets] = {}

    for name, path_str in stem_map.items():
        if not path_str:
            continue
        stem_path = Path(path_str)
        if not stem_path.exists():
            continue

        try:
            y, loaded_sr = librosa.load(str(stem_path), sr=sr, mono=True)

            # Onset detection
            onset_env = librosa.onset.onset_strength(y=y, sr=loaded_sr)
            onset_frames = librosa.onset.onset_detect(
                onset_envelope=onset_env, sr=loaded_sr, backtrack=True
            )
            onset_times = librosa.frames_to_time(onset_frames, sr=loaded_sr).tolist()

            # RMS energy curve
            rms = librosa.feature.rms(y=y)[0]
            rms_times = librosa.times_like(rms, sr=loaded_sr).tolist()
            max_rms = float(rms.max()) + 1e-8
            normalized_rms = (rms / max_rms).tolist()
            mean_energy = float(np.mean(rms / max_rms))

            results[name] = StemOnsets(
                name=name,
                onset_times=onset_times,
                energy=normalized_rms,
                energy_times=rms_times,
                mean_energy=mean_energy,
            )
            logger.info(f"  Stem '{name}': {len(onset_times)} onsets, mean energy {mean_energy:.2f}")

        except Exception as e:
            logger.warning(f"Failed to analyze stem '{name}': {e}")

    if results:
        logger.info(f"Stem analysis complete: {list(results.keys())}")
        return StemAnalysis(available=True, stems=results)

    return StemAnalysis(available=False)
