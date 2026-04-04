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
    """Detect song structure (verse/chorus/bridge/etc.) using self-similarity.

    Uses MFCCs and chroma features to build a self-similarity matrix,
    then applies change-point detection to find section boundaries.
    Labels are assigned based on energy, repetition, and position.
    """
    logger.info(f"Analyzing song structure: {audio_path}")
    y, sr = librosa.load(str(audio_path), sr=sr, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)

    # Extract features for structure analysis
    # MFCCs capture timbral characteristics
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)

    # Chroma captures harmonic/pitch content
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

    # Combine features
    features = np.vstack([mfcc, chroma])

    # Build self-similarity matrix
    rec = librosa.segment.recurrence_matrix(
        features, mode="affinity", sym=True, bandwidth=1.0
    )

    # Detect boundaries using novelty curve
    novelty = librosa.segment.novelty(rec)
    boundary_frames = _detect_boundaries(novelty, min_section_frames=40)

    # Convert to times
    boundary_times = librosa.frames_to_time(boundary_frames, sr=sr).tolist()

    # Ensure we have start and end
    if not boundary_times or boundary_times[0] > 1.0:
        boundary_times.insert(0, 0.0)
    if boundary_times[-1] < duration - 2.0:
        boundary_times.append(duration)

    # Compute energy per section for labeling
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.times_like(rms, sr=sr)

    sections = []
    for i in range(len(boundary_times) - 1):
        start = boundary_times[i]
        end = boundary_times[i + 1]

        # Get average energy for this section
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

    # Label sections based on energy, position, and repetition
    sections = _label_sections(sections, duration, rec, features, sr)

    logger.info(f"Detected {len(sections)} sections: {[s.label for s in sections]}")
    return sections


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
