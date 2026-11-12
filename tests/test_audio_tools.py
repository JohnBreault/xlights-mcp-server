from __future__ import annotations

import inspect

import pytest

from xlights_mcp import server
from xlights_mcp.audio import analyzer, beats, spectrum, structure
from xlights_mcp.config import AudioConfig, ServerConfig

TOOLS = ["analyze_song", "get_beat_map", "get_energy_profile", "get_song_structure"]


async def test_audio_tool_registration_and_signatures():
    registered = {tool.name: tool for tool in await server.mcp.list_tools()}
    for name in TOOLS:
        assert list(inspect.signature(getattr(server, name)).parameters) == ["mp3_path"]
        assert registered[name].inputSchema["required"] == ["mp3_path"]


@pytest.mark.parametrize("name", TOOLS)
def test_missing_audio_returns_error(name, tmp_path):
    assert "error" in getattr(server, name)(str(tmp_path / "missing.wav"))


def test_undecodable_audio_returns_error(tmp_path, monkeypatch):
    path = tmp_path / "bad.wav"
    path.write_bytes(b"not an audio file")
    monkeypatch.setattr(server, "_config", ServerConfig())
    assert "error" in server.get_energy_profile(str(path))


@pytest.mark.parametrize(
    ("tool", "module", "function"),
    [
        ("analyze_song", analyzer, "full_analysis"),
        ("get_beat_map", beats, "detect_beats"),
        ("get_energy_profile", spectrum, "analyze_spectrum"),
        ("get_song_structure", structure, "detect_structure"),
    ],
)
def test_analysis_failures_are_explicit(tool, module, function, tmp_path, monkeypatch, caplog):
    path = tmp_path / "bad.wav"
    path.write_bytes(b"invalid audio")
    monkeypatch.setattr(server, "_config", ServerConfig())

    def fail(*args, **kwargs):
        raise ValueError("cannot decode")

    monkeypatch.setattr(module, function, fail)
    assert "cannot decode" in getattr(server, tool)(str(path))["error"]
    assert "failed for" in caplog.text


@pytest.mark.parametrize(
    ("tool", "module", "function", "result", "required"),
    [
        (
            "get_beat_map",
            beats,
            "detect_beats",
            beats.BeatMap(),
            {"tempo", "beat_times", "downbeat_times", "onset_times", "beats_per_bar"},
        ),
        (
            "get_energy_profile",
            spectrum,
            "analyze_spectrum",
            spectrum.SpectrumAnalysis(),
            {"duration_seconds", "rms_energy", "rms_times", "bands", "dynamic_range"},
        ),
        ("get_song_structure", structure, "detect_structure", [], {"sections"}),
    ],
)
def test_tools_preserve_response_keys_and_use_configured_rate(
    tool, module, function, result, required, tmp_path, monkeypatch
):
    path = tmp_path / "song.wav"
    path.touch()
    monkeypatch.setattr(server, "_config", ServerConfig(audio=AudioConfig(sample_rate=16000)))
    calls = []

    def analyze(path, sr):
        calls.append(sr)
        return result

    monkeypatch.setattr(module, function, analyze)
    assert required <= getattr(server, tool)(str(path)).keys()
    assert calls == [16000]
