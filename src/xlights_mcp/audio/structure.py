"""Song structure detection — identify verse, chorus, bridge sections."""

from __future__ import annotations

import logging
from pathlib import Path

import librosa
import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SongSection(BaseModel):
    """A detected section of a song (verse, chorus, bridge, etc.)."""

    label: str  # "intro", "verse", "chorus", "bridge", "outro", "instrumental"
    start_time: float  # seconds
    end_time: float  # seconds
    energy_level: float = 0.0  # 0.0-1.0 average energy
    confidence: float = 0.0  # detection confidence

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
    """Detect song structure (verse/chorus/bridge/etc.).

    Uses a hybrid approach:
    1. MFCC/chroma self-similarity for boundary detection
    2. RMS energy for section labeling
    3. Fallback to energy-based segmentation if too few boundaries found
    """
    logger.info(f"Analyzing song structure: {audio_path}")
    y, sr = librosa.load(str(audio_path), sr=sr, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)

    # Extract features for structure analysis
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    features = np.vstack([mfcc, chroma])

    # Build self-similarity matrix
    rec = librosa.segment.recurrence_matrix(
        features, mode="affinity", sym=True, bandwidth=1.0
    )

    # Compute novelty curve with adaptive kernel
    kernel_size = max(8, min(64, features.shape[1] // 20))
    novelty = _compute_novelty(rec, kernel_size=kernel_size)
    boundary_frames = _detect_boundaries(novelty, min_section_frames=15, peak_threshold=0.1)
    boundary_times = librosa.frames_to_time(boundary_frames, sr=sr).tolist()

    # If we got too few sections, fall back to energy-based segmentation
    min_sections = max(4, int(duration / 30))  # at least 1 section per 30s
    if len(boundary_times) < min_sections:
        logger.info(f"Novelty found only {len(boundary_times)} boundaries, using energy-based fallback")
        boundary_times = _energy_based_segmentation(y, sr, duration, min_sections)

    # Ensure start and end
    if not boundary_times or boundary_times[0] > 2.0:
        boundary_times.insert(0, 0.0)
    if boundary_times[-1] < duration - 2.0:
        boundary_times.append(duration)

    # Remove duplicates and sort
    boundary_times = sorted(set(round(t, 2) for t in boundary_times))

    # Compute energy per section
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.times_like(rms, sr=sr)

    sections = []
    for i in range(len(boundary_times) - 1):
        start = boundary_times[i]
        end = boundary_times[i + 1]
        if end - start < 1.0:  # skip tiny sections
            continue

        mask = (rms_times >= start) & (rms_times < end)
        section_energy = float(np.mean(rms[mask])) if np.any(mask) else 0.0

        sections.append(
            SongSection(
                label="unknown",
                start_time=start,
                end_time=end,
                energy_level=section_energy,
            )
        )

    # Label sections
    sections = _label_sections(sections, duration, rec, features, sr)

    logger.info(f"Detected {len(sections)} sections: {[s.label for s in sections]}")
    return sections


def _energy_based_segmentation(
    y: np.ndarray, sr: int, duration: float, target_sections: int
) -> list[float]:
    """Segment based on RMS energy changes when novelty detection underperforms."""
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.times_like(rms, sr=sr)

    # Smooth the RMS curve
    window = max(5, len(rms) // 50)
    smoothed = np.convolve(rms, np.ones(window) / window, mode="same")

    # Find significant changes in energy (derivative peaks)
    diff = np.abs(np.diff(smoothed))
    diff_times = rms_times[:-1]

    # Find peaks in the energy derivative
    threshold = np.percentile(diff, 85)
    min_gap = duration / (target_sections * 2)  # minimum gap between boundaries

    boundaries = []
    for i in range(1, len(diff) - 1):
        if diff[i] > threshold and diff[i] > diff[i - 1] and diff[i] > diff[i + 1]:
            t = float(diff_times[i])
            if not boundaries or (t - boundaries[-1]) >= min_gap:
                boundaries.append(t)

    # If still too few, just evenly divide
    if len(boundaries) < target_sections - 1:
        section_len = duration / target_sections
        boundaries = [section_len * i for i in range(1, target_sections)]

    return boundaries


def _compute_novelty(rec_matrix: np.ndarray, kernel_size: int = 64) -> np.ndarray:
    """Compute a novelty curve from a recurrence matrix using a checkerboard kernel.

    This replaces librosa.segment.novelty which was removed in librosa 0.11.
    """
    n = rec_matrix.shape[0]
    half = kernel_size // 2
    novelty = np.zeros(n)

    for i in range(half, n - half):
        # Checkerboard kernel: compare top-left/bottom-right vs top-right/bottom-left
        tl = rec_matrix[i - half : i, i - half : i].mean()
        br = rec_matrix[i : i + half, i : i + half].mean()
        tr = rec_matrix[i - half : i, i : i + half].mean()
        bl = rec_matrix[i : i + half, i - half : i].mean()
        novelty[i] = max(0, (tl + br) / 2 - (tr + bl) / 2)

    return novelty


def _detect_boundaries(
    novelty: np.ndarray, min_section_frames: int = 40, peak_threshold: float = 0.3
) -> list[int]:
    """Find section boundaries from a novelty curve."""
    if len(novelty) == 0:
        return []

    max_nov = novelty.max()
    if max_nov == 0:
        return []

    threshold = peak_threshold * max_nov
    boundaries = []

    for i in range(1, len(novelty) - 1):
        if novelty[i] > threshold and novelty[i] > novelty[i - 1] and novelty[i] > novelty[i + 1]:
            if not boundaries or (i - boundaries[-1]) >= min_section_frames:
                boundaries.append(i)

    return boundaries


def _label_sections(
    sections: list[SongSection],
    duration: float,
    rec_matrix: np.ndarray,
    features: np.ndarray,
    sr: int,
) -> list[SongSection]:
    """Assign labels (verse, chorus, etc.) to detected sections.

    Uses heuristics based on energy, position, and feature similarity.
    """
    if not sections:
        return sections

    # Normalize energy across sections
    max_energy = max(s.energy_level for s in sections) or 1.0
    for s in sections:
        s.energy_level = s.energy_level / max_energy

    num_sections = len(sections)

    for i, section in enumerate(sections):
        position_ratio = section.start_time / duration

        # Position-based heuristics
        if position_ratio < 0.05 and section.duration < 15:
            section.label = "intro"
            section.confidence = 0.7
        elif position_ratio > 0.85 and section.duration < 20:
            section.label = "outro"
            section.confidence = 0.7
        elif section.energy_level > 0.7:
            section.label = "chorus"
            section.confidence = 0.6
        elif section.energy_level < 0.3:
            section.label = "bridge"
            section.confidence = 0.4
        else:
            section.label = "verse"
            section.confidence = 0.5

        # Short sections with low energy near beginning/end
        if section.duration < 5:
            section.label = "transition"
            section.confidence = 0.5

    # Second pass: look for repeating sections (similar energy = same type)
    _refine_labels_by_repetition(sections)

    return sections


def _refine_labels_by_repetition(sections: list[SongSection]) -> None:
    """Refine labels by looking for repeating energy patterns (AABA, etc.)."""
    if len(sections) < 4:
        return

    # Group sections by similar energy levels
    energy_levels = [s.energy_level for s in sections]
    high_energy = [i for i, e in enumerate(energy_levels) if e > 0.65]
    mid_energy = [i for i, e in enumerate(energy_levels) if 0.35 <= e <= 0.65]

    # If we see alternating high/mid patterns, refine to verse/chorus
    for i in high_energy:
        if sections[i].label not in ("intro", "outro", "transition"):
            sections[i].label = "chorus"
            sections[i].confidence = max(sections[i].confidence, 0.65)

    for i in mid_energy:
        if sections[i].label not in ("intro", "outro", "transition", "bridge"):
            sections[i].label = "verse"
            sections[i].confidence = max(sections[i].confidence, 0.55)
