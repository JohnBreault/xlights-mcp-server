"""Frequency spectrum and energy analysis for music files."""

from __future__ import annotations

import logging
from pathlib import Path

import librosa
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from xlights_mcp.audio.beats import FRAME_LENGTH, HOP_LENGTH, _validate_audio

logger = logging.getLogger(__name__)


class BandEnergy(BaseModel):
    """Energy levels for a frequency band over time."""

    model_config = ConfigDict(allow_inf_nan=False)

    name: str  # "bass", "mids", "highs"
    freq_range: tuple[int, int]  # Hz range
    # Normalized 0.0-1.0 energy values, one per analysis frame
    energy: list[float] = Field(default_factory=list)
    frame_times: list[float] = Field(default_factory=list)  # seconds
    peak_times: list[float] = Field(default_factory=list)  # seconds where energy peaks


class SpectrumAnalysis(BaseModel):
    """Frequency spectrum and energy analysis results."""

    model_config = ConfigDict(allow_inf_nan=False)

    duration_seconds: float = 0.0
    rms_energy: list[float] = Field(default_factory=list)  # overall loudness curve
    rms_times: list[float] = Field(default_factory=list)
    bands: list[BandEnergy] = Field(default_factory=list)
    peak_loudness_time: float = 0.0  # time of peak loudness
    average_loudness: float = 0.0
    dynamic_range: float = 0.0  # ratio of max to mean energy
    spectral_flux: list[float] = Field(default_factory=list)  # normalized positive flux
    spectral_centroid: list[float] = Field(default_factory=list)  # Hz
    spectral_bandwidth: list[float] = Field(default_factory=list)  # Hz
    spectral_rolloff: list[float] = Field(default_factory=list)  # Hz, 85% cumulative magnitude
    spectral_flatness: list[float] = Field(default_factory=list)  # 0-1
    energy_short: list[float] = Field(default_factory=list)  # 0.25-second smoothing
    energy_medium: list[float] = Field(default_factory=list)  # 2-second smoothing
    energy_long: list[float] = Field(default_factory=list)  # 8-second smoothing


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
    _validate_audio(y, sr)
    return _analyze_spectrum(y, sr, use_simple_bands)


def _smooth_energy(values: np.ndarray, seconds: float, sr: int) -> list[float]:
    width = min(len(values), max(1, round(seconds * sr / HOP_LENGTH)))
    width = width if width % 2 else max(1, width - 1)
    padded = np.pad(values, width // 2, mode="edge")
    return np.clip(np.convolve(padded, np.ones(width) / width, mode="valid"), 0, 1).tolist()


def _analyze_spectrum(
    y: np.ndarray,
    sr: int,
    use_simple_bands: bool = True,
    magnitude: np.ndarray | None = None,
    rms: np.ndarray | None = None,
) -> SpectrumAnalysis:
    duration = librosa.get_duration(y=y, sr=sr)

    # RMS energy (overall loudness)
    if rms is None:
        rms = librosa.feature.rms(y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)[0]
    rms_times = librosa.times_like(rms, sr=sr).tolist()
    rms_normalized = (rms / (rms.max() + 1e-8)).tolist()

    # Peak loudness
    peak_idx = int(np.argmax(rms))
    peak_time = rms_times[peak_idx] if rms_times else 0.0
    avg_loudness = float(np.mean(rms))
    dynamic_range = float(np.max(rms) / (avg_loudness + 1e-8))

    # Frequency band analysis
    S = magnitude
    if S is None:
        S = np.abs(librosa.stft(y, n_fft=FRAME_LENGTH, hop_length=HOP_LENGTH))
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
        spectral_flux=_normalized_flux(S),
        spectral_centroid=librosa.feature.spectral_centroid(S=S, sr=sr)[0].tolist(),
        spectral_bandwidth=librosa.feature.spectral_bandwidth(S=S, sr=sr)[0].tolist(),
        spectral_rolloff=librosa.feature.spectral_rolloff(S=S, sr=sr)[0].tolist(),
        spectral_flatness=librosa.feature.spectral_flatness(S=S)[0].tolist(),
        energy_short=_smooth_energy(np.asarray(rms_normalized), 0.25, sr),
        energy_medium=_smooth_energy(np.asarray(rms_normalized), 2.0, sr),
        energy_long=_smooth_energy(np.asarray(rms_normalized), 8.0, sr),
    )


def _normalized_flux(magnitude: np.ndarray) -> list[float]:
    positive = np.maximum(np.diff(magnitude, axis=1), 0).mean(axis=0)
    flux = np.r_[0.0, positive]
    return (flux / max(float(flux.max()), 1e-8)).tolist()


def _find_peaks(data: np.ndarray, threshold: float = 0.7, min_distance: int = 4) -> list[int]:
    """Find peak indices in a 1D array above a relative threshold."""
    max_val = data.max()
    abs_threshold = threshold * max_val
    peaks = []
    for i in range(1, len(data) - 1):
        if (
            data[i] > abs_threshold
            and data[i] > data[i - 1]
            and data[i] > data[i + 1]
            and (not peaks or (i - peaks[-1]) >= min_distance)
        ):
            peaks.append(i)
    return peaks
