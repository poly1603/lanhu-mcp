"""Design tokens and Flet theme construction for the Lanhu MCP GUI.

Usage::

    import flet as ft
    from lanhu_mcp.gui import theme

    page.theme = theme.build_theme(theme.LIGHT)
    page.dark_theme = theme.build_theme(theme.DARK)
    palette = theme.LIGHT
    page.bgcolor = palette.bg
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import flet as ft

# ════════════════════════════════════════════════════════════════
# Spacing scale
# ════════════════════════════════════════════════════════════════
SPACING: Dict[str, int] = {
    "0": 0, "1": 4, "2": 8, "3": 12,
    "4": 16, "5": 20, "6": 24, "8": 32, "10": 40, "12": 48,
}


def space(key: str) -> int:
    return SPACING.get(str(key), 0)


# ════════════════════════════════════════════════════════════════
# Corner radius
# ════════════════════════════════════════════════════════════════
RADIUS: Dict[str, int] = {
    "none": 0, "sm": 6, "md": 10, "lg": 12, "xl": 16, "2xl": 20, "full": 9999,
}


def radius(key: str) -> int:
    return RADIUS.get(str(key), 0)


# ════════════════════════════════════════════════════════════════
# Shadows (ARGB hex)
# ════════════════════════════════════════════════════════════════
SHADOW_SM = "14000000"
SHADOW_MD = "1A000000"
SHADOW_LG = "22000000"
SHADOW_XL = "2E000000"


# ════════════════════════════════════════════════════════════════
# Typography
# ════════════════════════════════════════════════════════════════
FONT_FAMILY = "PingFang SC, Microsoft YaHei, Helvetica Neue, Segoe UI, sans-serif"
FONT_MONO = "Cascadia Code, JetBrains Mono, Consolas, monospace"

FONT_SIZES: Dict[str, int] = {
    "xs": 10, "sm": 12, "base": 14, "md": 14,
    "lg": 16, "xl": 18, "2xl": 20, "3xl": 24, "4xl": 28, "5xl": 32,
}


def font_size(key: str) -> int:
    return FONT_SIZES.get(str(key), 14)


def alpha(hex_color: str, opacity: int) -> str:
    c = hex_color.lstrip("#")
    if len(c) == 6:
        return f"#{max(0, min(opacity, 255)):02X}{c}"
    return hex_color


WEIGHT_NORMAL = ft.FontWeight.NORMAL
WEIGHT_MEDIUM = ft.FontWeight.W_500
WEIGHT_SEMIBOLD = ft.FontWeight.W_600
WEIGHT_BOLD = ft.FontWeight.BOLD


# ════════════════════════════════════════════════════════════════
# Palette
# ════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Palette:
    name: str = ""

    # Backgrounds
    bg: str = ""
    sidebar: str = ""
    sidebar_hover: str = ""
    sidebar_active: str = ""
    sidebar_text: str = ""
    card: str = ""
    card_hover: str = ""
    surface: str = ""
    surface_hover: str = ""
    input_bg: str = ""
    input_bg_disabled: str = ""

    # Brand / primary
    primary: str = ""
    primary_hover: str = ""
    primary_active: str = ""
    primary_light: str = ""
    primary_light_hover: str = ""
    primary_gradient_start: str = ""
    primary_gradient_end: str = ""

    # Semantic
    success: str = ""
    success_hover: str = ""
    success_light: str = ""
    danger: str = ""
    danger_hover: str = ""
    danger_light: str = ""
    warning: str = ""
    warning_hover: str = ""
    warning_light: str = ""
    accent: str = ""
    accent_light: str = ""
    accent_warm: str = ""
    accent_warm_light: str = ""
    info: str = ""
    info_light: str = ""

    # Text
    text_primary: str = ""
    text_secondary: str = ""
    text_muted: str = ""
    text_disabled: str = ""
    text_on_primary: str = ""
    text_on_dark: str = ""

    # Borders
    border: str = ""
    border_light: str = ""
    border_hover: str = ""
    border_focus: str = ""
    border_error: str = ""

    # Log
    log_bg: str = ""
    log_text: str = ""

    # Shadows (ARGB hex)
    shadow_sm: str = "#14000000"
    shadow_md: str = "#1A000000"
    shadow_lg: str = "#22000000"

    def as_dict(self) -> Dict[str, str]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "name"}


# ════════════════════════════════════════════════════════════════
# LIGHT
# ════════════════════════════════════════════════════════════════
LIGHT = Palette(
    name="light",
    bg="#F6F8FB",
    sidebar="#101828",
    sidebar_hover="#1D2939",
    sidebar_active="#2563EB",
    sidebar_text="#E4E7EC",
    card="#FFFFFF",
    card_hover="#F9FAFB",
    surface="#F2F4F7",
    surface_hover="#EAECF0",
    input_bg="#FFFFFF",
    input_bg_disabled="#F2F4F7",

    primary="#2563EB",
    primary_hover="#1D4ED8",
    primary_active="#1E40AF",
    primary_light="#EFF6FF",
    primary_light_hover="#DBEAFE",
    primary_gradient_start="#2563EB",
    primary_gradient_end="#06B6D4",

    success="#12B76A",
    success_hover="#039855",
    success_light="#ECFDF3",
    danger="#F04438",
    danger_hover="#D92D20",
    danger_light="#FEF3F2",
    warning="#F79009",
    warning_hover="#DC6803",
    warning_light="#FFFAEB",
    accent="#06B6D4",
    accent_light="#ECFEFF",
    accent_warm="#F97316",
    accent_warm_light="#FFF7ED",
    info="#2563EB",
    info_light="#EFF6FF",

    text_primary="#101828",
    text_secondary="#475467",
    text_muted="#667085",
    text_disabled="#98A2B3",
    text_on_primary="#FFFFFF",
    text_on_dark="#F9FAFB",

    border="#D0D5DD",
    border_light="#EAECF0",
    border_hover="#98A2B3",
    border_focus="#2563EB",
    border_error="#F04438",

    log_bg="#0B1220",
    log_text="#E4E7EC",

    shadow_sm="#0F101828",
    shadow_md="#18101828",
    shadow_lg="#24101828",
)

# ════════════════════════════════════════════════════════════════
# DARK
# ════════════════════════════════════════════════════════════════
DARK = Palette(
    name="dark",
    bg="#0B1220",
    sidebar="#0F172A",
    sidebar_hover="#1E293B",
    sidebar_active="#2563EB",
    sidebar_text="#E2E8F0",
    card="#111827",
    card_hover="#1F2937",
    surface="#182230",
    surface_hover="#243247",
    input_bg="#111827",
    input_bg_disabled="#182230",

    primary="#60A5FA",
    primary_hover="#93C5FD",
    primary_active="#3B82F6",
    primary_light="#172554",
    primary_light_hover="#1E3A8A",
    primary_gradient_start="#3B82F6",
    primary_gradient_end="#22D3EE",

    success="#32D583",
    success_hover="#6CE9A6",
    success_light="#052E1A",
    danger="#FDA29B",
    danger_hover="#F97066",
    danger_light="#3B1210",
    warning="#FDB022",
    warning_hover="#FEC84B",
    warning_light="#3B2500",
    accent="#22D3EE",
    accent_light="#083344",
    accent_warm="#FB923C",
    accent_warm_light="#431407",
    info="#60A5FA",
    info_light="#172554",

    text_primary="#F8FAFC",
    text_secondary="#CBD5E1",
    text_muted="#94A3B8",
    text_disabled="#64748B",
    text_on_primary="#FFFFFF",
    text_on_dark="#F8FAFC",

    border="#334155",
    border_light="#243247",
    border_hover="#475569",
    border_focus="#60A5FA",
    border_error="#FDA29B",

    log_bg="#020617",
    log_text="#E2E8F0",

    shadow_sm="#44000000",
    shadow_md="#55000000",
    shadow_lg="#66000000",
)


def get_palette(mode: str) -> Palette:
    return DARK if str(mode).lower() == "dark" else LIGHT


def build_theme(palette: Palette) -> ft.Theme:
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
        scrollbar_theme=ft.ScrollbarTheme(
            thumb_color=palette.border_hover,
            track_color=palette.surface,
            thickness=6,
            radius=8,
        ),
    )


__all__ = [
    "SPACING", "RADIUS", "SHADOW_SM", "SHADOW_MD", "SHADOW_LG", "SHADOW_XL",
    "FONT_FAMILY", "FONT_MONO", "FONT_SIZES",
    "WEIGHT_NORMAL", "WEIGHT_MEDIUM", "WEIGHT_SEMIBOLD", "WEIGHT_BOLD",
    "Palette", "LIGHT", "DARK",
    "space", "radius", "font_size", "alpha", "get_palette", "build_theme",
]
