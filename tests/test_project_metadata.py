from __future__ import annotations

import tomllib
from pathlib import Path


def test_runtime_dependencies_support_current_mcp_api():
    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]

    assert "mcp[cli]>=1.2.0,<2" in project["dependencies"]


def test_modern_madmom_stays_optional_and_pinned():
    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert not any(dep.startswith("madmom") for dep in project["project"]["dependencies"])
    beat_dependencies = project["project"]["optional-dependencies"]["beats"]
    assert len(beat_dependencies) == 1
    dependency, marker = beat_dependencies[0].split(";", 1)
    assert dependency.strip() == (
        "madmom-modern @ https://github.com/imcmurray/madmom-modern/archive/"
        "df718c704a3b460ac6c61b7e61663a0436b91bda.tar.gz"
    )
    assert marker.strip() == "sys_platform != 'darwin' or platform_machine != 'x86_64'"
