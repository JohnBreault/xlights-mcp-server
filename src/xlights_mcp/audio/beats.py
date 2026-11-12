"""Beat and tempo detection for music files."""

from __future__ import annotations

import logging
from pathlib import Path

import librosa
import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BeatMap(BaseModel):
    """Beat analysis results for a song."""

    tempo: float = 0.0  # BPM
    beat_times: list[float] = Field(default_factory=list)  # seconds
    downbeat_times: list[float] = Field(default_factory=list)  # bar start times
    onset_times: list[float] = Field(default_factory=list)  # note onset times
    beats_per_bar: int = 4

    @property
    def beat_times_ms(self) -> list[int]:
        """Beat times in milliseconds (xLights native unit)."""
        return [int(t * 1000) for t in self.beat_times]

    @property
    def downbeat_times_ms(self) -> list[int]:
        """Downbeat times in milliseconds."""
        return [int(t * 1000) for t in self.downbeat_times]

    @property
    def onset_times_ms(self) -> list[int]:
        """Onset times in milliseconds."""
        return [int(t * 1000) for t in self.onset_times]


def detect_beats(audio_path: Path, sr: int = 22050) -> BeatMap:
    """Detect beats, downbeats, and onsets in an audio file.

    Uses librosa for beat tracking and onset detection.
    Falls back gracefully if madmom is not available.
    """
    logger.info(f"Analyzing beats: {audio_path}")
    y, sr = librosa.load(str(audio_path), sr=sr, mono=True)

    # Beat tracking
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()

    # Extract scalar tempo
    tempo_val = float(tempo) if np.isscalar(tempo) else float(tempo[0])

    # Onset detection
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr).tolist()

    # Estimate downbeats (every 4 beats by default)
    downbeat_times = []
    if beat_times:
        for i in range(0, len(beat_times), 4):
            downbeat_times.append(beat_times[i])

    # Try madmom for better beat detection if available
    beat_times_madmom, downbeat_times_madmom, beats_per_bar = _try_madmom_downbeats(audio_path)
    if beat_times_madmom:
        beat_times = beat_times_madmom
        downbeat_times = downbeat_times_madmom
        if len(beat_times) > 1:
            tempo_val = 60.0 / float(np.median(np.diff(beat_times)))
    else:
        beats_per_bar = 4

    logger.info(
        f"Detected: tempo={tempo_val:.1f} BPM, "
        f"{len(beat_times)} beats, "
        f"{len(downbeat_times)} downbeats, "
        f"{len(onset_times)} onsets"
    )

    return BeatMap(
        tempo=tempo_val,
        beat_times=beat_times,
        downbeat_times=downbeat_times,
        onset_times=onset_times,
        beats_per_bar=beats_per_bar,
    )


def _try_madmom_downbeats(audio_path: Path) -> tuple[list[float], list[float], int]:
    """Attempt to use madmom for more accurate downbeat detection."""
    try:
        from madmom.features.downbeats import DBNDownBeatTrackingProcessor, RNNDownBeatProcessor

        logger.info("Using madmom for downbeat detection")
        act = RNNDownBeatProcessor()(str(audio_path))
        result = DBNDownBeatTrackingProcessor(
            beats_per_bar=[3, 4], num_tempi=12, fps=100
        )(act)

        # result is array of [time, beat_position]
        # downbeats are where beat_position == 1
        beat_times = [float(row[0]) for row in result]
        downbeats = [float(row[0]) for row in result if int(row[1]) == 1]
        beat_positions = [int(row[1]) for row in result]
        beats_per_bar = max(beat_positions, default=4)
        logger.info(f"Madmom detected {len(downbeats)} downbeats")
        return beat_times, downbeats, beats_per_bar
    except ImportError:
        logger.debug("madmom not installed, using librosa-only downbeat estimation")
        return [], [], 4
    except Exception as e:
        logger.warning(f"madmom downbeat detection failed: {e}")
        return [], [], 4
