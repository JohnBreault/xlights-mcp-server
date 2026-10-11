"""Windows stdio transport that doesn't deadlock DLL loads.

On Windows, a synchronous ReadFile pending on the stdin pipe blocks any other
thread that loads a native extension (numpy, scipy, librosa's lazy imports, …)
until the next MCP message arrives. The stock stdio transport keeps such a read
pending between requests, so the first tool call that imports numpy hangs.

This reader polls PeekNamedPipe and only reads once data is waiting, so no
blocking read is ever left outstanding on the pipe.
"""

from __future__ import annotations

import ctypes
import io
import msvcrt
import os
import sys
import time
from ctypes import wintypes

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server

FILE_TYPE_PIPE = 3
POLL_INTERVAL = 0.01

_kernel32 = ctypes.windll.kernel32
_kernel32.PeekNamedPipe.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.c_void_p,
]
_kernel32.GetFileType.argtypes = [wintypes.HANDLE]


class _PolledPipe(io.RawIOBase):
    def __init__(self, fd: int):
        self._fd = fd
        self._handle = msvcrt.get_osfhandle(fd)

    def readable(self) -> bool:
        return True

    def readinto(self, buf) -> int:
        available = wintypes.DWORD()
        while True:
            if not _kernel32.PeekNamedPipe(
                self._handle, None, 0, None, ctypes.byref(available), None
            ):
                return 0  # pipe closed by the client -> EOF
            if available.value:
                data = os.read(self._fd, min(available.value, len(buf)))
                buf[: len(data)] = data
                return len(data)
            time.sleep(POLL_INTERVAL)


def stdin_is_pipe() -> bool:
    handle = msvcrt.get_osfhandle(sys.stdin.fileno())
    return _kernel32.GetFileType(handle) == FILE_TYPE_PIPE


def run(mcp: FastMCP) -> None:
    """Equivalent of mcp.run() (stdio) using the polling stdin reader."""
    stdin = anyio.wrap_file(
        io.TextIOWrapper(
            io.BufferedReader(_PolledPipe(sys.stdin.fileno())),
            encoding="utf-8",
            errors="replace",
        )
    )

    async def _serve() -> None:
        async with stdio_server(stdin=stdin) as (read_stream, write_stream):
            await mcp._mcp_server.run(
                read_stream, write_stream, mcp._mcp_server.create_initialization_options()
            )

    anyio.run(_serve)
