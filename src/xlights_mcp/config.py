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

    host: str = "rudolph.local"
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
    active_show: str = "christmas"
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


def load_config() -> ServerConfig:
    """Load configuration from disk, creating defaults if needed."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        return ServerConfig(**data)

    # Create default config
    config = ServerConfig(
        show_folders={
            "christmas": "~/Library/Mobile Documents/com~apple~CloudDocs/xLights/Christmas",
            "halloween": "~/Library/Mobile Documents/com~apple~CloudDocs/xLights/Halloween",
            "baseline": "~/Library/Mobile Documents/com~apple~CloudDocs/xLights/house-baseline",
        },
        active_show="christmas",
    )
    save_config(config)
    return config


def save_config(config: ServerConfig) -> None:
    """Persist configuration to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config.model_dump(mode="json"), f, indent=2, default=str)
