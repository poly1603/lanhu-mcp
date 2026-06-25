"""Design tokens and Flet theme construction for the Lanhu MCP GUI.

Ported from the legacy Tkinter ``COLORS`` / ``SPACING`` / ``RADIUS`` / ``FONT``
constants (TDesign-based) into a self-contained, Flet-friendly module. This
module has **no** Tkinter dependency and may be imported without a display.

Usage::

    import flet as ft
    from lanhu_mcp.gui import theme

    page.theme = theme.build_theme(theme.LIGHT)
    page.dark_theme = theme.build_theme(theme.DARK)
    palette = theme.LIGHT  # or theme.DARK
    page.bgcolor = palette.bg
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import flet as ft

# ---------------------------------------------------------------------------
# Spacing scale (4px base, TDesign spec)
# ---------------------------------------------------------------------------
SPACING: Dict[str, int] = {
    "0": 0,
    "1": 4,
    "2": 8,
    "3": 12,
    "4": 16,
    "5": 20,
    "6": 24,
    "8": 32,
    "10": 40,
    "12": 48,
}


def space(key: str) -> int:
    """Return a spacing value by token key (e.g. ``space('4')`` -> 16)."""
    return SPACING.get(str(key), 0)


# ---------------------------------------------------------------------------
# Corner radius scale (TDesign spec)
# ---------------------------------------------------------------------------
RADIUS: Dict[str, int] = {
    "none": 0,
    "sm": 3,
    "md": 6,
    "lg": 9,
    "xl": 12,
    "2xl": 16,
    "full": 9999,
}


def radius(key: str) -> int:
    return RADIUS.get(str(key), 0)


# ---------------------------------------------------------------------------
# Typography (TDesign spec)
# ---------------------------------------------------------------------------
FONT_FAMILY = "PingFang SC, Microsoft YaHei, Helvetica Neue, Segoe UI, sans-serif"
FONT_MONO = "Cascadia Code, Consolas, monospace"

FONT_SIZES: Dict[str, int] = {
    "xs": 10,
    "sm": 12,
    "base": 14,
    "md": 14,
    "lg": 16,
    "xl": 18,
    "2xl": 20,
    "3xl": 24,
    "4xl": 28,
    "5xl": 32,
}


def font_size(key: str) -> int:
    return FONT_SIZES.get(str(key), 14)


# Flet FontWeight aliases (semibold -> w600, etc.)
WEIGHT_NORMAL = ft.FontWeight.NORMAL
WEIGHT_MEDIUM = ft.FontWeight.W_500
WEIGHT_SEMIBOLD = ft.FontWeight.W_600
WEIGHT_BOLD = ft.FontWeight.BOLD


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Palette:
    """A resolved color palette for one theme mode (light or dark)."""

    name: str

    # Backgrounds
    bg: str
    sidebar: str
    sidebar_hover: str
    sidebar_active: str
    sidebar_text: str
    card: str
    card_hover: str
    surface: str
    surface_hover: str
    input_bg: str
    input_bg_disabled: str

    # Brand / primary
    primary: str
    primary_hover: str
    primary_active: str
    primary_light: str
    primary_light_hover: str

    # Semantic
    success: str
    success_hover: str
    danger: str
    danger_hover: str
    warning: str
    warning_hover: str
    accent: str
    accent_light: str
    accent_warm: str
    accent_warm_light: str

    # Text
    text_primary: str
    text_secondary: str
    text_muted: str
    text_disabled: str
    text_on_primary: str
    text_on_dark: str

    # Borders
    border: str
    border_light: str
    border_hover: str
    border_focus: str
    border_error: str

    # Log surface
    log_bg: str
    log_text: str

    # Shadow color (rgba string)
    shadow_color: str = "#1A000000"  # ~6% black in ARGB hex

    def as_dict(self) -> Dict[str, str]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "name"}


# Light palette — faithful port of the legacy TDesign COLORS dict.
LIGHT = Palette(
    name="light",
    bg="#F3F3F3",
    sidebar="#2C2C2C",
    sidebar_hover="#393939",
    sidebar_active="#4A4A4A",
    sidebar_text="#EEEEEE",
    card="#FFFFFF",
    card_hover="#FAFAFA",
    surface="#F3F3F3",
    surface_hover="#E7E7E7",
    input_bg="#FFFFFF",
    input_bg_disabled="#F3F3F3",
    primary="#0052D9",
    primary_hover="#266FE8",
    primary_active="#003A99",
    primary_light="#ECF2FE",
    primary_light_hover="#D4E3FC",
    success="#00A870",
    success_hover="#25C288",
    danger="#E34D59",
    danger_hover="#F66F7A",
    warning="#ED7B2F",
    warning_hover="#FB9A4B",
    accent="#00809A",
    accent_light="#E3F5F8",
    accent_warm="#F59D0A",
    accent_warm_light="#FEF3CD",
    text_primary="#1A1A1A",
    text_secondary="#666666",
    text_muted="#999999",
    text_disabled="#CCCCCC",
    text_on_primary="#FFFFFF",
    text_on_dark="#EEEEEE",
    border="#DEDEDE",
    border_light="#EEEEEE",
    border_hover="#C0C0C0",
    border_focus="#0052D9",
    border_error="#E34D59",
    log_bg="#2C2C2C",
    log_text="#EEEEEE",
    shadow_color="#14000000",
)

# Dark palette — derived from the same brand hues, tuned for a dark surface.
DARK = Palette(
    name="dark",
    bg="#1A1A1A",
    sidebar="#202020",
    sidebar_hover="#2C2C2C",
    sidebar_active="#3A3A3A",
    sidebar_text="#EEEEEE",
    card="#242424",
    card_hover="#2C2C2C",
    surface="#1F1F1F",
    surface_hover="#2A2A2A",
    input_bg="#2C2C2C",
    input_bg_disabled="#242424",
    primary="#4A8DF7",
    primary_hover="#6BA3F9",
    primary_active="#266FE8",
    primary_light="#1E2A3F",
    primary_light_hover="#26344D",
    success="#37C28E",
    success_hover="#56D6A6",
    danger="#F0707B",
    danger_hover="#F58A93",
    warning="#F6A04B",
    warning_hover="#F9B872",
    accent="#3FB6CE",
    accent_light="#1B2E33",
    accent_warm="#F6B23C",
    accent_warm_light="#33290F",
    text_primary="#F0F0F0",
    text_secondary="#B8B8B8",
    text_muted="#888888",
    text_disabled="#5A5A5A",
    text_on_primary="#FFFFFF",
    text_on_dark="#EEEEEE",
    border="#3A3A3A",
    border_light="#2E2E2E",
    border_hover="#4A4A4A",
    border_focus="#4A8DF7",
    border_error="#F0707B",
    log_bg="#141414",
    log_text="#D8D8D8",
    shadow_color="#33000000",
)


def get_palette(mode: str) -> Palette:
    """Return the palette for ``'light'`` or ``'dark'`` (defaults to light)."""
    return DARK if str(mode).lower() == "dark" else LIGHT


def build_theme(palette: Palette) -> ft.Theme:
    """Construct a Flet :class:`ft.Theme` from a palette."""
    return ft.Theme(
        font_family=FONT_FAMILY,
        color_scheme_seed=palette.primary,
        color_scheme=ft.ColorScheme(
            primary=palette.primary,
            on_primary=palette.text_on_primary,
            surface=palette.card,
            on_surface=palette.text_primary,
            error=palette.danger,
            outline=palette.border,
        ),
        visual_density=ft.VisualDensity.COMFORTABLE,
    )


__all__ = [
    "SPACING",
    "RADIUS",
    "FONT_FAMILY",
    "FONT_MONO",
    "FONT_SIZES",
    "WEIGHT_NORMAL",
    "WEIGHT_MEDIUM",
    "WEIGHT_SEMIBOLD",
    "WEIGHT_BOLD",
    "Palette",
    "LIGHT",
    "DARK",
    "space",
    "radius",
    "font_size",
    "get_palette",
    "build_theme",
]
