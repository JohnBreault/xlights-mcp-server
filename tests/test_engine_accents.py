"""Accent-hit timing in auto generation when no drum stems are available."""

from __future__ import annotations

from pathlib import Path

from xlights_mcp.audio.analyzer import SongAnalysis
from xlights_mcp.audio.beats import BeatMap
from xlights_mcp.audio.structure import SongSection
from xlights_mcp.sequencer import engine
from xlights_mcp.xlights.models import LightModel, ShowConfig

BEAT = 0.5  # 120 BPM
BEATS = [round(i * BEAT, 3) for i in range(64)]  # 32 s
DOWNBEATS = BEATS[::4]


def _accent_starts(tmp_path, monkeypatch, energy: float) -> list[float]:
    analysis = SongAnalysis(
        file_path="song.mp3",
        file_name="song.mp3",
        duration_seconds=32.0,
        beats=BeatMap(tempo=120.0, beat_times=BEATS, downbeat_times=DOWNBEATS),
        sections=[SongSection(label="chorus", start_time=0.0, end_time=32.0, energy_level=energy)],
    )
    show = ShowConfig(
        show_path=str(tmp_path),
        show_name="test",
        models=[LightModel(name="Eaves 1", display_as="Single Line", pixel_count=47)],
    )
    captured = {}
    monkeypatch.setattr(engine, "write_xsq", lambda spec, *_: captured.setdefault("spec", spec))
    engine._generate_auto(analysis, show, Path(tmp_path) / "song.mp3", None, "christmas")
    return sorted(e.start_time_ms / 1000 for e in captured["spec"].effects if e.layer == 2)


def test_high_energy_accents_hit_every_beat(tmp_path, monkeypatch):
    starts = _accent_starts(tmp_path, monkeypatch, energy=0.9)
    assert starts == BEATS


def test_accents_hit_every_other_beat(tmp_path, monkeypatch):
    starts = _accent_starts(tmp_path, monkeypatch, energy=0.7)
    assert starts == BEATS[::2]
