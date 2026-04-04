"""FPP schedule management."""

from __future__ import annotations

from xlights_mcp.config import FPPConfig
from xlights_mcp.fpp.client import _get, _post


def get_schedule(config: FPPConfig) -> dict:
    """Get the current FPP schedule."""
    return _get(config, "/schedule")


def reload_schedule(config: FPPConfig) -> dict:
    """Reload the FPP schedule from disk."""
    return _post(config, "/schedule/reload")
