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


def test_legacy_numpy_constraint_is_limited_to_supported_intel_macos_python():
    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )

    optional_dependencies = project["project"]["optional-dependencies"]
    for extra in ("separation", "lyrics"):
        numpy_dependency = next(
            dependency
            for dependency in optional_dependencies[extra]
            if dependency.startswith("numpy<2;")
        )
        assert numpy_dependency.split(";", 1)[1].strip() == (
            "sys_platform == 'darwin' and platform_machine == 'x86_64' "
            "and python_version < '3.13'"
        )

    assert (
        "numpy>=2; sys_platform == 'darwin' and platform_machine == 'x86_64' "
        "and python_version >= '3.13'"
    ) in project["project"]["dependencies"]
