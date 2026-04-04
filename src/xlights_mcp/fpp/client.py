"""Falcon Pi Player (FPP) REST API client."""

from __future__ import annotations

import logging

import httpx

from xlights_mcp.config import FPPConfig

logger = logging.getLogger(__name__)


def _base_url(config: FPPConfig) -> str:
    return f"http://{config.host}:{config.port}"


def _get(config: FPPConfig, path: str) -> dict:
    """Make a GET request to the FPP API."""
    url = f"{_base_url(config)}/api{path}"
    try:
        resp = httpx.get(url, timeout=config.timeout)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        return {"error": f"Cannot connect to FPP at {config.host}:{config.port}. Is it on the network?"}
    except httpx.TimeoutException:
        return {"error": f"Timeout connecting to FPP at {config.host}:{config.port}"}
    except Exception as e:
        return {"error": str(e)}


def _post(config: FPPConfig, path: str, data: dict | None = None) -> dict:
    """Make a POST request to the FPP API."""
    url = f"{_base_url(config)}/api{path}"
    try:
        resp = httpx.post(url, json=data, timeout=config.timeout)
        resp.raise_for_status()
        return resp.json() if resp.content else {"success": True}
    except httpx.ConnectError:
        return {"error": f"Cannot connect to FPP at {config.host}:{config.port}"}
    except httpx.TimeoutException:
        return {"error": f"Timeout connecting to FPP at {config.host}:{config.port}"}
    except Exception as e:
        return {"error": str(e)}


def get_fpp_status(config: FPPConfig) -> dict:
    """Get FPP system status including current playback state."""
    status = _get(config, "/system/status")
    if "error" in status:
        return status

    return {
        "connected": True,
        "host": config.host,
        "status": status,
    }


def list_playlists(config: FPPConfig) -> dict:
    """List all playlists on FPP."""
    result = _get(config, "/playlists")
    if "error" in result:
        return result
    return {"playlists": result}


def start_playlist(config: FPPConfig, name: str, repeat: bool = False) -> dict:
    """Start a playlist on FPP."""
    repeat_val = "1" if repeat else "0"
    return _get(config, f"/playlist/{name}/start/{repeat_val}")


def stop_playback(config: FPPConfig) -> dict:
    """Stop current playback on FPP."""
    return _get(config, "/playlists/stop")


def list_sequences(config: FPPConfig) -> dict:
    """List sequences stored on FPP."""
    return _get(config, "/sequence")


def get_schedule(config: FPPConfig) -> dict:
    """Get the FPP schedule."""
    return _get(config, "/schedule")
