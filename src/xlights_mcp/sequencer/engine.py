"""Sequence generation engine — orchestrates audio analysis → effect placement → .xsq output."""

from __future__ import annotations

import logging
from pathlib import Path

from xlights_mcp.audio.analyzer import SongAnalysis, full_analysis
from xlights_mcp.audio.structure import SongSection
from xlights_mcp.config import AudioConfig
from xlights_mcp.xlights.effects import get_effects_for_model, get_effects_for_musical_feature
from xlights_mcp.xlights.models import LightModel, ShowConfig
from xlights_mcp.xlights.palettes import ColorPalette, get_theme_palettes
from xlights_mcp.xlights.show import load_show_config
from xlights_mcp.xlights.xsq_writer import EffectPlacement, SequenceSpec, write_xsq

logger = logging.getLogger(__name__)

# Default effect settings for commonly used effects
DEFAULT_EFFECT_SETTINGS: dict[str, dict[str, str]] = {
    "Shockwave": {
        "E_CHECKBOX_Shockwave_Blend_Edges": "1",
        "E_CHECKBOX_Shockwave_Scale": "0",
        "E_SLIDER_Shockwave_Accel": "0",
        "E_SLIDER_Shockwave_CenterX": "50",
        "E_SLIDER_Shockwave_CenterY": "50",
        "E_SLIDER_Shockwave_End_Radius": "100",
        "E_SLIDER_Shockwave_End_Width": "5",
        "E_SLIDER_Shockwave_Start_Radius": "1",
        "E_SLIDER_Shockwave_Start_Width": "10",
    },
    "Morph": {
        "E_CHECKBOX_Morph_End_Link": "0",
        "E_CHECKBOX_Morph_Start_Link": "0",
        "E_CHECKBOX_ShowHeadAtStart": "0",
        "E_SLIDER_MorphAccel": "0",
        "E_SLIDER_MorphDuration": "0",
        "E_SLIDER_MorphEndLength": "1",
        "E_SLIDER_MorphStartLength": "1",
    },
    "SingleStrand": {
        "E_CHECKBOX_Chase_Group_All": "0",
        "E_CHOICE_Chase_Type1": "From Middle",
        "E_CHOICE_Fade_Type": "None",
        "E_CHOICE_SingleStrand_Colors": "Palette",
        "E_CHOICE_Skips_Direction": "Left",
        "E_NOTEBOOK_SingleStrand": "Chase",
    },
    "Twinkle": {
        "E_CHECKBOX_Twinkle_ReRandom": "0",
        "E_CHECKBOX_Twinkle_Strobe": "0",
        "E_CHOICE_Twinkle_Style": "New Render Method",
        "E_SLIDER_Twinkle_Count": "3",
        "E_SLIDER_Twinkle_Steps": "14",
    },
    "Plasma": {
        "E_CHOICE_Plasma_Color": "Normal",
        "E_SLIDER_Plasma_Line_Density": "1",
        "E_SLIDER_Plasma_Speed": "10",
        "E_SLIDER_Plasma_Style": "1",
    },
    "Meteors": {
        "E_CHECKBOX_Meteors_UseMusic": "0",
        "E_CHOICE_Meteors_Effect": "Explode",
        "E_CHOICE_Meteors_Type": "Palette",
        "E_SLIDER_Meteors_Count": "22",
        "E_SLIDER_Meteors_Length": "25",
        "E_SLIDER_Meteors_Speed": "20",
    },
    "On": {},
    "ColorWash": {},
    "Chase": {
        "E_CHOICE_Chase_Type1": "From Middle",
        "E_SLIDER_Chase_Rotations": "10",
    },
    "Circles": {
        "E_CHECKBOX_Circles_Bounce": "0",
        "E_CHECKBOX_Circles_Bubbles": "1",
        "E_CHECKBOX_Circles_Collide": "0",
        "E_CHECKBOX_Circles_Linear_Fade": "1",
        "E_CHECKBOX_Circles_Plasma": "0",
        "E_CHECKBOX_Circles_Radial": "0",
    },
    "Pinwheel": {
        "E_SLIDER_Pinwheel_Arms": "3",
        "E_SLIDER_Pinwheel_ArmSize": "50",
        "E_SLIDER_Pinwheel_Twist": "30",
        "E_SLIDER_Pinwheel_Speed": "10",
    },
    "Shimmer": {},
    "Marquee": {},
}


def generate_sequence(
    mp3_path: Path,
    show_path: Path | None,
    mode: str = "auto",
    palette_hint: str | None = None,
    theme: str | None = None,
    audio_config: AudioConfig | None = None,
) -> dict:
    """Generate a complete xLights sequence from a music file.

    Args:
        mp3_path: Path to the .mp3 file
        show_path: Path to the xLights show folder
        mode: "auto", "guided", or "template"
        palette_hint: Color hint string
        theme: Theme hint string
        audio_config: Audio settings
    """
    if not show_path or not show_path.exists():
        return {"error": f"Show path not found: {show_path}"}

    # Load show configuration
    show_config = load_show_config(show_path)
    if not show_config.models:
        return {"error": "No models found in show configuration"}

    # Analyze the audio
    analysis = full_analysis(mp3_path, audio_config)

    if mode == "auto":
        return _generate_auto(analysis, show_config, mp3_path, palette_hint, theme)
    elif mode == "guided":
        return _generate_guided_preview(analysis, show_config)
    elif mode == "template":
        return {"error": "Template mode not yet implemented. Use 'auto' or 'guided'."}
    else:
        return {"error": f"Invalid mode: {mode}"}


def preview_sequence_plan(
    mp3_path: Path,
    show_path: Path | None,
    mode: str = "auto",
    audio_config: AudioConfig | None = None,
) -> dict:
    """Preview what a sequence would look like without generating."""
    if not show_path or not show_path.exists():
        return {"error": f"Show path not found: {show_path}"}

    analysis = full_analysis(mp3_path, audio_config)
    show_config = load_show_config(show_path)

    sections_summary = []
    for s in analysis.sections:
        sections_summary.append({
            "label": s.label,
            "start": f"{s.start_time:.1f}s",
            "end": f"{s.end_time:.1f}s",
            "duration": f"{s.duration:.1f}s",
            "energy": f"{s.energy_level:.2f}",
        })

    return {
        "song": mp3_path.stem,
        "duration": f"{analysis.duration_seconds:.1f}s",
        "tempo": f"{analysis.beats.tempo:.0f} BPM",
        "beat_count": len(analysis.beats.beat_times),
        "sections": sections_summary,
        "models": len(show_config.models),
        "controllers": len(show_config.controllers),
    }


def _generate_auto(
    analysis: SongAnalysis,
    show_config: ShowConfig,
    mp3_path: Path,
    palette_hint: str | None,
    theme: str | None,
) -> dict:
    """Fully automatic sequence generation."""
    # Select palettes based on theme
    theme_palettes = get_theme_palettes(theme)
    palette_names = list(theme_palettes.keys())

    # Build palette list for the sequence
    palettes: list[ColorPalette] = []
    effects: list[EffectPlacement] = []

    # Assign palettes to sections
    section_palettes: dict[str, ColorPalette] = {}
    for i, section in enumerate(analysis.sections):
        pname = palette_names[i % len(palette_names)]
        pal = theme_palettes[pname]
        section_palettes[f"{section.label}_{i}"] = pal
        if pal not in palettes:
            palettes.append(pal)

    # Generate effects for each model × section
    for model in show_config.models:
        model_effects = get_effects_for_model(model.model_category)
        if not model_effects:
            continue

        for i, section in enumerate(analysis.sections):
            section_key = f"{section.label}_{i}"
            palette = section_palettes.get(section_key, palettes[0] if palettes else ColorPalette())

            # Pick musical features for this section
            musical_features = _section_to_musical_features(section)

            # Pick effect based on model type + musical features
            effect_name = _pick_effect(model, musical_features, model_effects)

            # Get beat-aligned timing within the section
            section_effects = _place_effects_in_section(
                model=model,
                effect_name=effect_name,
                section=section,
                analysis=analysis,
                palette=palette,
            )
            effects.extend(section_effects)

    # Build the sequence spec
    spec = SequenceSpec(
        song_title=mp3_path.stem,
        artist="",
        album="",
        media_file=str(mp3_path),
        duration_ms=analysis.duration_ms,
        timing_ms=25,
        palettes=palettes,
        effects=effects,
    )

    # Write the .xsq file
    output_path = Path(show_config.show_path) / f"{mp3_path.stem}.xsq"
    write_xsq(spec, show_config, output_path)

    return {
        "success": True,
        "output_path": str(output_path),
        "song": mp3_path.stem,
        "duration": f"{analysis.duration_seconds:.1f}s",
        "tempo": f"{analysis.beats.tempo:.0f} BPM",
        "sections": len(analysis.sections),
        "models_with_effects": len(show_config.models),
        "total_effects": len(effects),
        "message": f"Sequence created: {output_path.name}. Open in xLights to preview and render.",
    }


def _generate_guided_preview(analysis: SongAnalysis, show_config: ShowConfig) -> dict:
    """Return analysis for guided/interactive mode."""
    sections = []
    for i, s in enumerate(analysis.sections):
        sections.append({
            "index": i,
            "label": s.label,
            "start_time": f"{s.start_time:.1f}s",
            "end_time": f"{s.end_time:.1f}s",
            "energy": f"{s.energy_level:.2f}",
            "suggested_effects": get_effects_for_musical_feature(s.label),
        })

    models_by_category = {}
    for m in show_config.models:
        cat = m.model_category
        models_by_category.setdefault(cat, []).append(m.name)

    return {
        "mode": "guided",
        "message": "Here's the song analysis. Tell me which effects you want for each section.",
        "song_info": {
            "tempo": f"{analysis.beats.tempo:.0f} BPM",
            "duration": f"{analysis.duration_seconds:.1f}s",
            "beat_count": len(analysis.beats.beat_times),
        },
        "sections": sections,
        "models_by_category": models_by_category,
    }


def _section_to_musical_features(section: SongSection) -> list[str]:
    """Map a song section to musical feature tags for effect selection."""
    features = [section.label]  # "verse", "chorus", etc.

    if section.energy_level > 0.7:
        features.append("high_energy")
    elif section.energy_level < 0.3:
        features.append("low_energy")

    if section.label in ("intro",):
        features.append("intro")
    elif section.label in ("outro",):
        features.append("outro")

    return features


def _pick_effect(
    model: LightModel,
    musical_features: list[str],
    model_effects: list[str],
) -> str:
    """Pick the best effect for a model given musical features."""
    # Score effects by how many musical features they match
    scores: dict[str, int] = {}
    for feature in musical_features:
        feature_effects = get_effects_for_musical_feature(feature)
        for eff in feature_effects:
            if eff in model_effects:
                scores[eff] = scores.get(eff, 0) + 1

    if scores:
        return max(scores, key=scores.get)

    # Fallback to first model-compatible effect
    return model_effects[0] if model_effects else "ColorWash"


def _place_effects_in_section(
    model: LightModel,
    effect_name: str,
    section: SongSection,
    analysis: SongAnalysis,
    palette: ColorPalette,
) -> list[EffectPlacement]:
    """Place effects within a section, aligned to beats where appropriate."""
    effects: list[EffectPlacement] = []
    settings = DEFAULT_EFFECT_SETTINGS.get(effect_name, {}).copy()

    # Quick/punchy effects get placed on individual beats
    beat_effects = {"Shockwave", "Morph", "Strobe"}
    # Sustained effects span the entire section
    sustained_effects = {"Plasma", "ColorWash", "Twinkle", "On", "Circles", "Pinwheel",
                         "Galaxy", "Butterfly", "Shimmer", "Snowflakes", "Fire"}

    if effect_name in beat_effects:
        # Place on beats within this section
        section_beats = [
            b for b in analysis.beats.beat_times
            if section.start_time <= b < section.end_time
        ]
        for beat_time in section_beats:
            beat_ms = int(beat_time * 1000)
            # Short burst: ~200ms per beat hit
            effects.append(EffectPlacement(
                model_name=model.name,
                effect_name=effect_name,
                start_time_ms=beat_ms,
                end_time_ms=beat_ms + 200,
                settings=settings,
                palette=palette,
            ))

    elif effect_name in sustained_effects:
        # Span the entire section
        effects.append(EffectPlacement(
            model_name=model.name,
            effect_name=effect_name,
            start_time_ms=section.start_time_ms,
            end_time_ms=section.end_time_ms,
            settings=settings,
            palette=palette,
        ))

    else:
        # Rhythmic effects: place between downbeats
        section_downbeats = [
            b for b in analysis.beats.downbeat_times
            if section.start_time <= b < section.end_time
        ]
        if len(section_downbeats) >= 2:
            for j in range(len(section_downbeats) - 1):
                start_ms = int(section_downbeats[j] * 1000)
                end_ms = int(section_downbeats[j + 1] * 1000)
                effects.append(EffectPlacement(
                    model_name=model.name,
                    effect_name=effect_name,
                    start_time_ms=start_ms,
                    end_time_ms=end_ms,
                    settings=settings,
                    palette=palette,
                ))
        else:
            # Fallback: span the section
            effects.append(EffectPlacement(
                model_name=model.name,
                effect_name=effect_name,
                start_time_ms=section.start_time_ms,
                end_time_ms=section.end_time_ms,
                settings=settings,
                palette=palette,
            ))

    return effects
