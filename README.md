# xLights MCP Server

A Model Context Protocol (MCP) server that analyzes music and generates xLights light show sequences. Integrates with GitHub Copilot CLI for a conversational workflow.

## Features

- **Audio Analysis**: Beat detection, song structure analysis, frequency spectrum, source separation
- **Sequence Generation**: Creates valid .xsq files with effects placed on your actual light models
- **Three Modes**: Fully automatic, guided/interactive, and template-based generation
- **Show Management**: Read and work with your existing xLights show folders
- **FPP Integration**: Upload sequences, manage playlists, control Falcon Pi Player

## Quick Start

```bash
# Install with uv
uv pip install -e ".[all]"

# Or minimal install (no GPU-heavy deps)
uv pip install -e .

# Run the server
xlights-mcp-server
```

## Copilot CLI Integration

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "xlights": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/xlights-mcp-server", "xlights-mcp-server"]
    }
  }
}
```

## Configuration

Create `~/.xlights-mcp/config.json`:

```json
{
  "show_folders": {
    "christmas": "~/Library/Mobile Documents/com~apple~CloudDocs/xLights/Christmas",
    "halloween": "~/Library/Mobile Documents/com~apple~CloudDocs/xLights/Halloween",
    "baseline": "~/Library/Mobile Documents/com~apple~CloudDocs/xLights/house-baseline"
  },
  "active_show": "christmas",
  "fpp": {
    "host": "rudolph.local",
    "port": 80
  }
}
```

## License

MIT
