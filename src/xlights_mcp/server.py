"""MCP Server entry point for xLights Sequence Generator."""

from __future__ import annotations

import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from xlights_mcp.config import load_config, save_config, ServerConfig

logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP(
    "xLights Sequence Generator",
    instructions="Analyze music and generate xLights light show sequences. "
    "Use list_shows/switch_show to manage show folders, analyze_song to analyze music, "
    "and create_sequence to generate .xsq files.",
)

# Global config — loaded at startup
_config: ServerConfig | None = None


def get_config() -> ServerConfig:
    """Get the current server configuration."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


# ---------------------------------------------------------------------------
# Show Management Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_shows() -> dict:
    """List all configured xLights show folders.

    Returns the available show folders (e.g., Christmas, Halloween) and
    indicates which one is currently active.
    """
    config = get_config()
    if not config.show_folders:
        return {
            "error": "No xLights show folders found.",
            "hint": (
                "No show folders were auto-detected. Make sure xLights is installed "
                "and has at least one show folder containing xlights_rgbeffects.xml. "
                "Common locations: ~/Documents/xLights/, ~/xLights/, or iCloud Drive. "
                "You can also manually create ~/.xlights-mcp/config.json with your paths."
            ),
        }
    shows = {}
    for name, path_str in config.show_folders.items():
        path = Path(path_str).expanduser()
        shows[name] = {
            "path": str(path),
            "exists": path.exists(),
            "active": name == config.active_show,
        }
    return {"shows": shows, "active": config.active_show}


@mcp.tool()
def switch_show(show_name: str) -> dict:
    """Switch the active xLights show folder.

    Args:
        show_name: Name of the show to activate (e.g., "christmas", "halloween")
    """
    config = get_config()
    if show_name not in config.show_folders:
        return {
            "error": f"Unknown show '{show_name}'. Available: {config.list_shows()}"
        }

    config.active_show = show_name
    save_config(config)
    return {"active_show": show_name, "path": str(config.active_show_path)}


@mcp.tool()
def list_models() -> dict:
    """List all light models in the active xLights show.

    Returns model names, types, controller assignments, and channel info.
    """
    from xlights_mcp.xlights.show import load_show_models

    config = get_config()
    show_path = config.active_show_path
    if not show_path or not show_path.exists():
        return {
            "error": "No active show folder configured.",
            "hint": "Run list_shows first. If no shows are found, make sure xLights is installed "
            "with at least one show folder, or manually configure ~/.xlights-mcp/config.json.",
        }

    models = load_show_models(show_path)
    return {
        "show": config.active_show,
        "model_count": len(models),
        "models": [m.model_dump() for m in models],
    }


@mcp.tool()
def list_controllers() -> dict:
    """List all controllers configured in the active xLights show.

    Returns controller names, IPs, protocols, and channel counts.
    """
    from xlights_mcp.xlights.show import load_show_controllers

    config = get_config()
    show_path = config.active_show_path
    if not show_path or not show_path.exists():
        return {
            "error": "No active show folder configured.",
            "hint": "Run list_shows first. If no shows are found, make sure xLights is installed "
            "with at least one show folder, or manually configure ~/.xlights-mcp/config.json.",
        }

    controllers = load_show_controllers(show_path)
    return {
        "show": config.active_show,
        "controller_count": len(controllers),
        "controllers": [c.model_dump() for c in controllers],
    }


@mcp.tool()
def list_sequences() -> dict:
    """List all sequences (.xsq files) in the active show folder."""
    config = get_config()
    show_path = config.active_show_path
    if not show_path or not show_path.exists():
        return {
            "error": "No active show folder configured.",
            "hint": "Run list_shows first. If no shows are found, make sure xLights is installed "
            "with at least one show folder, or manually configure ~/.xlights-mcp/config.json.",
        }

    sequences = []
    for xsq in sorted(show_path.glob("*.xsq")):
        sequences.append({"name": xsq.stem, "path": str(xsq)})
    return {
        "show": config.active_show,
        "sequence_count": len(sequences),
        "sequences": sequences,
    }


@mcp.tool()
def inspect_sequence(sequence_name: str) -> dict:
    """Inspect an existing xLights sequence file.

    Shows the song info, duration, models used, and effect summary.

    Args:
        sequence_name: Name of the sequence (without .xsq extension)
    """
    from xlights_mcp.xlights.xsq_reader import read_xsq_summary

    config = get_config()
    show_path = config.active_show_path
    if not show_path:
        return {"error": "No active show configured"}

    xsq_path = show_path / f"{sequence_name}.xsq"
    if not xsq_path.exists():
        return {"error": f"Sequence not found: {xsq_path}"}

    return read_xsq_summary(xsq_path)


@mcp.tool()
def list_effects() -> dict:
    """List all available xLights effects with descriptions.

    Returns effect names, descriptions, and which model types they work best on.
    """
    from xlights_mcp.xlights.effects import get_effect_library

    return {"effects": get_effect_library()}


# ---------------------------------------------------------------------------
# Audio Analysis Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def analyze_song(mp3_path: str) -> dict:
    """Analyze a music file for light show sequencing.

    Performs full audio analysis: beat detection, song structure,
    frequency spectrum, energy profile, and optionally source separation.

    Args:
        mp3_path: Path to the .mp3 file to analyze
    """
    from xlights_mcp.audio.analyzer import full_analysis

    path = Path(mp3_path).expanduser()
    if not path.exists():
        return {"error": f"File not found: {path}"}

    config = get_config()
    analysis = full_analysis(path, config.audio)
    return analysis.model_dump()


@mcp.tool()
def get_song_structure(mp3_path: str) -> dict:
    """Get the verse/chorus/bridge structure of a song.

    Args:
        mp3_path: Path to the .mp3 file
    """
    from xlights_mcp.audio.structure import detect_structure

    path = Path(mp3_path).expanduser()
    if not path.exists():
        return {"error": f"File not found: {path}"}

    sections = detect_structure(path)
    return {"sections": [s.model_dump() for s in sections]}


@mcp.tool()
def get_beat_map(mp3_path: str) -> dict:
    """Get beat and downbeat timestamps for a song.

    Args:
        mp3_path: Path to the .mp3 file
    """
    from xlights_mcp.audio.beats import detect_beats

    path = Path(mp3_path).expanduser()
    if not path.exists():
        return {"error": f"File not found: {path}"}

    result = detect_beats(path)
    return result.model_dump()


@mcp.tool()
def get_energy_profile(mp3_path: str) -> dict:
    """Get energy and frequency band analysis for a song.

    Returns loudness curve and bass/mid/high energy over time.

    Args:
        mp3_path: Path to the .mp3 file
    """
    from xlights_mcp.audio.spectrum import analyze_spectrum

    path = Path(mp3_path).expanduser()
    if not path.exists():
        return {"error": f"File not found: {path}"}

    result = analyze_spectrum(path)
    return result.model_dump()


# ---------------------------------------------------------------------------
# Sequence Generation Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def create_sequence(
    mp3_path: str,
    mode: str = "auto",
    palette_hint: str | None = None,
    theme: str | None = None,
    vocal_assignments: dict[str, str] | None = None,
) -> dict:
    """Create an xLights sequence from a music file.

    Analyzes the audio and generates a .xsq file with effects placed on
    your light models according to the selected generation mode.

    Args:
        mp3_path: Path to the .mp3 file
        mode: Generation mode — "auto" (AI picks everything), "guided" (interactive),
              or "template" (apply saved recipes)
        palette_hint: Optional color hint (e.g., "red and green", "orange and purple")
        theme: Optional theme hint (e.g., "christmas", "halloween", "energetic")
        vocal_assignments: Optional mapping of model names to vocal track names.
            Use {"all": "<track_name>"} to assign one track to all singing models,
            or map individual models like {"Snowman": "Vocals", "Bulb Blue": "Full Mix Vocals"}.
            If omitted and singing models are detected, returns available models and
            tracks so you can prompt the user for assignments.
    """
    from xlights_mcp.sequencer.engine import generate_sequence

    path = Path(mp3_path).expanduser()
    if not path.exists():
        return {"error": f"File not found: {path}"}

    if mode not in ("auto", "guided", "template"):
        return {"error": f"Invalid mode '{mode}'. Use: auto, guided, template"}

    config = get_config()
    result = generate_sequence(
        mp3_path=path,
        show_path=config.active_show_path,
        mode=mode,
        palette_hint=palette_hint,
        theme=theme,
        audio_config=config.audio,
        vocal_assignments=vocal_assignments,
    )
    return result


@mcp.tool()
def preview_plan(mp3_path: str, mode: str = "auto") -> dict:
    """Preview the sequence generation plan without creating a file.

    Shows what effects would be placed on which models, based on the
    audio analysis and selected mode.

    Args:
        mp3_path: Path to the .mp3 file
        mode: Generation mode — "auto", "guided", or "template"
    """
    from xlights_mcp.sequencer.engine import preview_sequence_plan

    path = Path(mp3_path).expanduser()
    if not path.exists():
        return {"error": f"File not found: {path}"}

    config = get_config()
    return preview_sequence_plan(
        mp3_path=path,
        show_path=config.active_show_path,
        mode=mode,
        audio_config=config.audio,
    )


# ---------------------------------------------------------------------------
# FPP Integration Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def fpp_status() -> dict:
    """Check Falcon Pi Player connection status and current state.

    Returns FPP version, current playlist, scheduler state, etc.
    """
    from xlights_mcp.fpp.client import get_fpp_status

    config = get_config()
    return get_fpp_status(config.fpp)


@mcp.tool()
def fpp_upload_sequence(fseq_path: str, audio_path: str | None = None) -> dict:
    """Upload a sequence (.fseq) and optional audio to Falcon Pi Player.

    Args:
        fseq_path: Path to the .fseq file to upload
        audio_path: Optional path to the audio file (.mp3/.ogg)
    """
    from xlights_mcp.fpp.upload import upload_sequence

    config = get_config()
    return upload_sequence(config.fpp, Path(fseq_path), Path(audio_path) if audio_path else None)


@mcp.tool()
def fpp_list_playlists() -> dict:
    """List all playlists on the Falcon Pi Player."""
    from xlights_mcp.fpp.client import list_playlists

    config = get_config()
    return list_playlists(config.fpp)


@mcp.tool()
def fpp_start_playlist(playlist_name: str, repeat: bool = False) -> dict:
    """Start a playlist on the Falcon Pi Player.

    Args:
        playlist_name: Name of the playlist to start
        repeat: Whether to loop the playlist
    """
    from xlights_mcp.fpp.client import start_playlist

    config = get_config()
    return start_playlist(config.fpp, playlist_name, repeat)


@mcp.tool()
def fpp_stop() -> dict:
    """Stop current playback on the Falcon Pi Player."""
    from xlights_mcp.fpp.client import stop_playback

    config = get_config()
    return stop_playback(config.fpp)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Run the xLights MCP server."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting xLights MCP Server v0.1.0")

    # Ensure config is loaded at startup
    config = get_config()
    logger.info(f"Active show: {config.active_show}")
    logger.info(f"Show path: {config.active_show_path}")

    mcp.run()


if __name__ == "__main__":
    main()
