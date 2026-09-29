"""Unit tests for show folder parsing helpers."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from lxml import etree

from xlights_mcp.xlights.show import load_model_groups, model_pixel_count


class TestModelPixelCount:
    def test_pixel_count_attribute(self):
        m = ET.fromstring('<model name="Cane" PixelCount="99" parm1="21" parm2="47"/>')
        assert model_pixel_count(m) == 99

    def test_legacy_parm_attributes(self):
        m = ET.fromstring('<model name="Eaves" DisplayAs="Single Line" parm1="1" parm2="47"/>')
        assert model_pixel_count(m) == 47

    def test_xlights_2026_strings_and_nodes(self):
        # xLights 2026 layouts drop parm1/parm2 for string-based models
        m = ET.fromstring(
            '<model name="Eaves" DisplayAs="Single Line" NumStrings="1" NodesPerString="47"/>'
        )
        assert model_pixel_count(m) == 47

    def test_lxml_element(self):
        m = etree.fromstring('<model name="Arch" NumStrings="4" NodesPerString="50"/>')
        assert model_pixel_count(m) == 200

    def test_no_size_attributes(self):
        assert model_pixel_count(ET.fromstring('<model name="X"/>')) == 0

    def test_non_numeric_falls_through(self):
        m = ET.fromstring('<model name="X" PixelCount="" parm1="a" parm2="2" NumStrings="2" NodesPerString="3"/>')
        assert model_pixel_count(m) == 6


class TestLoadModelGroups:
    def test_groups_in_modelgroups_section(self, tmp_path):
        (tmp_path / "xlights_rgbeffects.xml").write_text(
            '<xrgb><models><model name="A"/><model name="B"/></models>'
            '<modelGroups><modelGroup name="All" models="A, B" GridSize="400"/></modelGroups></xrgb>'
        )
        groups = load_model_groups(tmp_path)
        assert [(g.name, g.members) for g in groups] == [("All", ["A", "B"])]

    def test_groups_nested_under_models(self, tmp_path):
        (tmp_path / "xlights_rgbeffects.xml").write_text(
            '<xrgb><models><model name="A"/><modelGroup name="Nested" models="A"/></models></xrgb>'
        )
        assert [g.name for g in load_model_groups(tmp_path)] == ["Nested"]
