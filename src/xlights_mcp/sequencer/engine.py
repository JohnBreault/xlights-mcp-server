"""Sequence generation engine — orchestrates audio analysis → effect placement → .xsq output.

Architecture: 3-layer approach matching professional sequencing patterns:
  Layer 0 (background bed): Sustained effects that run the full section — twinkle, color wash, plasma
  Layer 1 (mid-layer motion): Rhythmic/directional effects synced to downbeats — chase, spirals
  Layer 2 (accent hits): Punchy effects on select beats — shockwave, morph, strobe

Models are assigned ROLES based on their physical type:
  - House outline/rooflines → bass pulse, slow morphs
  - Arches / candy canes → rhythmic chases, mirrored directions
  - Tree → spirals, pinwheels, meteors
  - Custom props → shockwaves, circles, warp
  - Windows / doors → marquee, color wash
  - Flakes / spinners → twinkle, shimmer, pinwheel

Palettes cycle per phrase (every 2-4 bars) for variety, not just per section.
"""

from __future__ import annotations

import logging
import random
from pathlib import Path

from xlights_mcp.audio.analyzer import SongAnalysis, full_analysis
from xlights_mcp.audio.structure import SongSection
from xlights_mcp.config import AudioConfig
from xlights_mcp.xlights.models import LightModel, ShowConfig
from xlights_mcp.xlights.palettes import ColorPalette, get_theme_palettes
from xlights_mcp.xlights.show import load_show_config
from xlights_mcp.xlights.xsq_writer import (
    EffectPlacement, SequenceSpec, TimingTrack, TimingTrackLabel, write_xsq,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Professional effect settings — extracted from real human-made sequences
# Multiple variants per effect type for variety
# ---------------------------------------------------------------------------

EFFECT_VARIANTS: dict[str, list[dict[str, str]]] = {
    "Shockwave_hit": [
        # Big expanding shockwave for impact moments
        {"E_CHECKBOX_Shockwave_Blend_Edges": "1", "E_CHECKBOX_Shockwave_Scale": "0",
         "E_SLIDER_Shockwave_Accel": "3", "E_SLIDER_Shockwave_CenterX": "50",
         "E_SLIDER_Shockwave_CenterY": "50", "E_SLIDER_Shockwave_End_Radius": "100",
         "E_SLIDER_Shockwave_End_Width": "5", "E_SLIDER_Shockwave_Start_Radius": "1",
         "E_SLIDER_Shockwave_Start_Width": "25"},
        # Tight imploding shockwave
        {"E_CHECKBOX_Shockwave_Blend_Edges": "1", "E_CHECKBOX_Shockwave_Scale": "0",
         "E_SLIDER_Shockwave_Accel": "0", "E_SLIDER_Shockwave_CenterX": "50",
         "E_SLIDER_Shockwave_CenterY": "50", "E_SLIDER_Shockwave_End_Radius": "0",
         "E_SLIDER_Shockwave_End_Width": "25", "E_SLIDER_Shockwave_Start_Radius": "100",
         "E_SLIDER_Shockwave_Start_Width": "5"},
        # Wide dramatic shockwave
        {"E_CHECKBOX_Shockwave_Blend_Edges": "1", "E_CHECKBOX_Shockwave_Scale": "0",
         "E_SLIDER_Shockwave_Accel": "0", "E_SLIDER_Shockwave_CenterX": "50",
         "E_SLIDER_Shockwave_CenterY": "50", "E_SLIDER_Shockwave_End_Radius": "245",
         "E_SLIDER_Shockwave_End_Width": "50", "E_SLIDER_Shockwave_Start_Radius": "1",
         "E_SLIDER_Shockwave_Start_Width": "10"},
    ],
    "Chase_left": [
        {"B_CHOICE_BufferStyle": "Per Model Single Line", "E_CHECKBOX_Chase_Group_All": "0",
         "E_CHOICE_Chase_Type1": "Left-Right", "E_CHOICE_Fade_Type": "None",
         "E_CHOICE_SingleStrand_Colors": "Palette", "E_NOTEBOOK_SSEFFECT_TYPE": "Chase",
         "E_SLIDER_Color_Mix1": "36", "E_SLIDER_Number_Chases": "1",
         "E_SLIDER_Chase_Rotations": "1"},
    ],
    "Chase_right": [
        {"B_CHOICE_BufferStyle": "Per Model Single Line", "E_CHECKBOX_Chase_Group_All": "0",
         "E_CHOICE_Chase_Type1": "Right-Left", "E_CHOICE_Fade_Type": "None",
         "E_CHOICE_SingleStrand_Colors": "Palette", "E_NOTEBOOK_SSEFFECT_TYPE": "Chase",
         "E_SLIDER_Color_Mix1": "36", "E_SLIDER_Number_Chases": "1",
         "E_SLIDER_Chase_Rotations": "1"},
    ],
    "Chase_from_middle": [
        {"B_CHOICE_BufferStyle": "Per Model Single Line", "E_CHECKBOX_Chase_Group_All": "0",
         "E_CHOICE_Chase_Type1": "From Middle", "E_CHOICE_Fade_Type": "None",
         "E_CHOICE_SingleStrand_Colors": "Palette", "E_NOTEBOOK_SSEFFECT_TYPE": "Chase",
         "E_SLIDER_Color_Mix1": "36", "E_SLIDER_Number_Chases": "1",
         "E_SLIDER_Chase_Rotations": "1"},
    ],
    "Chase_bounce": [
        {"B_CHOICE_BufferStyle": "Per Model Single Line", "E_CHECKBOX_Chase_Group_All": "0",
         "E_CHOICE_Chase_Type1": "Bounce from Left", "E_CHOICE_Fade_Type": "None",
         "E_CHOICE_SingleStrand_Colors": "Palette", "E_NOTEBOOK_SSEFFECT_TYPE": "Chase",
         "E_SLIDER_Color_Mix1": "36", "E_SLIDER_Number_Chases": "1",
         "E_SLIDER_Chase_Rotations": "1"},
    ],
    "Morph_quick": [
        {"E_CHECKBOX_Morph_End_Link": "0", "E_CHECKBOX_Morph_Start_Link": "0",
         "E_CHECKBOX_ShowHeadAtStart": "0", "E_SLIDER_MorphAccel": "0",
         "E_SLIDER_MorphDuration": "20", "E_SLIDER_MorphEndLength": "1",
         "E_SLIDER_MorphStartLength": "1", "E_SLIDER_Morph_End_X1": "0",
         "E_SLIDER_Morph_End_Y1": "0", "E_SLIDER_Morph_Start_X1": "100",
         "E_SLIDER_Morph_Start_Y1": "100"},
        {"E_CHECKBOX_Morph_End_Link": "0", "E_CHECKBOX_Morph_Start_Link": "0",
         "E_CHECKBOX_ShowHeadAtStart": "0", "E_SLIDER_MorphAccel": "0",
         "E_SLIDER_MorphDuration": "20", "E_SLIDER_MorphEndLength": "1",
         "E_SLIDER_MorphStartLength": "1", "E_SLIDER_Morph_End_X1": "100",
         "E_SLIDER_Morph_End_Y1": "100", "E_SLIDER_Morph_Start_X1": "0",
         "E_SLIDER_Morph_Start_Y1": "0"},
    ],
    "Twinkle_ambient": [
        {"E_CHECKBOX_Twinkle_ReRandom": "0", "E_CHECKBOX_Twinkle_Strobe": "0",
         "E_CHOICE_Twinkle_Style": "New Render Method",
         "E_SLIDER_Twinkle_Count": "3", "E_SLIDER_Twinkle_Steps": "14",
         "T_TEXTCTRL_Fadein": "0.5", "T_TEXTCTRL_Fadeout": "1.0"},
    ],
    "Twinkle_dense": [
        {"E_CHECKBOX_Twinkle_ReRandom": "0", "E_CHECKBOX_Twinkle_Strobe": "0",
         "E_CHOICE_Twinkle_Style": "New Render Method",
         "E_SLIDER_Twinkle_Count": "36", "E_SLIDER_Twinkle_Steps": "10",
         "T_TEXTCTRL_Fadein": "0.2", "T_TEXTCTRL_Fadeout": "0.5"},
    ],
    "ColorWash_slow": [
        {"E_CHECKBOX_ColorWash_CircularPalette": "1", "E_TEXTCTRL_ColorWash_Cycles": "1",
         "T_TEXTCTRL_Fadein": "1.0", "T_TEXTCTRL_Fadeout": "1.0"},
    ],
    "ColorWash_fast": [
        {"E_CHECKBOX_ColorWash_CircularPalette": "1", "E_TEXTCTRL_ColorWash_Cycles": "3"},
    ],
    "ColorWash_cycling": [
        {"E_CHECKBOX_ColorWash_CircularPalette": "1", "E_TEXTCTRL_ColorWash_Cycles": "20.0",
         "T_TEXTCTRL_Fadein": "2.5"},
    ],
    "Plasma_slow": [
        {"E_CHOICE_Plasma_Color": "Normal", "E_SLIDER_Plasma_Line_Density": "1",
         "E_SLIDER_Plasma_Speed": "10", "E_SLIDER_Plasma_Style": "10",
         "T_TEXTCTRL_Fadein": "0.5", "T_TEXTCTRL_Fadeout": "0.5"},
    ],
    "Plasma_fast": [
        {"E_CHOICE_Plasma_Color": "Normal", "E_SLIDER_Plasma_Line_Density": "1",
         "E_SLIDER_Plasma_Speed": "80", "E_SLIDER_Plasma_Style": "10",
         "T_TEXTCTRL_Fadein": "0.25", "T_TEXTCTRL_Fadeout": "0.25"},
    ],
    "Spirals_slow": [
        {"E_CHECKBOX_Spirals_3D": "1", "E_CHECKBOX_Spirals_Blend": "0",
         "E_CHECKBOX_Spirals_Grow": "0", "E_CHECKBOX_Spirals_Shrink": "0",
         "E_SLIDER_Spirals_Count": "1", "E_SLIDER_Spirals_Rotation": "20",
         "E_SLIDER_Spirals_Thickness": "50", "E_TEXTCTRL_Spirals_Movement": "1.0",
         "T_TEXTCTRL_Fadein": "0.5", "T_TEXTCTRL_Fadeout": "0.5"},
    ],
    "Spirals_fast": [
        {"E_CHECKBOX_Spirals_3D": "1", "E_CHECKBOX_Spirals_Blend": "0",
         "E_CHECKBOX_Spirals_Grow": "0", "E_CHECKBOX_Spirals_Shrink": "0",
         "E_SLIDER_Spirals_Count": "5", "E_SLIDER_Spirals_Rotation": "20",
         "E_SLIDER_Spirals_Thickness": "18", "E_TEXTCTRL_Spirals_Movement": "3.0"},
    ],
    "Spirals_reverse": [
        {"E_CHECKBOX_Spirals_3D": "1", "E_CHECKBOX_Spirals_Blend": "0",
         "E_CHECKBOX_Spirals_Grow": "0", "E_CHECKBOX_Spirals_Shrink": "0",
         "E_SLIDER_Spirals_Count": "1", "E_SLIDER_Spirals_Rotation": "-20",
         "E_SLIDER_Spirals_Thickness": "50", "E_TEXTCTRL_Spirals_Movement": "-1.0"},
    ],
    "Meteors_explode": [
        {"E_CHECKBOX_Meteors_UseMusic": "0", "E_CHOICE_Meteors_Effect": "Explode",
         "E_CHOICE_Meteors_Type": "Palette", "E_SLIDER_Meteors_Count": "5",
         "E_SLIDER_Meteors_Length": "25", "E_SLIDER_Meteors_Speed": "10",
         "E_SLIDER_Meteors_Swirl_Intensity": "0"},
    ],
    "Meteors_rain": [
        {"E_CHECKBOX_Meteors_UseMusic": "0", "E_CHOICE_Meteors_Effect": "Down",
         "E_CHOICE_Meteors_Type": "Palette", "E_SLIDER_Meteors_Count": "10",
         "E_SLIDER_Meteors_Length": "25", "E_SLIDER_Meteors_Speed": "15",
         "E_SLIDER_Meteors_Swirl_Intensity": "0"},
    ],
    "Pinwheel_sweep": [
        {"E_CHECKBOX_Pinwheel_Rotation": "1", "E_CHOICE_Pinwheel_3D": "Sweep",
         "E_CHOICE_Pinwheel_Style": "New Render Method",
         "E_SLIDER_Pinwheel_ArmSize": "150", "E_SLIDER_Pinwheel_Arms": "10",
         "E_SLIDER_Pinwheel_Speed": "5", "E_SLIDER_Pinwheel_Twist": "60"},
    ],
    "Butterfly_gentle": [
        {"E_CHOICE_Butterfly_Colors": "Palette", "E_CHOICE_Butterfly_Direction": "Normal",
         "E_SLIDER_Butterfly_Chunks": "1", "E_SLIDER_Butterfly_Skip": "2",
         "E_SLIDER_Butterfly_Speed": "10", "E_SLIDER_Butterfly_Style": "1",
         "T_TEXTCTRL_Fadein": "0.25", "T_TEXTCTRL_Fadeout": "0.25"},
    ],
    "Warp_mirror": [
        {"E_CHOICE_Warp_Treatment_APPLYLAST": "constant", "E_CHOICE_Warp_Type": "mirror",
         "E_SLIDER_Warp_X": "50", "E_SLIDER_Warp_Y": "50"},
    ],
    "Warp_wavy": [
        {"E_CHOICE_Warp_Treatment_APPLYLAST": "constant", "E_CHOICE_Warp_Type": "wavy",
         "E_SLIDER_Warp_Speed": "40"},
    ],
    "Marquee_default": [
        {"E_SLIDER_Marquee_Band_Size": "3", "E_SLIDER_Marquee_Skip_Size": "3",
         "E_SLIDER_Marquee_Speed": "3", "E_SLIDER_Marquee_Stagger": "0"},
    ],
    "On_solid": [{}],
}


# ---------------------------------------------------------------------------
# Model role assignments — what role each model type plays in the show
# ---------------------------------------------------------------------------

# Background bed effects per model category (Layer 0)
BED_EFFECTS: dict[str, list[str]] = {
    "arch": ["ColorWash_slow", "Twinkle_ambient"],
    "tree": ["Spirals_slow", "Plasma_slow", "ColorWash_cycling"],
    "single_line": ["ColorWash_slow", "Twinkle_ambient"],
    "poly_line": ["ColorWash_slow", "Twinkle_ambient"],
    "window": ["ColorWash_slow", "On_solid"],
    "custom": ["Twinkle_ambient", "ColorWash_slow", "Butterfly_gentle"],
    "other": ["ColorWash_slow", "Twinkle_ambient"],
}

# Mid-layer motion effects per model category (Layer 1) — synced to bars/downbeats
MOTION_EFFECTS: dict[str, list[str]] = {
    "arch": ["Chase_from_middle", "Chase_left", "Chase_right", "Chase_bounce"],
    "tree": ["Spirals_fast", "Spirals_reverse", "Pinwheel_sweep", "Meteors_rain"],
    "single_line": ["Chase_left", "Chase_right", "Chase_bounce"],
    "poly_line": ["Chase_left", "Chase_right", "Chase_from_middle"],
    "window": ["Marquee_default"],
    "custom": ["Plasma_fast", "Warp_mirror", "Warp_wavy"],
    "other": ["Chase_from_middle", "ColorWash_fast"],
}

# Accent effects per model category (Layer 2) — on select beats only
ACCENT_EFFECTS: dict[str, list[str]] = {
    "arch": ["Morph_quick", "Shockwave_hit"],
    "tree": ["Shockwave_hit", "Meteors_explode"],
    "single_line": ["Morph_quick"],
    "poly_line": ["Morph_quick"],
    "window": ["Shockwave_hit"],
    "custom": ["Shockwave_hit", "Morph_quick"],
    "other": ["Shockwave_hit"],
}

# Section energy thresholds
HIGH_ENERGY_THRESHOLD = 0.65
LOW_ENERGY_THRESHOLD = 0.35


# ---------------------------------------------------------------------------
# Model grouping — auto-detect groups from model names
# ---------------------------------------------------------------------------

# Patterns to detect model groups: (group_name, name_patterns, model_category_override)
MODEL_GROUP_PATTERNS: list[tuple[str, list[str], str | None]] = [
    ("canes", ["Left Cane", "Right Cane"], "arch"),
    ("arches", ["Arches-"], "arch"),
    ("flakes", ["Flake "], "custom"),
    ("spinners", ["Spinner "], "custom"),
    ("rooflines", ["Roofline", "Roof Peak", "Garage Roofline", "Porch Roofline"], "single_line"),
    ("pillars", ["Pillar"], "single_line"),
    ("windows_doors", ["Window", "Door"], "window"),
    ("bulbs", ["Bulb "], "custom"),
]


def _detect_model_groups(models: list[LightModel]) -> tuple[
    dict[str, list[LightModel]],  # group_name → member models
    list[LightModel],              # ungrouped models
    dict[str, str],                # group_name → model_category
]:
    """Auto-detect model groups from naming patterns.

    Returns grouped models (effects applied identically to all members),
    ungrouped models (effects applied individually), and category overrides.
    """
    groups: dict[str, list[LightModel]] = {}
    group_categories: dict[str, str] = {}
    grouped_names: set[str] = set()

    for group_name, patterns, cat_override in MODEL_GROUP_PATTERNS:
        members = []
        for model in models:
            for pattern in patterns:
                if model.name.startswith(pattern) or pattern in model.name:
                    members.append(model)
                    grouped_names.add(model.name)
                    break
        if members:
            groups[group_name] = members
            if cat_override:
                group_categories[group_name] = cat_override
            else:
                group_categories[group_name] = members[0].model_category

    ungrouped = [m for m in models if m.name not in grouped_names]
    return groups, ungrouped, group_categories


def generate_sequence(
    mp3_path: Path,
    show_path: Path | None,
    mode: str = "auto",
    palette_hint: str | None = None,
    theme: str | None = None,
    audio_config: AudioConfig | None = None,
) -> dict:
    """Generate a complete xLights sequence from a music file."""
    if not show_path or not show_path.exists():
        return {"error": f"Show path not found: {show_path}"}

    show_config = load_show_config(show_path)
    if not show_config.models:
        return {"error": "No models found in show configuration"}

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


# ---------------------------------------------------------------------------
# Auto-generation engine
# ---------------------------------------------------------------------------


def _generate_auto(
    analysis: SongAnalysis,
    show_config: ShowConfig,
    mp3_path: Path,
    palette_hint: str | None,
    theme: str | None,
) -> dict:
    """Professional-quality automatic sequence generation.

    Uses a 3-layer approach with model group synchronization:
      Layer 0: Background bed (twinkle, wash) — runs full section
      Layer 1: Motion (chase, spirals) — synced to bars
      Layer 2: Accent hits (shockwave, morph) — on select downbeats only

    Grouped models (canes, arches, etc.) get identical effects for synchronization.
    """
    rng = random.Random(hash(mp3_path.stem))  # deterministic per song

    # Build palette pool
    theme_palettes = get_theme_palettes(theme)
    palette_pool = list(theme_palettes.values())
    if not palette_pool:
        palette_pool = [ColorPalette(colors=["#FFFFFF"], active_colors=[1])]

    all_palettes: list[ColorPalette] = list(palette_pool)
    all_effects: list[EffectPlacement] = []

    # Pre-compute beats within each section
    section_beats = _precompute_section_beats(analysis)
    section_downbeats = _precompute_section_downbeats(analysis)

    # Detect model groups
    groups, ungrouped, group_categories = _detect_model_groups(show_config.models)
    logger.info(f"Detected {len(groups)} model groups, {len(ungrouped)} ungrouped models")
    for gname, members in groups.items():
        logger.info(f"  Group '{gname}': {[m.name for m in members]}")

    # Helper to generate effects for a model category and apply to a list of model names
    def generate_for_models(model_names: list[str], cat: str, group_seed: str):
        group_rng = random.Random(hash(group_seed + mp3_path.stem))

        for sec_idx, section in enumerate(analysis.sections):
            is_high = section.energy_level >= HIGH_ENERGY_THRESHOLD
            is_low = section.energy_level < LOW_ENERGY_THRESHOLD
            is_intro = section.label == "intro" or (sec_idx == 0 and section.duration < 15)
            is_outro = section.label == "outro" or (sec_idx == len(analysis.sections) - 1)

            pal_idx = (sec_idx // 2 + hash(group_seed)) % len(palette_pool)
            palette = palette_pool[pal_idx]

            downbeats_in_section = section_downbeats.get(sec_idx, [])

            # --- LAYER 0: Background bed ---
            bed_choices = BED_EFFECTS.get(cat, BED_EFFECTS["other"])
            if is_high:
                bed_key = "Twinkle_dense" if "Twinkle_ambient" in bed_choices else bed_choices[0]
            elif is_intro or is_outro:
                bed_key = "ColorWash_slow"
            else:
                bed_key = group_rng.choice(bed_choices)

            bed_settings = _get_settings(bed_key)
            for name in model_names:
                all_effects.append(EffectPlacement(
                    model_name=name, layer=0,
                    effect_name=_effect_name_from_key(bed_key),
                    start_time_ms=section.start_time_ms,
                    end_time_ms=section.end_time_ms,
                    settings=bed_settings, palette=palette,
                ))

            # --- LAYER 1: Motion (skip for intro/outro/low energy) ---
            if not is_intro and not is_outro and not is_low:
                motion_choices = MOTION_EFFECTS.get(cat, MOTION_EFFECTS["other"])
                if cat in ("arch", "single_line", "poly_line") and len(motion_choices) > 1:
                    motion_key = motion_choices[sec_idx % len(motion_choices)]
                else:
                    motion_key = group_rng.choice(motion_choices)

                motion_settings = _get_settings(motion_key)

                if len(downbeats_in_section) >= 2:
                    for j in range(len(downbeats_in_section) - 1):
                        start_ms = int(downbeats_in_section[j] * 1000)
                        end_ms = int(downbeats_in_section[j + 1] * 1000)
                        motion_pal_idx = (pal_idx + j // 2) % len(palette_pool)
                        for name in model_names:
                            all_effects.append(EffectPlacement(
                                model_name=name, layer=1,
                                effect_name=_effect_name_from_key(motion_key),
                                start_time_ms=start_ms, end_time_ms=end_ms,
                                settings=motion_settings,
                                palette=palette_pool[motion_pal_idx],
                            ))
                else:
                    for name in model_names:
                        all_effects.append(EffectPlacement(
                            model_name=name, layer=1,
                            effect_name=_effect_name_from_key(motion_key),
                            start_time_ms=section.start_time_ms,
                            end_time_ms=section.end_time_ms,
                            settings=motion_settings, palette=palette,
                        ))

            # --- LAYER 2: Accent hits (high energy only, selective beats) ---
            if is_high and downbeats_in_section:
                accent_choices = ACCENT_EFFECTS.get(cat, ACCENT_EFFECTS["other"])
                accent_key = group_rng.choice(accent_choices)
                accent_settings = _get_settings(accent_key)

                accent_interval = 2 if section.energy_level > 0.85 else 4
                for j, db_time in enumerate(downbeats_in_section):
                    if j % accent_interval != 0:
                        continue
                    db_ms = int(db_time * 1000)
                    beat_dur_ms = int(60000 / max(analysis.beats.tempo, 60))
                    accent_dur = min(beat_dur_ms, 500)
                    accent_pal_idx = (pal_idx + j) % len(palette_pool)

                    for name in model_names:
                        all_effects.append(EffectPlacement(
                            model_name=name, layer=2,
                            effect_name=_effect_name_from_key(accent_key),
                            start_time_ms=db_ms,
                            end_time_ms=db_ms + accent_dur,
                            settings=accent_settings,
                            palette=palette_pool[accent_pal_idx],
                        ))

    # Process grouped models — all members get identical effects
    for group_name, members in groups.items():
        cat = group_categories[group_name]
        member_names = [m.name for m in members]
        generate_for_models(member_names, cat, group_name)

    # Process ungrouped models individually
    for model in ungrouped:
        generate_for_models([model.name], model.model_category, model.name)

    # --- Singing Faces: extract lyrics and create timing track + Faces effects ---
    timing_tracks: list[TimingTrack] = []
    has_lyrics = False

    # Detect singing models (Snowman, Bulbs)
    singing_models = [m.name for m in show_config.models
                      if any(kw in m.name.lower() for kw in ("snowman", "bulb"))]

    if singing_models:
        lyric_track = _try_extract_lyrics(mp3_path)
        if lyric_track and lyric_track.available and lyric_track.phonemes:
            has_lyrics = True
            track_name = lyric_track.track_name

            # Build timing track with 2 layers: words (L0) + phonemes (L1)
            word_labels = []
            for w in lyric_track.words:
                word_labels.append(TimingTrackLabel(
                    label=w.word,
                    start_time_ms=int(w.start_time * 1000),
                    end_time_ms=int(w.end_time * 1000),
                ))

            phoneme_labels = []
            for p in lyric_track.phonemes:
                phoneme_labels.append(TimingTrackLabel(
                    label=p.phoneme,
                    start_time_ms=p.start_time_ms,
                    end_time_ms=p.end_time_ms,
                ))

            timing_tracks.append(TimingTrack(
                name=track_name,
                labels=[word_labels, phoneme_labels],
            ))

            # Place Faces effect on singing models (spans full song)
            faces_settings = {
                "E_CHECKBOX_Faces_Outline": "1",
                "E_CHOICE_Faces_EyeBlinkDuration": "Normal",
                "E_CHOICE_Faces_EyeBlinkFrequency": "Normal",
                "E_CHOICE_Faces_Eyes": "Auto",
                "E_CHOICE_Faces_TimingTrack": track_name,
                "T_TEXTCTRL_Fadein": "0.5",
                "T_TEXTCTRL_Fadeout": "0.5",
            }
            for model_name in singing_models:
                all_effects.append(EffectPlacement(
                    model_name=model_name,
                    layer=0,  # Faces on base layer
                    effect_name="Faces",
                    start_time_ms=0,
                    end_time_ms=analysis.duration_ms,
                    settings=faces_settings,
                    palette=all_palettes[0] if all_palettes else ColorPalette(),
                ))

            logger.info(f"Added Faces effect on {singing_models} with {len(lyric_track.phonemes)} phonemes")

    # Build sequence spec
    spec = SequenceSpec(
        song_title=mp3_path.stem, artist="", album="",
        media_file=str(mp3_path),
        duration_ms=analysis.duration_ms, timing_ms=25,
        palettes=all_palettes, effects=all_effects,
        timing_tracks=timing_tracks,
    )

    # Write (never overwrite existing)
    base_name = mp3_path.stem
    output_path = Path(show_config.show_path) / f"{base_name}.xsq"
    if output_path.exists():
        counter = 1
        while output_path.exists():
            output_path = Path(show_config.show_path) / f"{base_name} (generated {counter}).xsq"
            counter += 1

    write_xsq(spec, show_config, output_path)

    layers_used = set(e.layer for e in all_effects)

    return {
        "success": True,
        "output_path": str(output_path),
        "song": mp3_path.stem,
        "duration": f"{analysis.duration_seconds:.1f}s",
        "tempo": f"{analysis.beats.tempo:.0f} BPM",
        "sections": len(analysis.sections),
        "models_with_effects": len(show_config.models),
        "total_effects": len(all_effects),
        "layers_used": len(layers_used),
        "unique_palettes": len(all_palettes),
        "model_groups": len(groups),
        "has_lyrics": has_lyrics,
        "singing_models": singing_models if has_lyrics else [],
        "message": f"Sequence created: {output_path.name}. Open in xLights to preview and render.",
    }


# ---------------------------------------------------------------------------
# Guided mode
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_settings(variant_key: str) -> dict[str, str]:
    """Get effect settings for a named variant."""
    variants = EFFECT_VARIANTS.get(variant_key, [{}])
    return variants[0].copy() if variants else {}


def _effect_name_from_key(variant_key: str) -> str:
    """Extract the xLights effect name from a variant key.

    e.g. 'Chase_left' → 'SingleStrand', 'Shockwave_hit' → 'Shockwave'
    """
    key_to_effect = {
        "Shockwave_hit": "Shockwave",
        "Chase_left": "SingleStrand",
        "Chase_right": "SingleStrand",
        "Chase_from_middle": "SingleStrand",
        "Chase_bounce": "SingleStrand",
        "Morph_quick": "Morph",
        "Twinkle_ambient": "Twinkle",
        "Twinkle_dense": "Twinkle",
        "ColorWash_slow": "Color Wash",
        "ColorWash_fast": "Color Wash",
        "ColorWash_cycling": "Color Wash",
        "Plasma_slow": "Plasma",
        "Plasma_fast": "Plasma",
        "Spirals_slow": "Spirals",
        "Spirals_fast": "Spirals",
        "Spirals_reverse": "Spirals",
        "Meteors_explode": "Meteors",
        "Meteors_rain": "Meteors",
        "Pinwheel_sweep": "Pinwheel",
        "Butterfly_gentle": "Butterfly",
        "Warp_mirror": "Warp",
        "Warp_wavy": "Warp",
        "Marquee_default": "Marquee",
        "On_solid": "On",
    }
    return key_to_effect.get(variant_key, variant_key.split("_")[0])


def _precompute_section_beats(analysis: SongAnalysis) -> dict[int, list[float]]:
    """Pre-compute which beats fall in each section."""
    result: dict[int, list[float]] = {}
    for i, section in enumerate(analysis.sections):
        result[i] = [
            b for b in analysis.beats.beat_times
            if section.start_time <= b < section.end_time
        ]
    return result


def _precompute_section_downbeats(analysis: SongAnalysis) -> dict[int, list[float]]:
    """Pre-compute which downbeats fall in each section."""
    result: dict[int, list[float]] = {}
    for i, section in enumerate(analysis.sections):
        result[i] = [
            b for b in analysis.beats.downbeat_times
            if section.start_time <= b < section.end_time
        ]
    return result


def _try_extract_lyrics(mp3_path: Path):
    """Try to extract lyrics using Whisper. Returns None if unavailable."""
    try:
        from xlights_mcp.audio.lyrics import extract_lyrics
        return extract_lyrics(mp3_path, whisper_model="base")
    except ImportError:
        logger.info("Whisper not installed — skipping lyric extraction")
        return None
    except Exception as e:
        logger.warning(f"Lyric extraction failed: {e}")
        return None
