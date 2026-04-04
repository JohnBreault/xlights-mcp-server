"""Parse xLights show folder configuration files."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from xlights_mcp.xlights.models import (
    Controller,
    LightModel,
    ModelGroup,
    ShowConfig,
    SubModel,
)

logger = logging.getLogger(__name__)


def load_show_config(show_path: Path) -> ShowConfig:
    """Load complete show configuration from an xLights show folder.

    Reads xlights_networks.xml and xlights_rgbeffects.xml to build
    a complete picture of the controllers, models, and groups.
    """
    show_name = show_path.name
    controllers = load_show_controllers(show_path)
    models = load_show_models(show_path)
    groups = load_model_groups(show_path)
    total_channels = sum(c.max_channels for c in controllers)

    return ShowConfig(
        show_path=str(show_path),
        show_name=show_name,
        controllers=controllers,
        models=models,
        model_groups=groups,
        total_channels=total_channels,
    )


def load_show_controllers(show_path: Path) -> list[Controller]:
    """Parse xlights_networks.xml to extract controller configuration."""
    networks_file = show_path / "xlights_networks.xml"
    if not networks_file.exists():
        logger.warning(f"Networks file not found: {networks_file}")
        return []

    tree = ET.parse(networks_file)
    root = tree.getroot()
    controllers = []

    for ctrl_elem in root.findall("Controller"):
        max_channels = 0
        for network in ctrl_elem.findall("network"):
            ch = network.get("MaxChannels", "0")
            try:
                max_channels += int(ch)
            except ValueError:
                pass

        controller = Controller(
            id=ctrl_elem.get("Id", ""),
            name=ctrl_elem.get("Name", ""),
            description=ctrl_elem.get("Description", ""),
            controller_type=ctrl_elem.get("Type", ""),
            vendor=ctrl_elem.get("Vendor", ""),
            model=ctrl_elem.get("Model", ""),
            ip=ctrl_elem.get("IP", ""),
            protocol=ctrl_elem.get("Protocol", ""),
            max_channels=max_channels,
            active_state=ctrl_elem.get("ActiveState", ""),
        )
        controllers.append(controller)

    logger.info(f"Loaded {len(controllers)} controllers from {networks_file}")
    return controllers


def load_show_models(show_path: Path) -> list[LightModel]:
    """Parse xlights_rgbeffects.xml to extract model definitions."""
    effects_file = show_path / "xlights_rgbeffects.xml"
    if not effects_file.exists():
        logger.warning(f"RGB effects file not found: {effects_file}")
        return []

    tree = ET.parse(effects_file)
    root = tree.getroot()
    models_elem = root.find("models")
    if models_elem is None:
        return []

    models = []
    for m in models_elem:
        if m.tag == "model":
            # Collect submodels (child elements)
            submodels = []
            for child in m:
                if child.tag in ("subModel", "strandNames", "nodeNames"):
                    continue
                child_name = child.get("name", "")
                if child_name:
                    submodels.append(SubModel(name=child_name, parent=m.get("name", "")))

            pixel_count = 0
            parm1 = m.get("parm1", "0")
            parm2 = m.get("parm2", "0")
            pixel_count_attr = m.get("PixelCount", "")
            if pixel_count_attr:
                try:
                    pixel_count = int(pixel_count_attr)
                except ValueError:
                    pass
            elif parm1 and parm2:
                try:
                    pixel_count = int(parm1) * int(parm2)
                except ValueError:
                    pass

            model = LightModel(
                name=m.get("name", ""),
                display_as=m.get("DisplayAs", ""),
                controller=m.get("Controller", ""),
                pixel_count=pixel_count,
                string_type=m.get("StringType", "RGB Nodes"),
                submodels=submodels,
            )
            models.append(model)

    logger.info(f"Loaded {len(models)} models from {effects_file}")
    return models


def load_model_groups(show_path: Path) -> list[ModelGroup]:
    """Parse model groups from xlights_rgbeffects.xml."""
    effects_file = show_path / "xlights_rgbeffects.xml"
    if not effects_file.exists():
        return []

    tree = ET.parse(effects_file)
    root = tree.getroot()
    models_elem = root.find("models")
    if models_elem is None:
        return []

    groups = []
    for m in models_elem:
        if m.tag == "modelGroup":
            members_str = m.get("models", "")
            members = [name.strip() for name in members_str.split(",") if name.strip()]
            group = ModelGroup(
                name=m.get("name", ""),
                members=members,
                grid_size=m.get("GridSize", ""),
                layout=m.get("layout", ""),
            )
            groups.append(group)

    logger.info(f"Loaded {len(groups)} model groups from {effects_file}")
    return groups
