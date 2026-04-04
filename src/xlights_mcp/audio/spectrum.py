"""Frequency spectrum and energy analysis for music files."""

from __future__ import annotations

import logging
from pathlib import Path

import librosa
import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BandEnergy(BaseModel):
    """Energy levels for a frequency band over time."""

    name: str  # "bass", "mids", "highs"
    freq_range: tuple[int, int]  # Hz range
    # Normalized 0.0-1.0 energy values, one per analysis frame
    energy: list[float] = Field(default_factory=list)
    frame_times: list[float] = Field(default_factory=list)  # seconds
    peak_times: list[float] = Field(default_factory=list)  # seconds where energy peaks


class SpectrumAnalysis(BaseModel):
    """Frequency spectrum and energy analysis results."""

    duration_seconds: float = 0.0
    rms_energy: list[float] = Field(default_factory=list)  # overall loudness curve
    rms_times: list[float] = Field(default_factory=list)
    bands: list[BandEnergy] = Field(default_factory=list)
    peak_loudness_time: float = 0.0  # time of peak loudness
    average_loudness: float = 0.0
    dynamic_range: float = 0.0  # ratio of max to mean energy


# Standard frequency band definitions
FREQUENCY_BANDS = {
    "sub_bass": (20, 60),
    "bass": (60, 250),
    "low_mids": (250, 500),
    "mids": (500, 2000),
    "high_mids": (2000, 4000),
    "highs": (4000, 8000),
    "brilliance": (8000, 16000),
}

# Simplified 3-band split for effect mapping
SIMPLE_BANDS = {
    "bass": (20, 250),
    "mids": (250, 4000),
    "highs": (4000, 16000),
}


def analyze_spectrum(
    audio_path: Path,
    sr: int = 22050,
    use_simple_bands: bool = True,
) -> SpectrumAnalysis:
    """Analyze frequency spectrum and energy of an audio file.

    Args:
        audio_path: Path to audio file
        sr: Sample rate
        use_simple_bands: Use 3-band (bass/mid/high) split instead of 7-band
    """
    logger.info(f"Analyzing spectrum: {audio_path}")
    y, sr = librosa.load(str(audio_path), sr=sr, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)

    # RMS energy (overall loudness)
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.times_like(rms, sr=sr).tolist()
    rms_normalized = (rms / (rms.max() + 1e-8)).tolist()

    # Peak loudness
    peak_idx = int(np.argmax(rms))
    peak_time = rms_times[peak_idx] if rms_times else 0.0
    avg_loudness = float(np.mean(rms))
    dynamic_range = float(np.max(rms) / (avg_loudness + 1e-8))

    # Frequency band analysis
    S = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)
    frame_times = librosa.times_like(S, sr=sr).tolist()

    bands_def = SIMPLE_BANDS if use_simple_bands else FREQUENCY_BANDS
    band_results = []

    for band_name, (lo, hi) in bands_def.items():
        idx = (freqs >= lo) & (freqs < hi)
        if not np.any(idx):
            continue

        band_energy = S[idx].mean(axis=0)
        max_e = band_energy.max() + 1e-8
        normalized = (band_energy / max_e).tolist()

        # Find peaks in this band
        peak_indices = _find_peaks(band_energy, threshold=0.7)
        peak_times = [frame_times[i] for i in peak_indices if i < len(frame_times)]

        band_results.append(
            BandEnergy(
                name=band_name,
                freq_range=(lo, hi),
                energy=normalized,
                frame_times=frame_times,
                peak_times=peak_times,
            )
        )

    logger.info(
        f"Spectrum: duration={duration:.1f}s, "
        f"peak@{peak_time:.1f}s, "
        f"dynamic_range={dynamic_range:.1f}"
    )

    return SpectrumAnalysis(
        duration_seconds=duration,
        rms_energy=rms_normalized,
        rms_times=rms_times,
        bands=band_results,
        peak_loudness_time=peak_time,
        average_loudness=avg_loudness,
        dynamic_range=dynamic_range,
    )


def _find_peaks(
    data: np.ndarray, threshold: float = 0.7, min_distance: int = 4
) -> list[int]:
    """Find peak indices in a 1D array above a relative threshold."""
    max_val = data.max()
    abs_threshold = threshold * max_val
    peaks = []
    for i in range(1, len(data) - 1):
        if data[i] > abs_threshold and data[i] > data[i - 1] and data[i] > data[i + 1]:
            if not peaks or (i - peaks[-1]) >= min_distance:
                peaks.append(i)
    return peaks
