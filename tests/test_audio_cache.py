from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

from xlights_mcp.audio import analyzer, beats, cache
from xlights_mcp.audio.separator import StemPaths
from xlights_mcp.config import AudioConfig


def test_core_cache_reuses_decode_but_refreshes_stems(tmp_path, monkeypatch):
    audio = tmp_path / "a.wav"
    sf.write(audio, np.zeros(2205), 22050)
    config = AudioConfig(cache_dir=tmp_path / "cache")
    loads = []
    stem_calls = []
    load = analyzer.librosa.load

    def counted(*args, **kwargs):
        loads.append(args[0])
        return load(*args, **kwargs)

    def stems(*args):
        stem_calls.append(args[0])
        return StemPaths(available=len(stem_calls) > 1)

    monkeypatch.setattr(analyzer.librosa, "load", counted)
    monkeypatch.setattr(analyzer, "separate_stems", stems)
    monkeypatch.setattr(
        analyzer, "analyze_stems", lambda *args, **kwargs: analyzer.StemAnalysis(available=True)
    )
    monkeypatch.setattr(beats, "_try_madmom_beats", lambda *args: None)
    first = analyzer.full_analysis(audio, config)
    renamed = tmp_path / "renamed.wav"
    renamed.write_bytes(audio.read_bytes())
    second = analyzer.full_analysis(renamed, config)
    assert len(loads) == 1
    assert len(stem_calls) == 2
    assert first.beats == second.beats
    assert second.file_path == str(renamed)
    assert second.file_name == "renamed.wav"
    assert not first.stem_analysis.available
    assert second.stem_analysis.available
    sf.write(audio, np.ones(2205) * 0.01, 22050)
    analyzer.full_analysis(audio, config)
    assert len(loads) == 2


def test_cache_key_includes_sample_rate_backend_and_version(tmp_path, monkeypatch):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"audio")
    first = cache.cache_key(audio, 22050)
    assert cache.cache_key(audio, 44100) != first
    monkeypatch.setattr(cache, "CACHE_VERSION", cache.CACHE_VERSION + 1)
    assert cache.cache_key(audio, 22050) != first
    changed = cache.cache_key(audio, 22050)
    monkeypatch.setattr(cache, "_dependency_versions", lambda: {"madmom": "test-version"})
    assert cache.cache_key(audio, 22050) != changed


@pytest.mark.parametrize(
    "payload",
    [
        '{"beats":',
        '{"beats": 7}',
        "null",
        '{"beats":{"tempo":NaN},"spectrum":{},"sections":[]}',
    ],
)
def test_corrupt_or_invalid_cache_is_reported(tmp_path, caplog, payload):
    path = tmp_path / f"analysis-v{cache.CACHE_VERSION}-key.json"
    path.write_text(payload)
    assert cache.load_core(tmp_path, "key") is None
    assert "recomputing" in caplog.text


def test_cache_io_failure_is_logged_not_hidden(tmp_path, caplog):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("unchanged")
    analysis = cache.CoreAnalysis(
        beats=beats.BeatMap(), spectrum=analyzer.SpectrumAnalysis(), sections=[]
    )
    cache.save_core(blocker, "key", analysis)
    assert blocker.read_text() == "unchanged"
    assert "Cannot persist" in caplog.text


def test_transient_hpss_failure_is_not_persisted(tmp_path, monkeypatch):
    audio = tmp_path / "a.wav"
    sf.write(audio, np.zeros(2205), 22050)
    monkeypatch.setattr(analyzer, "separate_stems", lambda *args: StemPaths())
    monkeypatch.setattr(beats, "_try_madmom_beats", lambda *args: None)

    def fail(*args, **kwargs):
        raise ValueError("temporary")

    monkeypatch.setattr(beats.librosa.decompose, "hpss", fail)
    result = analyzer.full_analysis(audio, AudioConfig(cache_dir=tmp_path / "cache"))
    assert result.beats.warnings
    assert not list((tmp_path / "cache").glob("*.json"))
