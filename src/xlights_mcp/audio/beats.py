"""Beat and tempo detection for music files."""

from __future__ import annotations

import logging
from itertools import pairwise
from pathlib import Path

import librosa
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class TempoPoint(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    time: float
    tempo: float
    beat_count: int = 0


class TempoChange(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    time: float
    from_tempo: float
    to_tempo: float


class BeatMap(BaseModel):
    """Beat analysis results for a song."""

    model_config = ConfigDict(allow_inf_nan=False)

    tempo: float = 0.0  # BPM
    beat_times: list[float] = Field(default_factory=list)  # seconds
    downbeat_times: list[float] = Field(default_factory=list)  # bar start times
    onset_times: list[float] = Field(default_factory=list)  # note onset times
    beats_per_bar: int = 4
    meter_confidence: float = 0.0
    downbeat_confidence: float = 0.0
    rhythm_method: str = "librosa"
    tempo_curve: list[TempoPoint] = Field(default_factory=list)
    tempo_changes: list[TempoChange] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

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


HOP_LENGTH = 512
FRAME_LENGTH = 2048


def detect_beats(audio_path: Path, sr: int = 22050) -> BeatMap:
    """Detect beats, downbeats, and onsets in an audio file.

    Uses librosa for beat tracking and onset detection.
    Falls back gracefully if madmom is not available.
    """
    logger.info(f"Analyzing beats: {audio_path}")
    y, sr = librosa.load(str(audio_path), sr=sr, mono=True)

    _validate_audio(y, sr)
    magnitude = np.abs(librosa.stft(y, n_fft=FRAME_LENGTH, hop_length=HOP_LENGTH))
    diagnostics: list[str] = []
    onset_env, chroma = _prepare_rhythm(y, sr, magnitude, diagnostics)
    return _analyze_beats(y, sr, onset_env, chroma, audio_path, diagnostics)


def _validate_audio(y: np.ndarray, sr: int) -> None:
    if sr <= 0 or y.size == 0 or not np.isfinite(y).all():
        raise ValueError("Audio must contain finite samples at a positive sample rate")


def _prepare_rhythm(
    y: np.ndarray, sr: int, magnitude: np.ndarray, diagnostics: list[str] | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Prepare standard librosa features, sharing the full-mix STFT."""
    onset = None
    harmonic = magnitude
    try:
        harmonic, percussive = librosa.decompose.hpss(magnitude)
        mel = librosa.feature.melspectrogram(
            S=percussive**2, sr=sr, n_fft=FRAME_LENGTH, hop_length=HOP_LENGTH
        )
        onset = librosa.onset.onset_strength(
            S=librosa.power_to_db(mel), sr=sr, hop_length=HOP_LENGTH
        )
        if not np.any(onset > 0):
            logger.info("No percussive onset evidence; using full-mix onset envelope")
            onset = None
    except (ValueError, RuntimeError) as exc:
        logger.warning("HPSS unavailable; using full-mix rhythm features: %s", exc)
        harmonic = magnitude
        if diagnostics is not None:
            diagnostics.append(f"HPSS failed; full-mix fallback: {exc}")
        onset = None
    if onset is None:
        onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP_LENGTH)
    chroma = librosa.feature.chroma_stft(
        S=harmonic**2, sr=sr, n_fft=FRAME_LENGTH, hop_length=HOP_LENGTH, tuning=0.0
    )
    return onset, chroma


def _meter_and_phase(strengths: np.ndarray) -> tuple[int, int, float]:
    """Fit periodic accent patterns; ambiguous evidence retains four-beat bars."""
    if strengths.size < 12 or float(np.std(strengths)) < 1e-6:
        return 4, 0, 0.0
    centered = strengths - strengths.mean()
    variance = float(np.mean(centered**2))
    scores = {}
    phases = {}
    for meter in (2, 3, 4):
        # Complete bars avoid privileging a phase with an extra pickup beat.
        bars = centered[: len(centered) // meter * meter].reshape(-1, meter)
        profile = bars.mean(axis=0)
        repeat_error = float(np.mean((bars - profile) ** 2))
        scores[meter] = max(0.0, 1.0 - repeat_error / variance)
        phases[meter] = int(np.argmax(profile))
    best = max(scores, key=lambda meter: scores[meter])
    if scores[best] < 0.5 or scores[best] - scores[4] < 0.1:
        best = 4
    confidence = scores[best] if scores[best] >= 0.5 else 0.0
    if best == 4 and abs(scores[4] - scores[2]) < 0.1:
        # Alternating accents cannot distinguish two-beat from four-beat bars.
        confidence = 0.0
    return best, phases[best] if confidence else 0, confidence


def _tempo_windows(onset: np.ndarray, sr: int, duration: float) -> list[TempoPoint]:
    window = max(1, round(10 * sr / HOP_LENGTH))
    last = max(0, len(onset) - window)
    starts = sorted({*range(0, last + 1, max(1, window // 2)), last})
    points = []
    for start in starts:
        envelope = onset[start : start + window]
        beat_count = 0
        if not np.any(envelope > 0):
            value = 0.0
        else:
            tempo, frames = librosa.beat.beat_track(
                onset_envelope=envelope, sr=sr, hop_length=HOP_LENGTH
            )
            beat_count = len(frames)
            value = float(np.asarray(tempo).item()) if beat_count >= 2 else 0.0
        points.append(
            TempoPoint(
                time=min(start * HOP_LENGTH / sr, duration), tempo=value, beat_count=beat_count
            )
        )
    return points


def _analyze_beats(
    y: np.ndarray,
    sr: int,
    onset_env: np.ndarray,
    chroma: np.ndarray,
    audio_path: Path,
    diagnostics: list[str] | None = None,
) -> BeatMap:
    duration = len(y) / sr
    tempo, frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, hop_length=HOP_LENGTH)
    frames = frames[frames * HOP_LENGTH / sr < duration]
    tempo_val = float(np.asarray(tempo).item())
    beat_times = librosa.frames_to_time(frames, sr=sr, hop_length=HOP_LENGTH).tolist()
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, hop_length=HOP_LENGTH, backtrack=False
    )
    onset_times = [
        float(t)
        for t in librosa.frames_to_time(onset_frames, sr=sr, hop_length=HOP_LENGTH)
        if t < duration
    ]
    strengths = np.array([onset_env[max(0, f - 1) : f + 2].max() for f in frames], dtype=float)
    meter, phase, confidence = _meter_and_phase(strengths)
    phase_confidence = confidence
    if confidence and len(frames) >= 2 * meter:
        c = chroma[:, np.minimum(frames, chroma.shape[1] - 1)]
        c = librosa.util.normalize(c, axis=0)
        changes = np.r_[0.0, np.linalg.norm(np.diff(c, axis=1), axis=0)]
        # Harmonic changes break accent ties, never override clear accent evidence.
        accent = strengths / max(float(strengths.max()), 1e-8)
        evidence = accent + changes / max(float(changes.max()), 1e-8) * 0.1
        phase = max(range(meter), key=lambda p: float(np.mean(evidence[p::meter])))
    downbeat_times = beat_times[phase::meter]
    method = "librosa"
    warnings = list(diagnostics or [])
    enhanced = _try_madmom_beats(audio_path, warnings)
    if enhanced is not None:
        selected_beats, selected_downbeats, meter = enhanced
        beat_times = [t for t in selected_beats if 0 <= t < duration]
        downbeat_times = [t for t in selected_downbeats if 0 <= t < duration]
        if len(beat_times) > 1:
            tempo_val = float(60 / np.median(np.diff(beat_times)))
        method = "madmom"
        # Model output is not a calibrated probability.
        confidence = phase_confidence = 0.0
    curve = _tempo_windows(onset_env, sr, duration)
    changes = [
        TempoChange(time=b.time, from_tempo=a.tempo, to_tempo=b.tempo)
        for a, b in pairwise(curve)
        if a.tempo > 0 and b.tempo > 0 and abs(b.tempo / a.tempo - 1) > 0.1
    ]
    return BeatMap(
        tempo=tempo_val,
        beat_times=beat_times,
        downbeat_times=downbeat_times,
        onset_times=onset_times,
        beats_per_bar=meter,
        meter_confidence=confidence,
        downbeat_confidence=phase_confidence,
        rhythm_method=method,
        tempo_curve=curve,
        tempo_changes=changes,
        warnings=warnings,
    )


def _try_madmom_beats(
    audio_path: Path, diagnostics: list[str] | None = None
) -> tuple[list[float], list[float], int] | None:
    """Select a complete optional model grid, not downbeats from a different grid."""
    try:
        from madmom.features.downbeats import DBNDownBeatTrackingProcessor, RNNDownBeatProcessor

        logger.info("Using madmom for downbeat detection")
        act = RNNDownBeatProcessor()(str(audio_path))
        result = DBNDownBeatTrackingProcessor(beats_per_bar=[3, 4], num_tempi=12, fps=100)(act)
        if (
            result.ndim != 2
            or result.shape[1] != 2
            or not np.isfinite(result).all()
            or np.any(np.diff(result[:, 0]) <= 0)
        ):
            raise ValueError("Invalid madmom beat grid")
        downbeats = [float(row[0]) for row in result if int(row[1]) == 1]
        if not downbeats:
            logger.warning("madmom returned no downbeats; retaining librosa grid")
            if diagnostics is not None:
                diagnostics.append("madmom returned no downbeats; retaining librosa grid")
            return None
        return [float(row[0]) for row in result], downbeats, int(result[:, 1].max())
    except ImportError as exc:
        if exc.name == "madmom":
            logger.debug("madmom not installed, using librosa-only downbeat estimation")
        else:
            logger.warning("madmom import failed; using librosa: %s", exc)
            if diagnostics is not None:
                diagnostics.append(f"madmom import failed; librosa fallback: {exc}")
        return None
    except Exception as e:
        logger.warning("madmom downbeat detection failed: %s", e, exc_info=True)
        if diagnostics is not None:
            diagnostics.append(f"madmom failed; librosa fallback: {e}")
        return None
