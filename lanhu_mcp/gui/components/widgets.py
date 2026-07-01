"""Reusable Flet controls and helpers (v2 — enriched).

Adds: gradient cards, stat chips, quick-action tiles, tab bar, timeline,
level badges, and refined variants of the original widgets.
"""

from __future__ import annotations

import threading
import traceback
from typing import Callable, Dict, List, Optional

import flet as ft

from .. import theme
from ..theme import Palette
from ...core.errors import describe_error


# ════════════════════════════════════════════════════════════════
# Async bridge
# ════════════════════════════════════════════════════════════════
def run_in_background(
    page: ft.Page,
    work: Callable[[], object],
    on_done: Optional[Callable[[object], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
) -> threading.Thread:
    def runner() -> None:
        try:
            result = work()
        except Exception as exc:
            traceback.print_exc()
            if on_error is not None:
                try:
                    on_error(exc)
                except Exception:
                    traceback.print_exc()
            try:
                page.update()
            except Exception:
                pass
            return
        if on_done is not None:
            try:
                on_done(result)
            except Exception:
                traceback.print_exc()
        try:
            page.update()
        except Exception:
            pass

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread


# ════════════════════════════════════════════════════════════════
# Cards
# ════════════════════════════════════════════════════════════════
def card(
    palette: Palette,
    content: ft.Control,
    *,
    padding: int = 20,
    expand: bool = False,
) -> ft.Container:
    return ft.Container(
        content=content,
        bgcolor=palette.card,
        border=ft.border.all(1, palette.border_light),
        border_radius=theme.radius("xl"),
        padding=padding,
        expand=expand,
        shadow=ft.BoxShadow(
            spread_radius=0, blur_radius=4, color=palette.shadow_sm,
            offset=ft.Offset(0, 2),
        ),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )


def gradient_card(
    palette: Palette,
    content: ft.Control,
    *,
    padding: int = 20,
    expand: bool = False,
) -> ft.Container:
    """Card with a faint top-accent gradient bar."""
    return ft.Container(
        content=ft.Column([
            ft.Container(
                height=3,
                border_radius=theme.radius("full"),
                gradient=ft.LinearGradient(
                    begin=ft.alignment.center_left,
                    end=ft.alignment.center_right,
                    colors=[palette.primary_gradient_start, palette.primary_gradient_end],
                ),
            ),
            ft.Container(content=content, padding=ft.padding.only(top=padding - 4)),
        ], spacing=0, tight=True),
        bgcolor=palette.card,
        border=ft.border.all(1, palette.border_light),
        border_radius=theme.radius("xl"),
        padding=ft.padding.only(left=padding, right=padding, bottom=padding),
        expand=expand,
        shadow=ft.BoxShadow(
            spread_radius=0, blur_radius=6, color=palette.shadow_md,
            offset=ft.Offset(0, 2),
        ),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )


# ════════════════════════════════════════════════════════════════
# Section headers
# ════════════════════════════════════════════════════════════════
def section_title(palette: Palette, text: str, subtitle: str = "") -> ft.Control:
    children: List[ft.Control] = [
        ft.Text(text, size=theme.font_size("2xl"), weight=theme.WEIGHT_BOLD, color=palette.text_primary),
    ]
    if subtitle:
        children.append(
            ft.Text(subtitle, size=theme.font_size("sm"), color=palette.text_secondary)
        )
    return ft.Column(children, spacing=theme.space("1"))


# ════════════════════════════════════════════════════════════════
# Metric tiles
# ════════════════════════════════════════════════════════════════
def metric_tile(
    palette: Palette,
    label: str,
    value: str,
    *,
    icon: Optional[str] = None,
    accent: Optional[str] = None,
    sub: Optional[str] = None,
    trend: Optional[str] = None,  # "up" | "down" | None
) -> ft.Container:
    accent_color = accent or palette.primary
    head: List[ft.Control] = []
    if icon:
        head.append(
            ft.Container(
                content=ft.Icon(icon, size=18, color=accent_color),
                bgcolor=_alpha20(accent_color),
                border_radius=theme.radius("md"),
                padding=theme.space("2"),
            )
        )
    head.append(
        ft.Text(label, size=theme.font_size("sm"), color=palette.text_secondary)
    )
    value_row: List[ft.Control] = [
        ft.Text(value, size=theme.font_size("4xl"), weight=theme.WEIGHT_BOLD, color=palette.text_primary),
    ]
    if trend == "up":
        value_row.append(ft.Icon(ft.Icons.TRENDING_UP, size=18, color=palette.success))
    elif trend == "down":
        value_row.append(ft.Icon(ft.Icons.TRENDING_DOWN, size=18, color=palette.danger))
    content: List[ft.Control] = [
        ft.Row(head, spacing=theme.space("2")),
        ft.Row(value_row, spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
    ]
    if sub:
        content.append(ft.Text(sub, size=theme.font_size("xs"), color=palette.text_muted))
    return ft.Container(
        content=ft.Column(content, spacing=theme.space("2")),
        bgcolor=palette.card,
        border=ft.border.all(1, palette.border_light),
        border_radius=theme.radius("xl"),
        padding=theme.space("5"),
        expand=True,
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=3, color=palette.shadow_sm, offset=ft.Offset(0, 1)),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )


def stat_chip(
    palette: Palette,
    label: str,
    value: str,
    *,
    icon: Optional[str] = None,
    accent: Optional[str] = None,
) -> ft.Container:
    """Compact inline stat (label: value) with optional icon."""
    accent_color = accent or palette.primary
    row: List[ft.Control] = []
    if icon:
        row.append(ft.Icon(icon, size=14, color=accent_color))
    row.append(ft.Text(label, size=theme.font_size("xs"), color=palette.text_muted))
    row.append(ft.Text(value, size=theme.font_size("sm"), weight=theme.WEIGHT_SEMIBOLD, color=palette.text_primary))
    return ft.Container(
        content=ft.Row(row, spacing=theme.space("1"), tight=True),
        bgcolor=palette.surface,
        border_radius=theme.radius("full"),
        padding=ft.padding.symmetric(horizontal=10, vertical=6),
    )


# ════════════════════════════════════════════════════════════════
# Quick-action tile
# ════════════════════════════════════════════════════════════════
def quick_action_tile(
    palette: Palette,
    title: str,
    subtitle: str,
    icon: str,
    on_click: Callable,
    *,
    accent: Optional[str] = None,
) -> ft.Container:
    accent_color = accent or palette.primary
    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(icon, size=28, color=palette.text_on_primary),
                bgcolor=accent_color,
                border_radius=theme.radius("lg"),
                padding=theme.space("3"),
            ),
            ft.Column([
                ft.Text(title, size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=palette.text_primary),
                ft.Text(subtitle, size=theme.font_size("sm"), color=palette.text_muted),
            ], spacing=2, expand=True),
            ft.Icon(ft.Icons.CHEVRON_RIGHT, size=20, color=palette.text_disabled),
        ], spacing=theme.space("4"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=palette.card,
        border=ft.border.all(1, palette.border_light),
        border_radius=theme.radius("xl"),
        padding=theme.space("5"),
        ink=True,
        on_click=on_click,
        expand=True,
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=3, color=palette.shadow_sm, offset=ft.Offset(0, 1)),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )


# ════════════════════════════════════════════════════════════════
# Empty state
# ════════════════════════════════════════════════════════════════
def empty_state(
    palette: Palette,
    message: str,
    *,
    icon: str = ft.Icons.INBOX_OUTLINED,
    action: Optional[ft.Control] = None,
) -> ft.Container:
    children: List[ft.Control] = [
        ft.Container(
            content=ft.Icon(icon, size=48, color=palette.text_disabled),
            padding=theme.space("4"),
        ),
        ft.Text(message, size=theme.font_size("base"), color=palette.text_muted, text_align=ft.TextAlign.CENTER),
    ]
    if action is not None:
        children.append(action)
    return ft.Container(
        content=ft.Column(children, spacing=theme.space("3"), horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        alignment=ft.alignment.center,
        padding=theme.space("10"),
    )


# ════════════════════════════════════════════════════════════════
# Field row (detail)
# ════════════════════════════════════════════════════════════════
def field_row(palette: Palette, label: str, value: str) -> ft.Control:
    return ft.Row([
        ft.Text(label, size=theme.font_size("sm"), color=palette.text_secondary, width=110),
        ft.Text(value or "未读取到", size=theme.font_size("sm"),
                color=palette.text_primary if value else palette.text_muted,
                selectable=True, expand=True),
    ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.START)


# ════════════════════════════════════════════════════════════════
# Buttons
# ════════════════════════════════════════════════════════════════
def primary_button(text: str, on_click: Callable, *, icon: Optional[str] = None, disabled: bool = False) -> ft.FilledButton:
    return ft.FilledButton(text=text, icon=icon, on_click=on_click, disabled=disabled)


def secondary_button(text: str, on_click: Callable, *, icon: Optional[str] = None, disabled: bool = False) -> ft.OutlinedButton:
    return ft.OutlinedButton(text=text, icon=icon, on_click=on_click, disabled=disabled)


def danger_button(palette: Palette, text: str, on_click: Callable, *, icon: Optional[str] = None, disabled: bool = False) -> ft.OutlinedButton:
    return ft.OutlinedButton(text=text, icon=icon, on_click=on_click, disabled=disabled,
                             style=ft.ButtonStyle(color=palette.danger))


def ghost_icon_button(icon: str, on_click: Callable, *, tooltip: str = "", disabled: bool = False) -> ft.IconButton:
    return ft.IconButton(icon=icon, tooltip=tooltip, on_click=on_click, disabled=disabled)


# ════════════════════════════════════════════════════════════════
# Badges
# ════════════════════════════════════════════════════════════════
class StatusBadge(ft.Container):
    def __init__(self, palette: Palette, text: str, kind: str = "idle") -> None:
        color_map: Dict[str, tuple] = {
            "ok": (palette.success, palette.success_light or "#1A00A870"),
            "warn": (palette.warning, palette.warning_light or "#1AED7B2F"),
            "error": (palette.danger, palette.danger_light or "#1AE34D59"),
            "idle": (palette.text_muted, palette.surface_hover),
            "info": (palette.primary, palette.info_light or palette.primary_light),
        }
        fg, bg = color_map.get(kind, color_map["idle"])
        super().__init__(
            content=ft.Row([
                ft.Container(width=8, height=8, bgcolor=fg, border_radius=theme.radius("full")),
                ft.Text(text, size=theme.font_size("sm"), color=fg),
            ], spacing=theme.space("2"), tight=True),
            bgcolor=bg,
            border_radius=theme.radius("full"),
            padding=ft.padding.symmetric(horizontal=10, vertical=4),
        )


class CountBadge(ft.Container):
    """Small numeric badge (pill)."""
    def __init__(self, palette: Palette, count: int, kind: str = "info") -> None:
        color_map = {
            "info": (palette.primary, palette.info_light or palette.primary_light),
            "ok": (palette.success, palette.success_light or "#1A00A870"),
            "warn": (palette.warning, palette.warning_light or "#1AED7B2F"),
        }
        fg, bg = color_map.get(kind, color_map["info"])
        super().__init__(
            content=ft.Text(str(count), size=theme.font_size("xs"), weight=theme.WEIGHT_BOLD, color=fg),
            bgcolor=bg,
            border_radius=theme.radius("full"),
            padding=ft.padding.symmetric(horizontal=8, vertical=2),
        )


# ════════════════════════════════════════════════════════════════
# Tabs helper
# ════════════════════════════════════════════════════════════════
def tab_bar(palette: Palette, tabs: List[Dict[str, str]], on_change: Callable) -> ft.Tabs:
    """Build a Flet Tabs control from a list of {label, icon} dicts."""
    ftabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[ft.Tab(text=t["label"], icon=t.get("icon")) for t in tabs],
        on_change=lambda e: on_change(e.control.selected_index),
    )
    return ftabs


# ════════════════════════════════════════════════════════════════
# Timeline
# ════════════════════════════════════════════════════════════════
def timeline_item(
    palette: Palette,
    title: str,
    subtitle: str = "",
    time: str = "",
    kind: str = "info",
) -> ft.Control:
    color_map = {
        "ok": palette.success, "warn": palette.warning,
        "error": palette.danger, "info": palette.primary,
    }
    dot_color = color_map.get(kind, palette.text_muted)
    return ft.Row([
        ft.Column([
            ft.Container(width=10, height=10, bgcolor=dot_color, border_radius=theme.radius("full")),
            ft.Container(width=1, expand=True, bgcolor=palette.border_light),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        ft.Column([
            ft.Text(title, size=theme.font_size("sm"), weight=theme.WEIGHT_MEDIUM, color=palette.text_primary),
            ft.Text(subtitle, size=theme.font_size("xs"), color=palette.text_muted) if subtitle else ft.Container(),
        ], spacing=2, expand=True),
        ft.Text(time, size=theme.font_size("xs"), color=palette.text_muted) if time else ft.Container(),
    ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.START)


# ════════════════════════════════════════════════════════════════
# Toast & errors
# ════════════════════════════════════════════════════════════════
def toast(page: ft.Page, message: str, kind: str = "info", palette: Optional[Palette] = None) -> None:
    if palette is None:
        palette = theme.LIGHT
    color_map = {
        "ok": palette.success, "error": palette.danger,
        "warn": palette.warning, "info": palette.primary,
    }
    bar = ft.SnackBar(
        content=ft.Text(message, color="#FFFFFF"),
        bgcolor=color_map.get(kind, palette.primary),
        behavior=ft.SnackBarBehavior.FLOATING,
        margin=ft.margin.only(bottom=20, left=20, right=20),
    )
    page.open(bar)


def show_error(
    page: ft.Page,
    exc: BaseException,
    context: str = "",
    palette: Optional[Palette] = None,
    log: Optional[Callable[[str], None]] = None,
) -> None:
    friendly = describe_error(exc, context)
    if log is not None:
        try:
            log(f"{friendly.as_line()} (原始错误: {exc!r})")
        except Exception:
            pass
    toast(page, friendly.as_line(), "error", palette)


# ════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════
def _alpha20(hex_color: str) -> str:
    """Return hex_color with ~20% opacity in ARGB format."""
    c = hex_color.lstrip("#")
    if len(c) == 6:
        return f"#33{c}"
    return hex_color


__all__ = [
    "run_in_background",
    "card", "gradient_card", "section_title",
    "metric_tile", "stat_chip", "quick_action_tile",
    "empty_state", "field_row",
    "primary_button", "secondary_button", "danger_button", "ghost_icon_button",
    "StatusBadge", "CountBadge",
    "tab_bar", "timeline_item",
    "toast", "show_error",
]
