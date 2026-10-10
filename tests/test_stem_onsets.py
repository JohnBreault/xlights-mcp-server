"""Stem onset times must mark when a hit sounds, not the quiet before it."""

from __future__ import annotations

import numpy as np
import soundfile as sf

from xlights_mcp.audio.analyzer import analyze_stems
from xlights_mcp.audio.separator import StemPaths

SR = 22050
HITS = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]


def test_drum_onsets_land_on_hits(tmp_path):
    rng = np.random.default_rng(0)
    y = rng.normal(0, 0.002, int(4.5 * SR))  # low noise floor
    for t in HITS:
        i = int(t * SR)
        n = int(0.08 * SR)
        y[i : i + n] += rng.normal(0, 0.5, n) * np.exp(-np.linspace(0, 8, n))
    path = tmp_path / "drums.wav"
    sf.write(path, y, SR)

    stems = analyze_stems(StemPaths(drums=str(path), available=True), sr=SR)
    onsets = np.array(stems.stems["drums"].onset_times)

    errors = [float(np.min(np.abs(onsets - t))) for t in HITS]
    # one analysis frame is ~23 ms; backtracking shifts detections ~2 frames early
    assert max(errors) <= 0.03, errors
