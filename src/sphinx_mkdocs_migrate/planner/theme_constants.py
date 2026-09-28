"""Constants and comprehensive color/theme mappings for MkDocs to Sphinx migration."""
from enum import Enum
from typing import Dict, Any

class ThemeScheme(str, Enum):
    DEFAULT = "default"
    SLATE = "slate"
    LIGHT = "light"
    DARK = "dark"

# Exhaustive official Material for MkDocs color palette (Primary & Accent)
# Sourced directly from Material Design color system used by squidfunk/mkdocs-material
MKDOCS_MATERIAL_COLORS: Dict[str, str] = {
    # 19 Primary colors
    "red": "#ef5350",
    "pink": "#e91e63",
    "purple": "#ab47bc",
    "deep-purple": "#7e57c2",
    "indigo": "#3f51b5",
    "blue": "#2196f3",
    "light-blue": "#03a9f4",
    "cyan": "#00bcd4",
    "teal": "#009688",
    "green": "#4caf50",
    "light-green": "#8bc34a",
    "lime": "#cddc39",
    "yellow": "#ffeb3b",
    "amber": "#ffc107",
    "orange": "#ff9800",
    "deep-orange": "#ff5722",
    "brown": "#795548",
    "grey": "#9e9e9e",
    "blue-grey": "#607d8b",
    "white": "#ffffff",
    "black": "#000000",
    "slate": "#1e293b",
}

# Material Accent colors (A200/A400 shades)
MKDOCS_MATERIAL_ACCENTS: Dict[str, str] = {
    "red": "#ff5252",
    "pink": "#ff4081",
    "purple": "#e040fb",
    "deep-purple": "#7c4dff",
    "indigo": "#536dfe",
    "blue": "#448aff",
    "light-blue": "#40c4ff",
    "cyan": "#18ffff",
    "teal": "#64ffda",
    "green": "#69f0ae",
    "light-green": "#b2ff59",
    "lime": "#eeff41",
    "yellow": "#ffff00",
    "amber": "#ffd740",
    "orange": "#ffab40",
    "deep-orange": "#ff6e40",
}

def resolve_material_color(color_name: str, is_accent: bool = False) -> str:
    """Resolves a MkDocs Material color name to its hex code, or returns the raw string if already hex/rgb."""
    clean = color_name.strip().lower().replace("_", "-")
    if is_accent and clean in MKDOCS_MATERIAL_ACCENTS:
        return MKDOCS_MATERIAL_ACCENTS[clean]
    if clean in MKDOCS_MATERIAL_COLORS:
        return MKDOCS_MATERIAL_COLORS[clean]
    return color_name
