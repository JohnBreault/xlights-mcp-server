"""Data models for xLights show elements."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Controller(BaseModel):
    """An xLights output controller (e.g., Falcon F16v5, FPP)."""

    id: str
    name: str
    description: str = ""
    controller_type: str = ""  # "Ethernet", etc.
    vendor: str = ""
    model: str = ""  # "F16V5", "FPP Player Only", etc.
    ip: str = ""
    protocol: str = ""  # "DDP", "E1.31", "Player Only"
    max_channels: int = 0
    active_state: str = ""  # "Active", "xLights Only"


class SubModel(BaseModel):
    """A sub-model within a parent model (e.g., arch top/bottom)."""

    name: str
    parent: str


class LightModel(BaseModel):
    """A light model (physical light element) in the xLights show."""

    name: str
    display_as: str = ""  # "Arches", "Single Line", "Custom", "Poly Line", "Tree", etc.
    controller: str = ""
    pixel_count: int = 0
    string_type: str = "RGB Nodes"
    submodels: list[SubModel] = Field(default_factory=list)

    @property
    def model_category(self) -> str:
        """Categorize the model type for effect selection."""
        display = self.display_as.lower()
        if "arch" in display:
            return "arch"
        elif "tree" in display:
            return "tree"
        elif "single line" in display:
            return "single_line"
        elif "poly line" in display:
            return "poly_line"
        elif "window" in display:
            return "window"
        elif "custom" in display:
            return "custom"
        else:
            return "other"


class ModelGroup(BaseModel):
    """A group of models that can be controlled together."""

    name: str
    members: list[str] = Field(default_factory=list)
    grid_size: str = ""
    layout: str = ""


class ShowConfig(BaseModel):
    """Complete parsed show configuration."""

    show_path: str
    show_name: str
    controllers: list[Controller] = Field(default_factory=list)
    models: list[LightModel] = Field(default_factory=list)
    model_groups: list[ModelGroup] = Field(default_factory=list)
    total_channels: int = 0

    def get_models_by_controller(self, controller_name: str) -> list[LightModel]:
        """Get all models assigned to a specific controller."""
        return [m for m in self.models if m.controller == controller_name]

    def get_models_by_category(self, category: str) -> list[LightModel]:
        """Get all models of a specific category."""
        return [m for m in self.models if m.model_category == category]

    def get_model_by_name(self, name: str) -> LightModel | None:
        """Look up a model by exact name."""
        for m in self.models:
            if m.name == name:
                return m
        return None
