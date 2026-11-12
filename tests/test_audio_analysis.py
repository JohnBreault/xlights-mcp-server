"""Deterministic signals exercise analysis rather than external audio/model files."""

from __future__ import annotations

import sys
from itertools import pairwise
from pathlib import Path
from types import ModuleType

import librosa
import numpy as np
import pytest
import soundfile as sf
from lxml import etree

from xlights_mcp.audio import analyzer, beats, spectrum, structure
from xlights_mcp.audio.separator import StemPaths
from xlights_mcp.config import AudioConfig
from xlights_mcp.sequencer import engine
from xlights_mcp.xlights.models import LightModel, ShowConfig

SR = 22050


def _clicks(duration: float, times: np.ndarray) -> np.ndarray:
    signal = np.zeros(round(duration * SR))
    for time in times:
        start = round(float(time) * SR)
        length = min(round(0.06 * SR), len(signal) - start)
        if length > 0:
            signal[start : start + length] += np.random.default_rng(start).normal(
                0, 0.3, length
            ) * np.exp(-np.linspace(0, 8, length))
    return signal


@pytest.mark.parametrize(
    ("pattern", "meter", "phase"),
    [([1.0, 0.1, 0.4, 0.1], 4, 0), ([0.2, 1.0, 0.1], 3, 1)],
)
def test_meter_and_phase_follow_accents(pattern, meter, phase):
    detected, offset, confidence = beats._meter_and_phase(np.tile(pattern, 10))
    assert (detected, offset) == (meter, phase)
    assert confidence > 0.5


@pytest.mark.parametrize("strengths", [np.ones(30), np.zeros(0), np.arange(4)])
def test_meter_is_conservative_without_repeated_evidence(strengths):
    assert beats._meter_and_phase(strengths) == (4, 0, 0.0)


def test_two_and_four_beat_ambiguity_keeps_default_meter():
    assert beats._meter_and_phase(np.tile([1.0, 0.2], 12)) == (4, 0, 0.0)


def test_click_track_beats_and_onsets(tmp_path, monkeypatch):
    monkeypatch.setattr(beats, "_try_madmom_beats", lambda *args: None)
    hits = np.arange(1, 13, 0.5)
    path = tmp_path / "clicks.wav"
    sf.write(path, _clicks(14, hits), SR)
    result = beats.detect_beats(path)
    assert abs(result.tempo - 120) < 5
    assert len(result.beat_times) >= 20
    assert max(min(abs(np.asarray(result.onset_times) - t)) for t in hits) <= 0.03
    assert result.downbeat_times == result.beat_times[::4]
    assert all(0 <= t < 14 for t in result.beat_times + result.onset_times)
    assert len(result.tempo_curve) >= 2
    assert not result.tempo_changes


def test_tempo_windows_measure_change_and_cover_tail():
    # Known onset envelopes isolate tempo estimation from onset extraction.
    sr = beats.HOP_LENGTH * 50
    envelope = np.zeros(50 * 30 + 1)
    envelope[np.arange(25, 50 * 15, 25)] = 1
    envelope[np.arange(50 * 15, len(envelope), 20)] = 1
    curve = beats._tempo_windows(envelope, sr, 30)
    assert abs(curve[0].tempo - 120) < 5
    assert abs(curve[-1].tempo - 150) < 5
    assert curve[-1].time == pytest.approx((len(envelope) - 500) / 50)


def test_hpss_failure_uses_full_mix_and_reports_it(monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("separation failed")

    y = _clicks(2, np.array([0.5, 1.0]))
    magnitude = abs(librosa.stft(y))
    monkeypatch.setattr(librosa.decompose, "hpss", fail)
    warnings = []
    onset, chroma = beats._prepare_rhythm(y, SR, magnitude, warnings)
    np.testing.assert_allclose(onset, librosa.onset.onset_strength(y=y, sr=SR))
    assert chroma.shape[0] == 12
    assert "HPSS failed" in warnings[0]


@pytest.mark.parametrize("invalid", [False, True])
def test_optional_madmom_grid_is_coherent_or_falls_back(monkeypatch, invalid):
    module = ModuleType("madmom.features.downbeats")
    grid = np.column_stack((np.arange(0.5, 6, 0.5), np.tile([1, 2, 3], 4)[:11]))
    if invalid:
        grid[1, 0] = np.nan
    module.RNNDownBeatProcessor = lambda: lambda path: np.zeros((1, 2))
    module.DBNDownBeatTrackingProcessor = lambda **kwargs: lambda activations: grid
    for name in ("madmom", "madmom.features"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    monkeypatch.setitem(sys.modules, "madmom.features.downbeats", module)
    warnings = []
    result = beats._try_madmom_beats(Path("unused.wav"), warnings)
    if invalid:
        assert result is None
        assert warnings
    else:
        assert result == (grid[:, 0].tolist(), grid[grid[:, 1] == 1, 0].tolist(), 3)
        assert not warnings


def test_spectral_descriptors_flux_and_energy():
    times = np.arange(3 * SR) / SR
    y = np.sin(2 * np.pi * 1000 * times) * np.where(times < 1.5, 0.1, 0.8)
    result = spectrum._analyze_spectrum(y, SR)
    count = len(result.rms_times)
    for values in (
        result.spectral_flux,
        result.spectral_centroid,
        result.spectral_bandwidth,
        result.spectral_rolloff,
        result.spectral_flatness,
        result.energy_short,
        result.energy_medium,
        result.energy_long,
    ):
        assert len(values) == count
        assert np.isfinite(values).all()
    assert np.median(result.spectral_centroid[5:-5]) == pytest.approx(1000, abs=20)
    assert result.dynamic_range > 1
    assert result.energy_short[20] < result.energy_short[-20]
    assert np.var(result.energy_long) < np.var(result.rms_energy)
    assert result.rms_times[int(np.argmax(result.spectral_flux))] == pytest.approx(1.5, abs=0.05)


@pytest.mark.parametrize("frequency", [100, 1000, 6000])
def test_band_peaks_follow_tone_attacks(frequency):
    times = np.arange(3 * SR) / SR
    envelope = np.exp(-(((times - 1.5) / 0.08) ** 2))
    result = spectrum._analyze_spectrum(np.sin(2 * np.pi * frequency * times) * envelope, SR)
    band = next(
        band for band in result.bands if band.freq_range[0] <= frequency < band.freq_range[1]
    )
    assert min(abs(t - 1.5) for t in band.peak_times) < 0.06
    detailed = spectrum._analyze_spectrum(
        np.sin(2 * np.pi * frequency * times) * envelope, SR, use_simple_bands=False
    )
    assert len(detailed.bands) > len(result.bands)


@pytest.mark.parametrize("length", [1, 100, SR])
def test_short_silence_has_finite_aligned_energy(length):
    result = spectrum._analyze_spectrum(np.zeros(length), SR)
    assert not any(result.rms_energy)
    assert not any(result.spectral_flux)
    assert len(result.energy_long) == len(result.rms_times)
    assert all(0 <= t <= length / SR for t in result.rms_times)
    assert result.dynamic_range == 0


def test_low_sample_rate_omits_empty_bands():
    result = spectrum._analyze_spectrum(np.zeros(4000), 4000)
    assert [band.name for band in result.bands] == ["bass", "mids"]


def test_checkerboard_novelty_detects_feature_transition():
    features = np.zeros((2, 40))
    features[0, :20] = 1
    features[1, 20:] = 1
    novelty = structure._novelty(features)
    assert int(np.argmax(novelty)) == 20
    assert not structure._novelty(np.ones((2, 40))).any()


def test_novelty_matches_checkerboard_without_quadratic_storage():
    features = np.random.default_rng(42).normal(size=(5, 32))
    similarity = features.T @ features
    expected = np.zeros(32)
    for i in range(4, 29):
        expected[i] = (
            similarity[i - 4 : i, i - 4 : i].mean()
            + similarity[i : i + 4, i : i + 4].mean()
            - 2 * similarity[i - 4 : i, i : i + 4].mean()
        )
    expected /= expected.max()
    np.testing.assert_allclose(structure._novelty(features), expected, atol=1e-12)
    # A long beat sequence remains a feature-by-time operation, not an N x N matrix.
    long = np.ones((5, 20000))
    assert not structure._novelty(long).any()


def test_structure_tracks_timbre_changes_and_covers_timeline():
    duration = 32
    times = np.arange(SR * duration) / SR
    frequencies = np.where((times < 8) | ((times >= 16) & (times < 24)), 220, 880)
    y = 0.15 * np.sin(2 * np.pi * np.cumsum(frequencies) / SR)
    y += _clicks(duration, np.arange(0.5, duration, 0.5))
    magnitude = abs(librosa.stft(y))
    rms = librosa.feature.rms(y=y)[0]
    chroma = librosa.feature.chroma_stft(S=magnitude**2, sr=SR, tuning=0)
    grid = beats.BeatMap(tempo=120, beat_times=np.arange(0.5, duration, 0.5).tolist())
    sections = structure._analyze_structure(y, SR, grid, magnitude, rms, chroma)
    boundaries = [section.start_time for section in sections] + [sections[-1].end_time]
    assert boundaries[0] == 0
    assert boundaries[-1] == duration
    for transition in (8, 16, 24):
        assert min(abs(t - transition) for t in boundaries) <= 1
    assert all(a.end_time == b.start_time for a, b in pairwise(sections))
    assert all(section.end_time > section.start_time for section in sections)


def test_silent_structure_is_one_unknown_section():
    y = np.zeros(SR)
    magnitude = abs(librosa.stft(y))
    result = structure._analyze_structure(
        y,
        SR,
        beats.BeatMap(),
        magnitude,
        librosa.feature.rms(y=y)[0],
        np.zeros((12, magnitude.shape[1])),
    )
    assert [section.model_dump() for section in result] == [
        {
            "label": "unknown",
            "start_time": 0.0,
            "end_time": 1.0,
            "energy_level": 0.0,
            "confidence": 0.0,
        }
    ]


def test_analysis_drives_parseable_non_overwriting_sequence(tmp_path, monkeypatch):
    path = tmp_path / "song.wav"
    sf.write(path, _clicks(12, np.arange(1, 11, 0.5)), SR)
    monkeypatch.setattr(analyzer, "separate_stems", lambda *args: StemPaths())
    monkeypatch.setattr(beats, "_try_madmom_beats", lambda *args: None)
    analysis = analyzer.full_analysis(path, AudioConfig(cache_dir=tmp_path / "cache"))
    show = ShowConfig(
        show_path=str(tmp_path),
        show_name="test",
        models=[LightModel(name="Arch", display_as="Arches", pixel_count=50)],
    )
    specs = []
    real_writer = engine.write_xsq

    def capture(spec, *args, **kwargs):
        specs.append(spec)
        return real_writer(spec, *args, **kwargs)

    monkeypatch.setattr(engine, "write_xsq", capture)
    for _ in range(2):
        result = engine._generate_auto(analysis, show, path, None, "christmas")
        assert "error" not in result
    outputs = sorted(tmp_path.glob("*.xsq"))
    assert len(outputs) == 2
    for output in outputs:
        etree.parse(str(output))
    assert all(
        0 <= effect.start_time_ms < effect.end_time_ms <= analysis.duration_ms
        for spec in specs
        for effect in spec.effects
    )
    for i, section in enumerate(analysis.sections):
        assert engine._precompute_section_beats(analysis)[i] == [
            t for t in analysis.beats.beat_times if section.start_time <= t < section.end_time
        ]
    assert specs[0].effects
    motion = [effect for effect in specs[0].effects if effect.layer == 1]
    assert motion
    section_bars = engine._precompute_section_downbeats(analysis)
    expected_motion_spans = {
        (int(start * 1000), int(end * 1000))
        for i, section in enumerate(analysis.sections)
        for start, end in (
            pairwise(section_bars[i])
            if len(section_bars[i]) >= 2
            else [(section.start_time, section.end_time)]
        )
    }
    assert {
        (effect.start_time_ms, effect.end_time_ms) for effect in motion
    } == expected_motion_spans


def test_legacy_models_accept_missing_new_fields():
    assert beats.BeatMap.model_validate({"tempo": 120, "beat_times": [0.5]}).tempo_curve == []
    assert spectrum.SpectrumAnalysis.model_validate({"rms_energy": [1]}).energy_long == []
    with pytest.raises(ValueError, match="finite samples"):
        beats._validate_audio(np.array([np.nan]), SR)
    with pytest.raises(ValueError, match="finite samples"):
        beats._validate_audio(np.array([]), SR)
