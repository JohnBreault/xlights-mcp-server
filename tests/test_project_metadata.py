from __future__ import annotations

import tomllib
from pathlib import Path


def test_runtime_dependencies_support_current_mcp_api():
    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]

    assert "mcp[cli]>=1.2.0,<2" in project["dependencies"]


def test_madmom_stays_optional_without_a_build_during_uv_resolution():
    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert not any(dep.startswith("madmom") for dep in project["project"]["dependencies"])
    assert "madmom>=0.16.1" in project["project"]["optional-dependencies"]["beats"]
    assert {
        "name": "madmom",
        "version": "0.16.1",
        "requires-dist": ["numpy>=1.13.4", "scipy>=0.16", "cython>=0.25", "mido>=1.2.8"],
    } in project["tool"]["uv"]["dependency-metadata"]
