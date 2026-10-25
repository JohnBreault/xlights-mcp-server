from __future__ import annotations

import tomllib
from pathlib import Path


def test_runtime_dependencies_support_current_mcp_api():
    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]

    assert "mcp[cli]>=1.2.0,<2" in project["dependencies"]


def test_madmom_builds_with_uv_extra_build_dependency():
    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert "Cython" in project["tool"]["uv"]["extra-build-dependencies"]["madmom"]
