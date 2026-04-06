"""Unit tests for the path rewriter module."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from xlights_mcp.remapper.path_rewriter import rewrite_effect_paths, _rewrite_settings_string


# ---------------------------------------------------------------------------
# _rewrite_settings_string  (T031)
# ---------------------------------------------------------------------------


class TestRewriteSettingsString:
    def test_filepickerctrl_rewritten(self, tmp_path):
        settings = (
            "E_CHOICE_Chase_Type1=Left-Right,"
            "E_FILEPICKERCTRL_Video_Filename=/Users/xtreme/Desktop/xLights/Videos/intro.mp4,"
            "E_SLIDER_Chase_Rotations=10"
        )
        warnings: list[str] = []
        result = _rewrite_settings_string(settings, tmp_path, warnings)
        assert str(tmp_path / "intro.mp4") in result
        assert "/Users/xtreme" not in result
        # Non-path keys preserved
        assert "E_CHOICE_Chase_Type1=Left-Right" in result
        assert "E_SLIDER_Chase_Rotations=10" in result

    def test_missing_media_warning(self, tmp_path):
        settings = "E_FILEPICKERCTRL_IFS=/some/path/shader.fs"
        warnings: list[str] = []
        _rewrite_settings_string(settings, tmp_path, warnings)
        assert len(warnings) == 1
        assert "shader.fs" in warnings[0]

    def test_existing_media_no_warning(self, tmp_path):
        (tmp_path / "video.mp4").touch()
        settings = "E_0FILEPICKERCTRL_Video=/old/path/video.mp4"
        warnings: list[str] = []
        _rewrite_settings_string(settings, tmp_path, warnings)
        assert len(warnings) == 0

    def test_no_filepickerctrl_unchanged(self, tmp_path):
        settings = "E_SLIDER_Brightness=100,E_CHOICE_Mode=Normal"
        warnings: list[str] = []
        result = _rewrite_settings_string(settings, tmp_path, warnings)
        assert result == settings

    def test_empty_value_preserved(self, tmp_path):
        settings = "E_FILEPICKERCTRL_Video="
        warnings: list[str] = []
        result = _rewrite_settings_string(settings, tmp_path, warnings)
        assert result == settings


# ---------------------------------------------------------------------------
# rewrite_effect_paths  (T027)
# ---------------------------------------------------------------------------


class TestRewriteEffectPaths:
    def test_rewrites_effectdb_paths(self, tmp_path):
        xml = etree.fromstring(
            b"""<xsequence>
            <head><mediaFile>/old/path/audio.mp3</mediaFile></head>
            <EffectDB>
                <Effect>E_FILEPICKERCTRL_Video=/foreign/path/vid.mp4,E_SLIDER_X=5</Effect>
            </EffectDB>
            </xsequence>"""
        )
        warnings = rewrite_effect_paths(xml, tmp_path)
        effect_text = xml.find("EffectDB")[0].text
        assert str(tmp_path / "vid.mp4") in effect_text

    def test_rewrites_media_file(self, tmp_path):
        xml = etree.fromstring(
            b"""<xsequence>
            <head><mediaFile>/Users/other/show/song.mp3</mediaFile></head>
            </xsequence>"""
        )
        rewrite_effect_paths(xml, tmp_path)
        media = xml.find("head/mediaFile").text
        assert str(tmp_path / "song.mp3") in media

    def test_missing_media_produces_warning(self, tmp_path):
        xml = etree.fromstring(
            b"""<xsequence>
            <head><mediaFile>/nonexistent/audio.mp3</mediaFile></head>
            </xsequence>"""
        )
        warnings = rewrite_effect_paths(xml, tmp_path)
        assert any("audio.mp3" in w for w in warnings)
