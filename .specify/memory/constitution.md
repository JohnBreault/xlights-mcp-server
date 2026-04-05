# xLights MCP Server Constitution

## Core Principles

### I. Model-Agnostic Design
All features must work with any xLights show configuration. Never hardcode model names, group patterns, or controller-specific logic. Detect capabilities from the show XML (display_as, face_definitions, model groups) and adapt automatically.

### II. Musical Fidelity
Every effect placement must be justified by audio analysis data — beats, onsets, stem energy, section structure, or frequency bands. No arbitrary timing. Sequences should look intentionally choreographed to the music when viewed in xLights.

### III. Never Destructive
Never overwrite existing .xsq files. Generated sequences get incremented suffixes. Stem separation results and audio analysis are cached. User show configurations are read-only.

### IV. Professional Quality Output
Generated sequences should match the quality expectations of the xLights community. Effects must use correct xLights parameter names and valid value ranges. XML output must open cleanly in xLights without errors.

### V. Graceful Degradation
Optional dependencies (Demucs, Whisper, madmom) enhance quality but must never block core functionality. If stem separation fails, use full-mix analysis. If lyrics fail, skip singing faces. Always produce a usable sequence.

## Technical Constraints

- Python 3.11+ with type annotations throughout
- Pydantic models for all data structures crossing module boundaries
- MCP protocol via FastMCP — tools must return dicts, not raise exceptions
- Audio analysis via librosa (core), Demucs (stems), Whisper (lyrics)
- xLights XML format must match the output of xLights 2024+ exactly

## Quality Standards

- Effect variety: no model should have the same effect for more than 2 consecutive sections
- Palette variety: colors must change at least every 2 sections
- Layer separation: bed (L0), motion (L1), and accent (L2) must serve distinct visual purposes
- Singing models get dedicated layers — never mix regular effects with Faces

## Governance

This constitution governs all spec-driven development on this project. Feature specs must demonstrate compliance with these principles before implementation begins.

**Version**: 1.0.0 | **Ratified**: 2026-04-05
