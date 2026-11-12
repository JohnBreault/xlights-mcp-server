> **⚠️ Beta:** This project is currently in beta. Features may change, and you may encounter bugs. Feedback and contributions are welcome!

# xLights MCP Server

An MCP (Model Context Protocol) server that analyzes music and generates [xLights](https://xlights.org/) light show sequences. Works with any MCP-compatible AI tool — [GitHub Copilot CLI](https://docs.github.com/en/copilot/github-copilot-in-the-cli), [Claude Desktop](https://claude.ai/download), [Cursor](https://cursor.sh), [VS Code + Copilot Chat](https://code.visualstudio.com/), [Windsurf](https://codeium.com/windsurf), [Cline](https://github.com/cline/cline), and more.

Give it an `.mp3`, and it will analyze the beats, song structure, and energy — then generate a valid `.xsq` sequence file with effects placed across all of your light models, synced to the music

---

## What It Does

### 🎵 Audio Analysis
- **Beat & tempo detection** — percussion-aware beats, phase-aligned bars, conservative meter estimates, and local tempo changes
- **Song structure** — beat-synchronized timbre/harmony changes and acoustic repetition, with heuristic section labels
- **Frequency spectrum** — bass, mid, and high energy curves over time
- **Energy profiling** — loudness dynamics, multiscale RMS, spectral flux/brightness, peak detection, and dynamic range
- **Source separation** — isolate vocals, drums, bass, and other stems via [Demucs](https://github.com/facebookresearch/demucs) (optional)

### 💡 Sequence Generation
- **Generates valid `.xsq` files** that open directly in xLights — no xLights GUI required during generation
- **Reads your actual show config** — knows your models, controllers, channel counts, and model types
- **Intelligent effect selection** — picks effects based on model type (arches get chases, trees get spirals, etc.) and musical features (beats → shockwaves, choruses → high energy, verses → gentle)
- **Theme-aware palettes** — Christmas (red/green/gold) and Halloween (orange/purple) color schemes
- **Three generation modes:**
  - **Automatic** — AI picks everything, you review in xLights
  - **Guided** — AI shows song structure, you choose effects per section
  - **Template** — define reusable effect recipes, AI places them on beat
- **Never overwrites** — existing sequences are safe; generated files get a `(generated N)` suffix

### 📦 Sequence Import & Remapping
- **Import community sequences** — take any `.xsq` or `.zip` package from the xLights community and remap it to your show layout
- **Intelligent model matching** — automatically maps imported models to yours by name, type, and pixel count
- **Zip package support** — extracts audio, video, shader, and image assets; rewrites hardcoded file paths
- **Singing model awareness** — singing face models only match to other singing models
- **Full mapping report** — see exactly what matched, how, and what was skipped
- **Manual overrides** — correct any mapping before the remapped sequence is generated

### 📡 FPP Integration
- **Check status** of your Falcon Pi Player
- **Upload sequences** (.fseq + audio) to FPP
- **Manage playlists** — list, start, stop
- Works with FPP's REST API

---

## Prerequisites

- **Python 3.11+** (Python 3.12 recommended for optional audio features)
- **[uv](https://docs.astral.sh/uv/)** (recommended) or pip
- **ffmpeg** — for audio format handling (`brew install ffmpeg` on macOS, `apt install ffmpeg` on Linux)
- **xLights** — installed with at least one show folder configured

---

## Installation

### Step 1: Clone the repository

```bash
git clone https://github.com/JohnBreault/xlights-mcp-server.git
cd xlights-mcp-server
```

### Step 2: Create a virtual environment and install

```bash
uv venv --python 3.12
uv pip install -e .
```

If you already created `.venv` with an unsupported Python version, remove it
and run `uv venv --python 3.12` again. PyTorch wheels for `separation` and
`lyrics` may not be available for the newest Python releases, including 3.15.

**Optional extras for enhanced features:**

```bash
# Stem separation — isolates vocals/drums/bass for smarter sequencing (~2GB model download)
uv pip install -e ".[separation]"

# Lyrics/singing faces — transcribes vocals for lip-sync animation
uv pip install -e ".[lyrics]"

# Better beat detection
uv pip install -e ".[beats]"

# Everything
uv pip install -e ".[all]"
```

The `beats` extra uses a pinned [modernized madmom fork](https://github.com/imcmurray/madmom-modern)
with bundled models. Installing it requires GitHub access and a C compiler
(Xcode Command Line Tools on macOS, or Visual C++ Build Tools on Windows).
The models have a separate non-commercial license; see the fork's README.
Without this extra, core beat detection uses librosa.
Because this extra requires NumPy 2, if you add it to an environment that
already has `separation` or `lyrics`, upgrade the combined extras so PyTorch
is upgraded too (on platforms that support PyTorch 2.3 or later):

```bash
uv pip install --upgrade -e ".[separation,beats,lyrics]"
```

Omit any extras you do not use.
On Intel macOS, `separation` and `lyrics` use PyTorch 2.2.x with NumPy 1.x
because newer PyTorch wheels are unavailable. The `beats` extra skips madmom on
Intel macOS because it requires NumPy 2, so beat detection uses the librosa
fallback there, including when installing `all`.

### Step 3: Show folder configuration

On first run, the server **auto-detects** your xLights show folders by scanning common locations:

| OS | Locations checked |
|----|-------------------|
| macOS | `~/Library/Mobile Documents/com~apple~CloudDocs/xLights/`, `~/Documents/xLights/` |
| Windows | `~/Documents/xLights/` |
| Linux | `~/Documents/xLights/`, `~/xLights/`, `/opt/xLights/` |

It looks for directories containing `xlights_rgbeffects.xml` (the file xLights creates in every show folder).

**If auto-detection doesn't find your folders**, create or edit `~/.xlights-mcp/config.json`:

```json
{
  "show_folders": {
    "christmas": "/path/to/your/xLights/Christmas",
    "halloween": "/path/to/your/xLights/Halloween"
  },
  "active_show": "christmas",
  "fpp": {
    "host": "fpp.local",
    "port": 80
  }
}
```

### Step 4: Connect to your AI tool

The server uses **stdio transport** — your AI tool launches it as a subprocess.

<details>
<summary><strong>GitHub Copilot CLI</strong></summary>

Add to `~/.copilot/mcp-config.json`:

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

Restart Copilot CLI after saving.
</details>

<details>
<summary><strong>Claude Desktop</strong></summary>

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

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

Restart Claude Desktop after saving.
</details>

<details>
<summary><strong>VS Code + Copilot Chat</strong></summary>

Add to your VS Code `settings.json`:

```json
{
  "mcp": {
    "servers": {
      "xlights": {
        "command": "uv",
        "args": ["run", "--directory", "/path/to/xlights-mcp-server", "xlights-mcp-server"]
      }
    }
  }
}
```
</details>

<details>
<summary><strong>Cursor</strong></summary>

Add to Cursor MCP settings (Settings → MCP Servers → Add):

- **Name:** xlights
- **Command:** `uv`
- **Args:** `run --directory /path/to/xlights-mcp-server xlights-mcp-server`
</details>

<details>
<summary><strong>Other MCP clients</strong></summary>

Any tool that supports the [Model Context Protocol](https://modelcontextprotocol.io/) can use this server. Point it at:

```
command: uv
args: run --directory /path/to/xlights-mcp-server xlights-mcp-server
transport: stdio
```
</details>

Replace `/path/to/xlights-mcp-server` with the actual path where you cloned the repo.

---

## Usage

Once connected, interact with the server through natural language in your AI tool. Here are some example workflows:

### Explore your show

```
> List my xLights shows
> Switch to the Halloween show
> List all my light models
> Show me the controllers
> What sequences do I have?
> Inspect the "Deck The Halls" sequence
```

### Analyze a song

```
> Analyze the song ~/Music/Jingle Bell Rock.mp3
> Show me the song structure for ~/Music/Monster Mash.mp3
> Get the beat map for this song
> What's the energy profile look like?
```

The existing audio tools keep their names and arguments. `analyze_song` includes
the same beat and spectrum models returned by `get_beat_map` and
`get_energy_profile`, with these additional fields:

| Result | Additional fields | Units / interpretation |
|--------|-------------------|------------------------|
| Beats | `tempo_curve` | Overlapping 10-second windows, approximately 5 seconds apart; `time` is the window start in seconds, `tempo` is BPM, and `beat_count` records supporting detections. Short clips use one window; insufficient evidence yields zero BPM. |
| Beats | `tempo_changes` | Adjacent positive window estimates differing by more than 10%; `time`, `from_tempo`, and `to_tempo`. These are diagnostic estimates, not exact change boundaries. |
| Beats | `meter_confidence`, `downbeat_confidence`, `rhythm_method`, `warnings` | Heuristic evidence scores (not calibrated probabilities), selected backend, and degraded-analysis diagnostics. |
| Spectrum | `spectral_flux` | Positive frame-to-frame magnitude changes, normalized to 0-1. |
| Spectrum | `spectral_centroid`, `spectral_bandwidth`, `spectral_rolloff` | Hz; rolloff marks 85% of cumulative spectral magnitude. |
| Spectrum | `spectral_flatness` | Dimensionless 0-1 noise/tonality descriptor; silence is not evidence of audible noise. |
| Spectrum | `energy_short`, `energy_medium`, `energy_long` | Normalized RMS smoothed over approximately 0.25, 2, and 8 seconds, capped for short clips. |

All new spectral/energy curves use the existing `rms_times` timeline in seconds.
Existing band names, max-normalized band/RMS curves, raw `average_loudness`, and
`dynamic_range` (maximum RMS divided by mean RMS) retain their meanings.
The detailed seven-band Python option remains available.

Meter inference considers simple two-, three-, and four-beat accent patterns.
Ambiguous patterns, including indistinguishable two-/four-beat accents, retain
four-beat bars with zero inference confidence; this does not prove a 4/4 time
signature. Compound meters are not inferred. When installed and working, madmom
supplies a coherent beat/downbeat grid instead. HPSS failures fall back to
full-mix rhythm analysis with diagnostics. Onsets stay on attacks, without
backtracking into preceding quiet audio.

Section boundaries use beat-synchronized MFCC/chroma, brightness, and RMS features.
Local novelty and acoustic repetition inform boundaries and labels; confident
bar positions (or the selected madmom grid) can refine boundary alignment.
Low-evidence audio falls back to conservative energy boundaries or one whole-file
section. Silence returns an `unknown` section with zero confidence. Labels are
estimates, not guaranteed verse/chorus annotations; too few sections retain
energy-based labeling. All timestamps remain on the original, untrimmed audio
timeline. Sequence generation automatically consumes the improved beats,
downbeats, and sections; it does not yet use the local tempo curve or additional
spectral descriptors directly.

Full analysis (including generation/previews) decodes the full mix once on a cache
miss and persists validated core results under `AudioConfig.cache_dir` (default
`~/.xlights-mcp/audio_cache/`). Cache keys include file contents, sample rate,
analysis version, and relevant dependency versions. Writes are atomic; corrupt
or inaccessible caches are logged and recomputed. Transient enhancement failures
are not persisted as authoritative results. Optional stems are reevaluated outside
the core cache, so newly available stems are not hidden by a previous analysis.
Standalone beat/structure/energy tools analyze only the requested data and do not
use the full-analysis cache. No source audio or show configuration is modified.

These features use existing librosa/NumPy dependencies; no additional package,
service, or model is required. Invalid or undecodable audio produces an explicit
error dictionary from the audio MCP tools.

### Generate a sequence

```
> Create a sequence for ~/Music/Jingle Bell Rock.mp3
> Create a sequence for ~/Music/Jingle Bell Rock.mp3 using red and green colors
> Preview what a sequence would look like for this song before creating it
```

When generating, you'll be asked to choose a mode:
- **auto** — fully automatic, AI picks effects and colors
- **guided** — see the song structure first, then choose effects per section
- **template** — apply saved effect recipes to detected sections

### Import a community sequence

```
> Import the sequence ~/Downloads/Holly Jolly Christmas SD.zip to my show
> Import ~/Downloads/Christmas Time.xsq and show me the model mapping
> Import this sequence but map "Arch Left" to my "Arches-1" model
```

The importer supports both standalone `.xsq` files and `.zip` packages (which include audio, video assets, and the source show's model data). It automatically matches models from the imported sequence to your layout using:
1. **Exact name match** → identical model names
2. **Similar words** → shared words like "snowflake", "arch", "tree"
3. **Model type** → same `display_as` type (e.g., both Arches)
4. **Pixel count** → within 70% of each other
5. **Manual overrides** → you choose specific mappings

### Manage FPP (when controllers are online)

```
> Check the FPP status
> List playlists on FPP
> Start the Christmas playlist
> Stop playback
```

---

## Available Tools

### Show Management
| Tool | Description |
|------|-------------|
| `list_shows` | List all configured xLights show folders |
| `switch_show` | Switch the active show folder |
| `list_models` | List all light models with type, controller, and category info |
| `list_controllers` | List controllers with IPs, protocols, and channel counts |
| `list_sequences` | List all `.xsq` sequence files in the active show |
| `inspect_sequence` | Show song info, duration, effects, and models used in a sequence |
| `list_effects` | List all available xLights effects with descriptions |

### Audio Analysis
| Tool | Description |
|------|-------------|
| `analyze_song` | Full audio analysis: beats, structure, spectrum, energy |
| `get_song_structure` | Detect verse/chorus/bridge/intro/outro sections |
| `get_beat_map` | Get beat timestamps, downbeats, tempo, and onsets |
| `get_energy_profile` | Get loudness curve and bass/mid/high frequency band energy |

### Sequence Generation
| Tool | Description |
|------|-------------|
| `create_sequence` | Generate a `.xsq` file from an `.mp3` with effects on all models |
| `preview_plan` | Preview the generation plan without writing a file |

### Sequence Import & Remapping
| Tool | Description |
|------|-------------|
| `import_sequence` | Import a `.xsq` or `.zip` sequence package and remap models to your layout |

### FPP Integration
| Tool | Description |
|------|-------------|
| `fpp_status` | Check FPP connection and playback state |
| `fpp_upload_sequence` | Upload `.fseq` and audio to FPP |
| `fpp_list_playlists` | List all playlists on FPP |
| `fpp_start_playlist` | Start a playlist (with optional repeat) |
| `fpp_stop` | Stop current playback |

---

## How It Works

### Effect Selection Logic

The server maps **model types** to appropriate effects:

| Model Type | Best Effects |
|------------|-------------|
| Arches | SingleStrand, Chase, ColorWash, Morph |
| Tree | Spirals, Pinwheel, Meteors, Circles |
| Single Line | Chase, Morph, SingleStrand, Shimmer |
| Poly Line | Chase, SingleStrand, Twinkle, Morph |
| Window Frame | Marquee, ColorWash, On, Curtain |
| Custom shapes | Shockwave, Circles, Plasma, Twinkle, Warp |

And maps **musical features** to effect choices:

| Musical Feature | Effects |
|----------------|---------|
| Strong beats | Shockwave, Morph, Strobe |
| Rhythmic passages | SingleStrand, Chase, Bars, Marquee |
| High energy (chorus) | Chase, Meteors, SingleStrand |
| Low energy (verse) | Twinkle, Shimmer, ColorWash, Snowflakes |
| Sustained notes | Plasma, Pinwheel, Spirals, Galaxy |
| Transitions | Warp, Curtain, Morph |
| Intro/Outro | Curtain, ColorWash, Twinkle |

### File Format

Generated `.xsq` files are standard xLights XML containing:
- `<head>` — song metadata, media file path, duration, timing (25ms frames)
- `<ColorPalettes>` — themed color palettes for effects
- `<EffectDB>` — deduplicated effect parameter definitions
- `<DisplayElements>` — all models included in the sequence
- `<ElementEffects>` — effect placements per model, per layer, with timing

---

## Project Structure

```
xlights-mcp-server/
├── pyproject.toml
├── README.md
├── src/xlights_mcp/
│   ├── server.py              # MCP server entry point & tool definitions
│   ├── config.py              # Configuration management
│   ├── audio/
│   │   ├── analyzer.py        # Full analysis pipeline orchestrator
│   │   ├── cache.py           # Versioned core-analysis cache
│   │   ├── beats.py           # Beat/tempo/onset detection (librosa + madmom)
│   │   ├── structure.py       # Song section detection (verse/chorus/bridge)
│   │   ├── spectrum.py        # Frequency band & energy analysis
│   │   └── separator.py       # Demucs stem separation (optional)
│   ├── xlights/
│   │   ├── show.py            # Show folder parser (networks + models XML)
│   │   ├── xsq_reader.py     # Parse existing .xsq sequences
│   │   ├── xsq_writer.py     # Generate .xsq XML files
│   │   ├── effects.py         # Effect library & model/music mappings
│   │   ├── palettes.py        # Color palette definitions & themes
│   │   └── models.py          # Data models (Controller, LightModel, etc.)
│   ├── sequencer/
│   │   └── engine.py          # Sequence generation engine (auto/guided/template)
│   └── fpp/
│       ├── client.py          # FPP REST API client
│       ├── upload.py          # Sequence upload to FPP
│       └── schedule.py        # Schedule management
└── tests/
```

---

## Troubleshooting

**MCP server not loading**
- Verify your MCP config file is valid JSON (no comments, no trailing commas)
- Check the `--directory` path points to the repo root (where `pyproject.toml` is)
- Restart your AI tool after config changes
- Test manually: `cd /path/to/xlights-mcp-server && uv run xlights-mcp-server` — should start without errors

**"No xLights show folders found"**
- Make sure xLights is installed and you've opened it at least once (it creates `xlights_rgbeffects.xml` in each show folder)
- If your show folder is in a non-standard location, add it to `~/.xlights-mcp/config.json`

**"No models found" error**
- Verify the show folder contains `xlights_networks.xml` and `xlights_rgbeffects.xml`
- Use `list_shows` to check which show is active and whether the path exists

**Audio analysis is slow**
- First run downloads librosa data (~10MB); subsequent runs are faster
- Demucs stem separation takes 30-60s per song on CPU; results are cached
- Without optional deps, analysis takes ~5s per song

**Generated sequence looks wrong in xLights**
- The `.xsq` is a starting point — tweak effects, timing, and palettes in xLights
- Use `inspect_sequence` to review what was generated before opening

**FPP connection fails**
- Verify FPP is powered on and on the same network
- Check the hostname/IP in `~/.xlights-mcp/config.json`
- FPP tools gracefully report connection errors; core generation works fully offline

---

## License

MIT

### Audio-analysis research provenance

The deterministic audio capabilities were compared with
[twinklr at commit `59bd7e4`](https://github.com/bluewatersql/twinklr/tree/59bd7e4e59c3a45aa812fe03e516b6a7237a224d/packages/twinklr/core/audio).
That snapshot has no identified license granting source-code reuse. This project
therefore implements standard DSP techniques independently using
[librosa's documented APIs](https://librosa.org/doc/latest/), rather than copying
or translating twinklr source, tests, bespoke scoring rules, or tuned constants.
Twinklr is not a dependency, and this acknowledgment does not grant rights to its
code. Its LLM profiling, remote lyrics/metadata services, and optional MIR model
backends are not included.
