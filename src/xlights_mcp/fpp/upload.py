"""Upload sequences and audio to Falcon Pi Player."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from xlights_mcp.config import FPPConfig

logger = logging.getLogger(__name__)


def upload_sequence(
    config: FPPConfig,
    fseq_path: Path,
    audio_path: Path | None = None,
) -> dict:
    """Upload a .fseq sequence (and optional audio) to FPP.

    Args:
        config: FPP connection config
        fseq_path: Path to the .fseq file
        audio_path: Optional path to audio file (.mp3, .ogg)
    """
    if not fseq_path.exists():
        return {"error": f"File not found: {fseq_path}"}

    base_url = f"http://{config.host}:{config.port}"
    results = {}

    # Upload the .fseq file
    try:
        with open(fseq_path, "rb") as f:
            resp = httpx.post(
                f"{base_url}/api/sequence/{fseq_path.name}",
                content=f.read(),
                headers={"Content-Type": "application/octet-stream"},
                timeout=60.0,
            )
            resp.raise_for_status()
            results["fseq"] = {"uploaded": True, "name": fseq_path.name}
    except httpx.ConnectError:
        return {"error": f"Cannot connect to FPP at {config.host}:{config.port}"}
    except Exception as e:
        return {"error": f"Failed to upload {fseq_path.name}: {e}"}

    # Upload audio if provided
    if audio_path and audio_path.exists():
        try:
            with open(audio_path, "rb") as f:
                resp = httpx.post(
                    f"{base_url}/api/file/music/{audio_path.name}",
                    content=f.read(),
                    headers={"Content-Type": "application/octet-stream"},
                    timeout=60.0,
                )
                resp.raise_for_status()
                results["audio"] = {"uploaded": True, "name": audio_path.name}
        except Exception as e:
            results["audio"] = {"error": f"Failed to upload audio: {e}"}

    return {"success": True, **results}
