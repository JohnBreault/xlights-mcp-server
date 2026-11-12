"""Beat-synchronous novelty and acoustic repetition for song sections."""

from __future__ import annotations

import logging
from itertools import pairwise
from pathlib import Path

import librosa
import numpy as np
from pydantic import BaseModel, ConfigDict

from xlights_mcp.audio.beats import (
    FRAME_LENGTH,
    HOP_LENGTH,
    BeatMap,
    _analyze_beats,
    _prepare_rhythm,
    _validate_audio,
)

logger = logging.getLogger(__name__)


class SongSection(BaseModel):
    """A detected section, with heuristic (not calibrated) label confidence."""

    model_config = ConfigDict(allow_inf_nan=False)

    label: str
    start_time: float
    end_time: float
    energy_level: float = 0.0
    confidence: float = 0.0

    @property
    def start_time_ms(self) -> int:
        return int(self.start_time * 1000)

    @property
    def end_time_ms(self) -> int:
        return int(self.end_time * 1000)

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


def detect_structure(audio_path: Path, sr: int = 22050) -> list[SongSection]:
    """Detect sections without trimming or shifting the original audio timeline."""
    y, sr = librosa.load(str(audio_path), sr=sr, mono=True)
    _validate_audio(y, sr)
    magnitude = np.abs(librosa.stft(y, n_fft=FRAME_LENGTH, hop_length=HOP_LENGTH))
    onset, chroma = _prepare_rhythm(y, sr, magnitude)
    beats = _analyze_beats(y, sr, onset, chroma, audio_path)
    rms = librosa.feature.rms(y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)[0]
    return _analyze_structure(y, sr, beats, magnitude, rms, chroma)


def _novelty(features: np.ndarray, half_window: int = 4) -> np.ndarray:
    """Checkerboard novelty via local feature means, without a quadratic matrix.

    For dot-product similarity, the checkerboard block difference is exactly
    the squared distance between left and right mean feature vectors.
    """
    count = features.shape[1]
    result = np.zeros(count)
    width = min(half_window, (count - 1) // 2)
    if width < 1:
        return result
    sums = np.pad(np.cumsum(features, axis=1), ((0, 0), (1, 0)))
    centers = np.arange(width, count - width + 1)
    left = (sums[:, centers] - sums[:, centers - width]) / width
    right = (sums[:, centers + width] - sums[:, centers]) / width
    result[centers] = np.sum((left - right) ** 2, axis=0)
    return result / max(float(result.max()), 1e-8)


def _standardize(block: np.ndarray) -> np.ndarray:
    spread = block.std(axis=1, keepdims=True)
    return (block - block.mean(axis=1, keepdims=True)) / np.maximum(spread, 1e-6)


def _section_boundaries(
    novelty: np.ndarray, times: np.ndarray, beats: BeatMap, duration: float
) -> list[float]:
    peaks = librosa.util.peak_pick(
        novelty, pre_max=4, post_max=4, pre_avg=8, post_avg=8, delta=0.1, wait=8
    )
    candidates = [float(times[i]) for i in peaks if i < len(times)]
    if (beats.downbeat_confidence > 0 or beats.rhythm_method == "madmom") and beats.downbeat_times:
        bars = np.asarray(beats.downbeat_times)
        tolerance = min(1.0, 30 / max(beats.tempo, 1))
        candidates = [
            float(bars[np.argmin(abs(bars - t))])
            if float(np.min(abs(bars - t))) <= tolerance
            else t
            for t in candidates
        ]
    minimum = max(1.0, 4 * 60 / max(beats.tempo, 60))
    boundaries = [0.0]
    for candidate in sorted(set(candidates)):
        if candidate - boundaries[-1] >= minimum and duration - candidate >= minimum:
            boundaries.append(candidate)
    return [*boundaries, duration]


def _energy_boundaries(rms: np.ndarray, sr: int, duration: float) -> list[float]:
    if len(rms) < 3 or float(rms.max()) < 1e-8:
        return [0.0, duration]
    width = min(len(rms), max(1, round(sr / HOP_LENGTH)))
    smooth = np.convolve(
        np.pad(rms, (width // 2, width - 1 - width // 2), mode="edge"),
        np.ones(width) / width,
        mode="valid",
    )
    derivative = np.abs(np.diff(smooth))
    threshold = max(float(np.max(derivative)) * 0.4, float(rms.max()) * 0.005)
    boundaries = [0.0]
    for i in range(1, len(derivative) - 1):
        time = i * HOP_LENGTH / sr
        if (
            derivative[i] > threshold
            and derivative[i] > derivative[i - 1]
            and derivative[i] >= derivative[i + 1]
            and time - boundaries[-1] >= 4
            and duration - time >= 4
        ):
            boundaries.append(time)
    return [*boundaries, duration]


def _analyze_structure(
    y: np.ndarray,
    sr: int,
    beats: BeatMap,
    magnitude: np.ndarray,
    rms: np.ndarray,
    chroma: np.ndarray,
) -> list[SongSection]:
    duration = len(y) / sr
    frame_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=HOP_LENGTH)
    mel = librosa.feature.melspectrogram(S=magnitude**2, sr=sr, n_fft=FRAME_LENGTH)
    mfcc = librosa.feature.mfcc(S=librosa.power_to_db(mel), n_mfcc=13)
    centroid = librosa.feature.spectral_centroid(S=magnitude, sr=sr)
    blocks = [mfcc, chroma, centroid, rms.reshape(1, -1)]
    count = min(block.shape[1] for block in blocks)
    acoustic = np.vstack([_standardize(block[:, :count]) for block in blocks])
    boundaries = [0.0, duration]
    if len(beats.beat_times) >= 8 and float(rms.max()) > 1e-8:
        edges = librosa.time_to_frames(beats.beat_times, sr=sr, hop_length=HOP_LENGTH)
        edges = np.unique(np.clip(np.r_[0, edges, count], 0, count))
        synchronized = librosa.util.sync(acoustic, edges, aggregate=np.mean, pad=False)
        synchronized = librosa.util.normalize(synchronized, axis=0)
        times = librosa.frames_to_time(edges[:-1], sr=sr, hop_length=HOP_LENGTH)
        boundaries = _section_boundaries(_novelty(synchronized), times, beats, duration)
    if len(boundaries) == 2:
        logger.info("Insufficient section novelty; using conservative energy boundaries")
        boundaries = _energy_boundaries(rms, sr, duration)
    sections = []
    descriptors = []
    for start, end in pairwise(boundaries):
        mask = (frame_times >= start) & (frame_times < end)
        energy = float(np.mean(rms[mask])) if mask.any() else 0.0
        sections.append(
            SongSection(label="unknown", start_time=start, end_time=end, energy_level=energy)
        )
        feature_mask = (frame_times[:count] >= start) & (frame_times[:count] < end)
        descriptors.append(
            acoustic[:, feature_mask].mean(axis=1)
            if feature_mask.any()
            else np.zeros(acoustic.shape[0])
        )
    peak_energy = max((section.energy_level for section in sections), default=0.0)
    if peak_energy < 1e-8:
        return sections
    descriptor_matrix = librosa.util.normalize(np.asarray(descriptors).T, axis=0)
    similarity = descriptor_matrix.T @ descriptor_matrix
    np.fill_diagonal(similarity, -1.0)
    for i, section in enumerate(sections):
        section.energy_level /= peak_energy
        repeated = len(sections) > 2 and bool(np.any(similarity[i] > 0.8))
        position = section.start_time / duration
        if i == 0 and section.duration < 15 and section.energy_level < 0.7:
            section.label = "intro"
        elif i == len(sections) - 1 and position > 0.8 and section.energy_level < 0.7:
            section.label = "outro"
        elif section.energy_level > 0.7:
            # Too few sections cannot establish repetition; retain the energy fallback.
            section.label = "chorus" if repeated or len(sections) < 3 else "verse"
        elif position > 0.45 and section.energy_level < 0.3 and not repeated:
            section.label = "bridge"
        else:
            section.label = "verse"
        section.confidence = 0.6 if repeated else 0.4
    return sections
