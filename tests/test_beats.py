from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import numpy as np

from xlights_mcp.audio import beats
from xlights_mcp.audio.beats import _try_madmom_beats


def test_madmom_detects_three_beats_per_bar_in_short_clip(tmp_path, monkeypatch):
    # Arrange
    downbeats = ModuleType("madmom.features.downbeats")

    class RNNDownBeatProcessor:
        def __call__(self, path):
            assert path == str(tmp_path / "song.wav")
            return "activations"

    class DBNDownBeatTrackingProcessor:
        def __init__(self, beats_per_bar, num_tempi, fps):
            assert beats_per_bar == [3, 4]
            assert num_tempi == 12
            assert fps == 100

        def __call__(self, activations):
            assert activations == "activations"
            return np.array([[0.5, 1], [1.0, 2], [1.5, 3]])

    downbeats.RNNDownBeatProcessor = RNNDownBeatProcessor
    downbeats.DBNDownBeatTrackingProcessor = DBNDownBeatTrackingProcessor
    monkeypatch.setitem(sys.modules, "madmom", ModuleType("madmom"))
    monkeypatch.setitem(sys.modules, "madmom.features", ModuleType("madmom.features"))
    monkeypatch.setitem(sys.modules, "madmom.features.downbeats", downbeats)

    # Act
    result = _try_madmom_beats(tmp_path / "song.wav")

    # Assert
    assert result == (
        [0.5, 1.0, 1.5],
        [0.5],
        3,
    )


def test_madmom_downbeats_fall_back_when_not_installed(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setitem(sys.modules, "madmom", None)

    # Act
    result = _try_madmom_beats(tmp_path / "song.wav")

    # Assert
    assert result is None


def test_detect_beats_propagates_three_beats_per_bar(tmp_path, monkeypatch):
    # Arrange
    librosa_stub = SimpleNamespace(
        load=lambda path, sr, mono: (np.zeros(sr * 3), sr),
        stft=lambda y, **kwargs: np.zeros((1025, 4)),
        onset=SimpleNamespace(
            onset_detect=lambda **kwargs: np.array([1]),
        ),
        beat=SimpleNamespace(beat_track=lambda **kwargs: (120.0, np.array([1, 2, 3]))),
        frames_to_time=lambda frames, sr, hop_length: np.asarray(frames) * hop_length / sr,
    )
    monkeypatch.setattr(beats, "librosa", librosa_stub)
    monkeypatch.setattr(
        beats, "_prepare_rhythm", lambda *args: (np.zeros(4), np.zeros((12, 4)))
    )
    monkeypatch.setattr(
        beats,
        "_try_madmom_beats",
        lambda *args: ([0.5, 1.0, 1.5, 2.0], [0.5, 2.0], 3),
    )

    # Act
    result = beats.detect_beats(tmp_path / "song.wav")

    # Assert
    assert result.beat_times == [0.5, 1.0, 1.5, 2.0]
    assert result.downbeat_times == [0.5, 2.0]
    assert result.tempo == 120.0
    assert result.beats_per_bar == 3
    assert result.rhythm_method == "madmom"
