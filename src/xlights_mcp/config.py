"""Configuration management for xLights MCP Server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


CONFIG_DIR = Path.home() / ".xlights-mcp"
CONFIG_FILE = CONFIG_DIR / "config.json"
AUDIO_CACHE_DIR = CONFIG_DIR / "audio_cache"


class FPPConfig(BaseModel):
    """Falcon Pi Player connection settings."""

    host: str = "fpp.local"
    port: int = 80
    timeout: float = 10.0


class AudioConfig(BaseModel):
    """Audio analysis settings."""

    cache_dir: Path = AUDIO_CACHE_DIR
    demucs_model: str = "htdemucs"
    sample_rate: int = 22050
    frame_rate_ms: int = 25  # xLights standard: 25ms per frame (40fps)


class ServerConfig(BaseModel):
    """Main server configuration."""

    show_folders: dict[str, str] = Field(default_factory=dict)
    active_show: str = ""
    fpp: FPPConfig = Field(default_factory=FPPConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)

    @property
    def active_show_path(self) -> Path | None:
        """Get the filesystem path for the currently active show."""
        folder = self.show_folders.get(self.active_show)
        if folder:
            return Path(folder).expanduser()
        return None

    def get_show_path(self, show_name: str) -> Path | None:
        """Get the filesystem path for a named show."""
        folder = self.show_folders.get(show_name)
        if folder:
            return Path(folder).expanduser()
        return None

    def list_shows(self) -> list[str]:
        """List all configured show names."""
        return list(self.show_folders.keys())


def _find_xlights_show_folders() -> dict[str, str]:
    """Auto-detect xLights show folders from common locations."""
    candidates = [
        Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "xLights",  # macOS iCloud
        Path.home() / "Documents" / "xLights",  # macOS/Windows default
        Path.home() / "xLights",  # Linux / simple
        Path("/opt/xLights"),  # Linux system-wide
    ]

    folders: dict[str, str] = {}
    for base in candidates:
        if not base.exists():
            continue
        for child in sorted(base.iterdir()):
            if child.is_dir() and (child / "xlights_rgbeffects.xml").exists():
                folders[child.name.lower()] = str(child)

    return folders


def load_config() -> ServerConfig:
    """Load configuration from disk, auto-detecting show folders if needed."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        config = ServerConfig(**data)
        # Re-detect if all configured paths are missing
        if config.show_folders and not any(
            Path(p).expanduser().exists() for p in config.show_folders.values()
        ):
            detected = _find_xlights_show_folders()
            if detected:
                config.show_folders = detected
                config.active_show = next(iter(detected))
                save_config(config)
        return config

    # First run — auto-detect show folders
    folders = _find_xlights_show_folders()
    if folders:
        active = next(iter(folders))
        config = ServerConfig(show_folders=folders, active_show=active)
    else:
        # No show folders found — create empty config so tools can report the issue
        config = ServerConfig(show_folders={}, active_show="")

    save_config(config)
    return config


def save_config(config: ServerConfig) -> None:
    """Persist configuration to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config.model_dump(mode="json"), f, indent=2, default=str)
