from __future__ import annotations

import sys
from types import ModuleType

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
            return [[0.5, 1], [1.0, 2], [1.5, 1]]

    downbeats.RNNDownBeatProcessor = RNNDownBeatProcessor
    downbeats.DBNDownBeatTrackingProcessor = DBNDownBeatTrackingProcessor
    monkeypatch.setitem(sys.modules, "madmom", ModuleType("madmom"))
    monkeypatch.setitem(sys.modules, "madmom.features", ModuleType("madmom.features"))
    monkeypatch.setitem(sys.modules, "madmom.features.downbeats", downbeats)

    assert _try_madmom_downbeats(tmp_path / "song.wav") == [0.5, 1.5]


def test_madmom_downbeats_fall_back_when_not_installed(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "madmom", None)

    assert _try_madmom_downbeats(tmp_path / "song.wav") == []
