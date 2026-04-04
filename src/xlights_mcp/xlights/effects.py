"""xLights effect definitions and model-type compatibility."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EffectDef(BaseModel):
    """Definition of an xLights effect."""

    name: str
    description: str = ""
    best_for: list[str] = Field(default_factory=list)  # model categories
    musical_use: list[str] = Field(default_factory=list)  # when to use musically
    default_settings: dict[str, str] = Field(default_factory=dict)


# Comprehensive effect library based on analysis of existing sequences
EFFECT_LIBRARY: list[EffectDef] = [
    EffectDef(
        name="On",
        description="Solid color fill — static on state",
        best_for=["all"],
        musical_use=["sustained", "background", "accent"],
    ),
    EffectDef(
        name="Twinkle",
        description="Random pixel twinkling/sparkle effect",
        best_for=["custom", "tree", "single_line", "arch"],
        musical_use=["gentle", "ambient", "verse", "quiet_section"],
    ),
    EffectDef(
        name="Shimmer",
        description="Rapid on/off shimmer across all pixels",
        best_for=["single_line", "poly_line", "custom"],
        musical_use=["sustained_note", "building", "transition"],
    ),
    EffectDef(
        name="Shockwave",
        description="Expanding circular wave from center point",
        best_for=["custom", "tree", "arch"],
        musical_use=["beat_hit", "bass_drop", "accent", "downbeat"],
    ),
    EffectDef(
        name="Morph",
        description="Smooth color/position transition effect",
        best_for=["single_line", "poly_line", "arch"],
        musical_use=["beat_hit", "quick_accent", "transition"],
    ),
    EffectDef(
        name="SingleStrand",
        description="Chase/runner effect along a single strand (includes chase, fireworks, etc.)",
        best_for=["arch", "single_line", "poly_line"],
        musical_use=["rhythmic", "beat_sync", "running", "energetic"],
    ),
    EffectDef(
        name="Chase",
        description="Color chase running along the model",
        best_for=["arch", "single_line", "poly_line"],
        musical_use=["rhythmic", "beat_sync", "chorus", "energetic"],
    ),
    EffectDef(
        name="Circles",
        description="Animated circles/bubbles pattern",
        best_for=["custom", "tree"],
        musical_use=["playful", "moderate_energy", "verse"],
    ),
    EffectDef(
        name="Plasma",
        description="Flowing plasma/lava lamp effect",
        best_for=["custom", "tree", "arch"],
        musical_use=["ambient", "sustained", "intro", "bridge"],
    ),
    EffectDef(
        name="Pinwheel",
        description="Rotating pinwheel/spiral pattern",
        best_for=["tree", "custom"],
        musical_use=["sustained", "building", "chorus"],
    ),
    EffectDef(
        name="Spirals",
        description="Spiral pattern wrapping around a tree or cylinder",
        best_for=["tree"],
        musical_use=["sustained", "chorus", "building"],
    ),
    EffectDef(
        name="Meteors",
        description="Falling/flying meteor trails",
        best_for=["tree", "single_line", "custom"],
        musical_use=["high_energy", "climax", "chorus", "fills"],
    ),
    EffectDef(
        name="Warp",
        description="Pixel distortion/warp effect on layers below",
        best_for=["custom", "tree"],
        musical_use=["transition", "dramatic", "bridge"],
    ),
    EffectDef(
        name="Faces",
        description="Lip-sync / singing face animation (needs phoneme data)",
        best_for=["custom"],
        musical_use=["vocal_section", "singing_prop"],
    ),
    EffectDef(
        name="ColorWash",
        description="Smooth color gradient wash across the model",
        best_for=["all"],
        musical_use=["ambient", "verse", "gentle", "background"],
    ),
    EffectDef(
        name="Fire",
        description="Flickering fire/flame effect",
        best_for=["custom", "tree", "single_line"],
        musical_use=["dramatic", "building", "intense"],
    ),
    EffectDef(
        name="Butterfly",
        description="Symmetrical butterfly wing pattern",
        best_for=["custom", "tree"],
        musical_use=["ambient", "gentle", "verse"],
    ),
    EffectDef(
        name="Marquee",
        description="Theater marquee chase around border",
        best_for=["window", "poly_line", "custom"],
        musical_use=["rhythmic", "playful", "accent"],
    ),
    EffectDef(
        name="Strobe",
        description="Rapid strobe/flash effect",
        best_for=["all"],
        musical_use=["climax", "hit", "accent", "bass_drop"],
    ),
    EffectDef(
        name="Snowflakes",
        description="Falling snowflake animation",
        best_for=["custom", "tree"],
        musical_use=["gentle", "ambient", "christmas_theme"],
    ),
    EffectDef(
        name="Curtain",
        description="Opening/closing curtain reveal",
        best_for=["custom", "tree"],
        musical_use=["intro", "transition", "reveal"],
    ),
    EffectDef(
        name="Bars",
        description="Horizontal or vertical color bars",
        best_for=["custom", "tree", "arch"],
        musical_use=["rhythmic", "beat_sync", "energetic"],
    ),
    EffectDef(
        name="Galaxy",
        description="Swirling galaxy/nebula pattern",
        best_for=["tree", "custom"],
        musical_use=["ambient", "sustained", "bridge"],
    ),
]


# Musical feature → effect mapping
MUSICAL_EFFECT_MAP = {
    "strong_beat": ["Shockwave", "Morph", "Strobe"],
    "beat_sync": ["SingleStrand", "Chase", "Bars", "Marquee"],
    "bass_drop": ["Shockwave", "Strobe", "Fire"],
    "high_energy": ["Chase", "Meteors", "SingleStrand", "Bars"],
    "low_energy": ["Twinkle", "Shimmer", "ColorWash", "Snowflakes"],
    "sustained": ["Plasma", "Pinwheel", "Spirals", "Galaxy", "Butterfly"],
    "vocal": ["Faces"],
    "transition": ["Warp", "Curtain", "Morph"],
    "intro": ["Curtain", "ColorWash", "Plasma"],
    "outro": ["Twinkle", "ColorWash", "Shimmer"],
    "chorus": ["Chase", "Shockwave", "Meteors", "Pinwheel"],
    "verse": ["Twinkle", "ColorWash", "Circles", "Butterfly"],
    "bridge": ["Plasma", "Warp", "Galaxy"],
}


# Model category → best effects
MODEL_EFFECT_MAP = {
    "arch": ["SingleStrand", "Chase", "ColorWash", "Morph", "Shimmer", "Plasma"],
    "tree": ["Spirals", "Pinwheel", "Meteors", "Circles", "Shockwave", "Plasma", "Galaxy"],
    "single_line": ["Chase", "Morph", "SingleStrand", "Shimmer", "ColorWash"],
    "poly_line": ["Chase", "SingleStrand", "Shimmer", "Twinkle", "Morph"],
    "window": ["Marquee", "ColorWash", "On", "Curtain"],
    "custom": ["Shockwave", "Circles", "Plasma", "Twinkle", "Warp", "Fire", "Faces"],
    "other": ["ColorWash", "Twinkle", "On", "Shimmer"],
}


def get_effect_library() -> list[dict]:
    """Return the complete effect library as dicts for MCP tool response."""
    return [e.model_dump() for e in EFFECT_LIBRARY]


def get_effects_for_model(model_category: str) -> list[str]:
    """Get recommended effect names for a model category."""
    return MODEL_EFFECT_MAP.get(model_category, MODEL_EFFECT_MAP["other"])


def get_effects_for_musical_feature(feature: str) -> list[str]:
    """Get recommended effects for a musical feature."""
    return MUSICAL_EFFECT_MAP.get(feature, [])
