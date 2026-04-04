"""Color palette management for xLights sequences."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ColorPalette(BaseModel):
    """An xLights color palette for effects."""

    colors: list[str] = Field(default_factory=list)  # hex colors like "#FF0000"
    active_colors: list[int] = Field(default_factory=list)  # which palette slots are active
    sparkle_frequency: int = 0
    sparkle_color: str = ""

    def to_xlights_string(self) -> str:
        """Serialize to the xLights palette format string."""
        parts = []
        # Palette button colors (up to 8 slots)
        defaults = ["#FFFFFF", "#FF0000", "#00FF00", "#0000FF",
                     "#FFFF00", "#000000", "#00FFFF", "#FF00FF"]
        for i in range(8):
            color = self.colors[i] if i < len(self.colors) else defaults[i]
            parts.append(f"C_BUTTON_Palette{i + 1}={color}")

        # Active color checkboxes
        for idx in self.active_colors:
            parts.append(f"C_CHECKBOX_Palette{idx}=1")

        # Sparkle
        if self.sparkle_frequency > 0:
            parts.append(f"C_SLIDER_SparkleFrequency={self.sparkle_frequency}")
        if self.sparkle_color:
            parts.append(f"C_COLOURPICKERCTRL_SparklesColour={self.sparkle_color}")

        return ",".join(parts)


# Pre-defined theme palettes
CHRISTMAS_PALETTES = {
    "classic": ColorPalette(
        colors=["#FF0000", "#00FF00", "#FFFFFF"],
        active_colors=[1, 2, 3],
    ),
    "warm": ColorPalette(
        colors=["#FF0000", "#FEB800", "#FFD700", "#FFFFFF"],
        active_colors=[1, 2, 3, 4],
    ),
    "cool": ColorPalette(
        colors=["#0000FF", "#00FFFF", "#FFFFFF", "#C0C0FF"],
        active_colors=[1, 2, 3, 4],
    ),
    "candy_cane": ColorPalette(
        colors=["#FF0000", "#FFFFFF"],
        active_colors=[1, 2],
    ),
    "gold_silver": ColorPalette(
        colors=["#FFD700", "#C0C0C0", "#FFFFFF"],
        active_colors=[1, 2, 3],
    ),
    "icy": ColorPalette(
        colors=["#FFFFFF", "#87CEEB", "#00BFFF", "#ADD8E6"],
        active_colors=[1, 2, 3, 4],
    ),
    "traditional": ColorPalette(
        colors=["#FF0000", "#00FF00", "#FFD700", "#FFFFFF"],
        active_colors=[1, 2, 3, 4],
    ),
}

HALLOWEEN_PALETTES = {
    "classic": ColorPalette(
        colors=["#FF6600", "#800080", "#00FF00", "#000000"],
        active_colors=[1, 2, 3],
    ),
    "spooky": ColorPalette(
        colors=["#800080", "#00FF00", "#FF0000", "#000000"],
        active_colors=[1, 2, 3],
    ),
    "fire": ColorPalette(
        colors=["#FF0000", "#FF6600", "#FFD700", "#FFFFFF"],
        active_colors=[1, 2, 3],
    ),
    "ghostly": ColorPalette(
        colors=["#FFFFFF", "#E0E0FF", "#C0C0FF", "#8080FF"],
        active_colors=[1, 2, 3, 4],
    ),
}

GENERIC_PALETTES = {
    "rainbow": ColorPalette(
        colors=["#FF0000", "#FF8000", "#FFFF00", "#00FF00", "#0000FF", "#8000FF"],
        active_colors=[1, 2, 3, 4, 5, 6],
    ),
    "white": ColorPalette(
        colors=["#FFFFFF"],
        active_colors=[1],
    ),
    "warm_white": ColorPalette(
        colors=["#FFF5E6", "#FFE0B2", "#FFCC80"],
        active_colors=[1, 2, 3],
    ),
}


def get_theme_palettes(theme: str | None) -> dict[str, ColorPalette]:
    """Get palettes appropriate for a theme."""
    if theme and "halloween" in theme.lower():
        return {**HALLOWEEN_PALETTES, **GENERIC_PALETTES}
    elif theme and "christmas" in theme.lower():
        return {**CHRISTMAS_PALETTES, **GENERIC_PALETTES}
    return {**CHRISTMAS_PALETTES, **GENERIC_PALETTES}
