from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import numpy as np

import xlights_mcp.audio.beats as beats
from xlights_mcp.audio.beats import _try_madmom_downbeats


def test_madmom_downbeats_use_supported_time_signatures(tmp_path, monkeypatch):
    downbeats = ModuleType("madmom.features.downbeats")

    class RNNDownBeatProcessor:
        def __call__(self, path):
            assert path == str(tmp_path / "song.wav")
            return "activations"

    class DBNDownBeatTrackingProcessor:
        def __init__(self, beats_per_bar, fps):
            assert beats_per_bar == [3, 4]
            assert fps == 100

        def __call__(self, activations):
            assert activations == "activations"
            return [[0.5, 1], [1.0, 2], [1.5, 3], [2.0, 1], [2.5, 2], [3.0, 3]]

    downbeats.RNNDownBeatProcessor = RNNDownBeatProcessor
    downbeats.DBNDownBeatTrackingProcessor = DBNDownBeatTrackingProcessor
    monkeypatch.setitem(sys.modules, "madmom", ModuleType("madmom"))
    monkeypatch.setitem(sys.modules, "madmom.features", ModuleType("madmom.features"))
    monkeypatch.setitem(sys.modules, "madmom.features.downbeats", downbeats)

    assert _try_madmom_downbeats(tmp_path / "song.wav") == (
        [0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
        [0.5, 2.0],
        3,
    )


def test_madmom_downbeats_fall_back_when_not_installed(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "madmom", None)

    assert _try_madmom_downbeats(tmp_path / "song.wav") == ([], [], 4)


def test_detect_beats_propagates_three_beats_per_bar(tmp_path, monkeypatch):
    librosa_stub = SimpleNamespace(
        load=lambda path, sr, mono: (np.array([0.0]), sr),
        onset=SimpleNamespace(
            onset_strength=lambda y, sr: np.array([0.0]),
            onset_detect=lambda onset_envelope, sr: np.array([1]),
        ),
        beat=SimpleNamespace(beat_track=lambda onset_envelope, sr: (120.0, np.array([1, 2, 3]))),
        frames_to_time=lambda frames, sr: np.asarray(frames, dtype=float) / sr,
    )
    monkeypatch.setattr(beats, "librosa", librosa_stub)
    monkeypatch.setattr(
        beats,
        "_try_madmom_downbeats",
        lambda path: ([0.5, 1.0, 1.5, 2.0], [0.5, 2.0], 3),
    )

    result = beats.detect_beats(tmp_path / "song.wav")

    assert result.beat_times == [0.5, 1.0, 1.5, 2.0]
    assert result.downbeat_times == [0.5, 2.0]
    assert result.tempo == 120.0
    assert result.beats_per_bar == 3
